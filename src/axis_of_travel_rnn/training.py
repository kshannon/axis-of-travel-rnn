"""
Training and evaluation: the model maker, the Trainer, predict, window_sse, the persistence baseline and the hidden states of whole blocks.
"""

import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from tqdm.auto import tqdm

from .models import MemorylessMLP, PredictiveRNN

EVAL_BATCH = 128  # windows per batch when no gradient is needed
GRAD_CLIP = 1.0  # the largest gradient norm of a step, as in the pilot
NUM_THREADS = 4  # torch threads on the cpu
CHECKPOINT = "epoch_{:03d}.pt"  # one before the first epoch (epoch 0) and one after each


def make_model(kind, n_in, n_out, hidden_size, seed):
    """
    A freshly initialised rnn or memoryless network whose weights the seed fixes, the global torch generator left as it was.
    """
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        if kind == "memoryless":
            return MemorylessMLP(n_in, hidden_size, n_out)
        return PredictiveRNN(n_in, hidden_size, n_out)


def predict(model, x):
    """
    The prediction (B, T, n_out) of either network, which return different things.
    """
    output = model(x)
    return output[0] if isinstance(output, tuple) else output


def on_device(batch, device):
    """
    The tensors of a batch moved to the device.
    """
    return {key: value.to(device) if torch.is_tensor(value) else value for key, value in batch.items()}


def window_sse(prediction, batch):
    """
    The summed squared error of each window (mean over the output columns, masked by loss_weight) and its weight.
    """
    error = ((prediction - batch["y"]) ** 2).mean(-1) * batch["loss_weight"]
    return error.sum(1), batch["loss_weight"].sum(1)


def mean_loss(dataset, predict_fn, device="cpu"):
    """
    The masked mean squared error over every window of the dataset for predict_fn(batch) predictions.
    """
    sse, weight = 0.0, 0.0
    with torch.no_grad():
        for batch in torch.utils.data.DataLoader(dataset, batch_size=EVAL_BATCH):
            window_error, window_weight = window_sse(predict_fn(on_device(batch, device)), on_device(batch, device))
            sse, weight = sse + float(window_error.sum()), weight + float(window_weight.sum())
    return sse / weight


def model_loss(model, dataset, device="cpu"):
    """
    The masked mean squared error of the network on the dataset.
    """
    return mean_loss(dataset, lambda batch: predict(model, batch["x"]), device)


def persistence_loss(dataset):
    """
    The masked mean squared error of predicting the current position as the future one.
    """
    return mean_loss(dataset, lambda batch: batch["current"])


def finite_runs(mask):
    """
    The (start, stop) of every maximal run of True in a boolean array.
    """
    edges = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(int), [0]])))
    return list(zip(edges[::2], edges[1::2]))


def hidden_states(model, dataset, device="cpu"):
    """
    The (T, hidden_size) hidden states of each whole block of the dataset, run from zero over every stretch of finite inputs, NaN elsewhere.
    """
    states = []
    with torch.no_grad():
        for x in dataset.features:
            h = np.full((len(x), model.readout.in_features), np.nan, dtype=np.float32)
            for start, stop in finite_runs(np.isfinite(x).all(axis=1)):
                h[start:stop] = model(torch.from_numpy(x[start:stop])[None].to(device))[1][0].cpu().numpy()
            states.append(h)
    return states


class Trainer:
    """
    Adam on the masked squared error with gradient clipping, stopped early on the validation loss, the best weights kept.
    """

    def __init__(self, model, learning_rate, batch_size, epochs, patience, device="cpu", checkpoint_dir=None, seed=0):
        torch.set_num_threads(NUM_THREADS)
        self.model, self.device = model.to(device), device
        self.batch_size, self.epochs, self.patience, self.seed = batch_size, epochs, patience, seed
        self.checkpoint_dir = None if checkpoint_dir is None else Path(checkpoint_dir)
        self.parameters = [p for p in model.parameters() if p.requires_grad]
        self.optimiser = torch.optim.Adam(self.parameters, lr=learning_rate)
        self.rows = []  # one per epoch, filled as it goes, so an interrupted run keeps what it did

    def checkpoint(self, epoch):
        """
        Save the weights after this epoch, when there is a checkpoint folder.
        """
        if self.checkpoint_dir is not None:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            torch.save(self.model.state_dict(), self.checkpoint_dir / CHECKPOINT.format(epoch))

    def train_epoch(self, loader):
        """
        One pass over the loader with a gradient step per batch, and the mean batch loss.
        """
        losses = []
        self.model.train()
        for batch in loader:
            batch = on_device(batch, self.device)
            sse, weight = window_sse(predict(self.model, batch["x"]), batch)
            loss = sse.sum() / weight.sum()
            self.optimiser.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.parameters, GRAD_CLIP)
            self.optimiser.step()
            losses.append(loss.item())
        self.model.eval()
        return float(np.mean(losses))

    def fit(self, train_ds, val_ds):
        """
        Train until the validation loss has not improved for patience epochs or the epochs run out, and return the rows.
        """
        generator = torch.Generator().manual_seed(self.seed)
        loader = torch.utils.data.DataLoader(train_ds, batch_size=self.batch_size, shuffle=True, generator=generator)
        assert len(loader) > 0, "no training windows"
        best, best_state, waited = float("inf"), None, 0
        self.checkpoint(0)
        bar = tqdm(range(1, self.epochs + 1), desc="epochs")
        try:
            for epoch in bar:
                start = time.perf_counter()
                train_loss = self.train_epoch(loader)
                val_loss = model_loss(self.model, val_ds, self.device)
                improved = val_loss < best
                if improved:
                    best, waited = val_loss, 0
                    best_state = {key: value.clone() for key, value in self.model.state_dict().items()}
                else:
                    waited += 1
                self.rows.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss,
                                  "seconds": time.perf_counter() - start, "best": improved})
                self.checkpoint(epoch)
                bar.set_postfix(train=f"{train_loss:.5f}", val=f"{val_loss:.5f}")
                if waited >= self.patience:
                    break
        finally:
            bar.close()
            if best_state is not None:
                self.model.load_state_dict(best_state)
        return self.rows
