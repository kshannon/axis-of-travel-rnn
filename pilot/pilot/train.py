"""
Training and evaluation of the pilot's arms: the Trainer, the baselines, run folders with manifests and the sweep.
"""

import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import numpy as np
import torch
from proj_helpers.paths import repo_root
from torch import nn
from tqdm import tqdm

from .analysis import RIDGE_ALPHA, decode_heading, decode_position
from .config import DIETS, NUM_THREADS, RUNS_DIR, WORLDS
from .dataset import (
    NOISY_BLOCKS, EqualWorldBatches, PilotDataset, fit_scaler, make_feature_layout, select_sessions, session_features,
)
from .models import MemorylessMLP, PredictiveRNN
from .worlds import data_hash

EVAL_BATCH = 128  # windows per batch when no gradient is needed
NOISE_SEEDS = {"val": 1, "test": 2}  # input noise of the validation and test data, the same for every arm and seed
EPOCH_STRIDE = 1000  # the training noise of epoch e in a run with seed s is seeded 1000 * s + e: a new draw each epoch
# The preset keys a run depends on besides the data. A cached run is reused only when these are unchanged.
SETTING_KEYS = ("horizon", "horizons", "window", "stride", "no_loss_steps", "input_noise_sd", "n_hidden", "rnn_type",
                "learning_rate", "batch_size", "grad_clip", "patience", "max_epochs", "place_n", "hd_n")


@dataclass(frozen=True)
class ArmSpec:
    input_set: str  # place_only, place_motion or full
    diet: tuple  # the worlds the network trains on, in the order of WORLDS
    kind: str  # trained, untrained (frozen recurrent weights, fitted readout) or memoryless

    @property
    def name(self):
        """
        A folder name for the arm, for example place_only_trained_both.
        """
        return f"{self.input_set}_{self.kind}_{'both' if self.diet == WORLDS else self.diet[0]}"


# ---------------------------------------------------------------------------
# losses and evaluation
# ---------------------------------------------------------------------------

def predict(model, x):
    """
    The prediction (B, T, n_out) of either network, which return different things.
    """
    output = model(x)
    return output[0] if isinstance(output, tuple) else output


def window_sse(prediction, batch):
    """
    The summed squared error of each window (mean over the output cells, masked by loss_weight) and its weight.
    """
    error = ((prediction - batch["y"]) ** 2).mean(-1) * batch["loss_weight"]
    return error.sum(1), batch["loss_weight"].sum(1)


def window_errors(dataset, predict_fn):
    """
    The summed error and weight of every window of the dataset, and its world, for predict_fn(batch) predictions.
    """
    sse, weight = [], []
    with torch.no_grad():
        for batch in torch.utils.data.DataLoader(dataset, batch_size=EVAL_BATCH):
            window_error, window_weight = window_sse(predict_fn(batch), batch)
            sse.append(window_error)
            weight.append(window_weight)
    worlds = np.array([dataset.sessions[k].world for k, _ in dataset.windows])
    return torch.cat(sse).numpy(), torch.cat(weight).numpy(), worlds


def mean_losses(errors):
    """
    The masked mean squared error over all windows ("all") and over the windows of each world.
    """
    sse, weight, worlds = errors
    losses = {"all": float(sse.sum() / weight.sum())}
    for world in sorted(set(worlds.tolist())):
        losses[world] = float(sse[worlds == world].sum() / weight[worlds == world].sum())
    return losses


def losses_on_test(model, layout, scaler, cfg, test):
    """
    The test loss of a network at each horizon of cfg, on these test sessions with the usual input noise.
    """
    losses = {}
    for horizon in cfg["horizons"]:
        dataset = PilotDataset(test, layout, cfg, horizon, scaler, NOISE_SEEDS["test"])
        losses[str(horizon)] = mean_losses(window_errors(dataset, lambda batch: predict(model, batch["x"])))
    return losses


def current_place(dataset, batch):
    """
    The clean place vectors at the steps of the windows of a batch.
    """
    rows = [dataset.sessions[k].place[start:start + dataset.window]
            for k, start in zip(batch["session"].tolist(), batch["start"].tolist())]
    return torch.from_numpy(np.stack(rows))


def persistence_losses(cfg, sessions):
    """
    Test loss at each horizon of predicting the current place vector: the clean one and the noisy input the net sees.
    """
    layout = make_feature_layout("place_only", cfg)  # in this layout the input is the noisy place vector
    scaler = fit_scaler(select_sessions(sessions, cfg, "train", WORLDS))
    test = select_sessions(sessions, cfg, "test", WORLDS)
    losses = {"clean": {}, "noisy": {}}
    for horizon in cfg["horizons"]:
        dataset = PilotDataset(test, layout, cfg, horizon, scaler, NOISE_SEEDS["test"])
        losses["clean"][str(horizon)] = mean_losses(window_errors(dataset, lambda batch: current_place(dataset, batch)))
        losses["noisy"][str(horizon)] = mean_losses(window_errors(dataset, lambda batch: batch["x"]))
    return losses


def hidden_states(model, sessions, layout, scaler, cfg, noise_seed):
    """
    The (T, n_hidden) hidden states of each whole session, from noisy inputs as in training.
    """
    states = []
    with torch.no_grad():
        for session in sessions:
            x = session_features(session, layout, scaler)
            rng = np.random.default_rng([noise_seed, session.seed])
            for name, columns in layout.columns.items():
                if name in NOISY_BLOCKS:
                    x[:, columns] += rng.normal(0.0, cfg["input_noise_sd"], size=x[:, columns].shape)
            states.append(model(torch.from_numpy(x)[None])[1][0].numpy())
    return states


def decoder_scores(model, layout, scaler, cfg, fit, test):
    """
    Test R-squared of ridge decoders from hidden state to position and heading, fitted on the fit sessions.
    """
    h_fit = hidden_states(model, fit, layout, scaler, cfg, NOISE_SEEDS["val"])
    h_test = hidden_states(model, test, layout, scaler, cfg, NOISE_SEEDS["test"])
    scores = {"position": {}, "heading": {}}
    for group in ("all", *WORLDS):  # all sessions pooled, then each world on its own
        fit_pairs = [(h, s) for h, s in zip(h_fit, fit) if group in ("all", s.world)]
        test_pairs = [(h, s) for h, s in zip(h_test, test) if group in ("all", s.world)]
        h_a, h_b = (np.concatenate([h for h, _ in pairs]) for pairs in (fit_pairs, test_pairs))
        a, b = ({field: np.concatenate([getattr(s, field) for _, s in pairs]) for field in ("pos", "heading")}
                for pairs in (fit_pairs, test_pairs))
        scores["position"][group] = decode_position(h_a, a["pos"], h_b, b["pos"])
        scores["heading"][group] = decode_heading(h_a, a["heading"], h_b, b["heading"])
    return scores


# ---------------------------------------------------------------------------
# models, readout fit, trainer
# ---------------------------------------------------------------------------

def make_model(arm, cfg, seed):
    """
    A freshly initialised network for the arm; the seed fixes its weights through the global torch generator.
    """
    layout = make_feature_layout(arm.input_set, cfg)
    torch.manual_seed(seed)
    if arm.kind == "memoryless":
        return MemorylessMLP(layout.n_in, cfg["n_hidden"], layout.n_out)
    return PredictiveRNN(layout.n_in, cfg["n_hidden"], layout.n_out, cfg["rnn_type"],
                         freeze_recurrent=arm.kind == "untrained")


def fit_readout(model, dataset):
    """
    Set the readout of a frozen network to the ridge regression of the target on its hidden states, no gradient steps.
    """
    n_hidden, n_out = model.readout.in_features, model.readout.out_features
    n, sum_h, sum_y = 0, np.zeros(n_hidden), np.zeros(n_out)
    h_h, h_y = np.zeros((n_hidden, n_hidden)), np.zeros((n_hidden, n_out))
    with torch.no_grad():
        for batch in torch.utils.data.DataLoader(dataset, batch_size=EVAL_BATCH):
            keep = batch["loss_weight"] > 0
            h, y = model(batch["x"])[1][keep].double().numpy(), batch["y"][keep].double().numpy()
            n, sum_h, sum_y, h_h, h_y = n + len(h), sum_h + h.sum(0), sum_y + y.sum(0), h_h + h.T @ h, h_y + h.T @ y
        mean_h, mean_y = sum_h / n, sum_y / n
        weights = np.linalg.solve(h_h - n * np.outer(mean_h, mean_h) + RIDGE_ALPHA * np.eye(n_hidden),
                                  h_y - n * np.outer(mean_h, mean_y))
        model.readout.weight.copy_(torch.from_numpy(weights.T))
        model.readout.bias.copy_(torch.from_numpy(mean_y - mean_h @ weights))


def empty_history(arm, seed):
    """
    The loss curves and timings of a run before its first epoch.
    """
    return {"arm": arm.name, "seed": seed, "train_loss": [], "val_loss": [], "epoch_seconds": [], "best_epoch": None,
            "early_stopped": False}


class Trainer:
    """
    Adam on the masked squared error with gradient clipping, stopped early on the validation loss.
    """

    def __init__(self, model, arm, cfg, seed):
        torch.set_num_threads(NUM_THREADS)
        self.model, self.arm, self.cfg, self.seed = model, arm, cfg, seed
        self.parameters = [p for p in model.parameters() if p.requires_grad]
        self.optimiser = torch.optim.Adam(self.parameters, lr=cfg["learning_rate"])
        self.history = empty_history(arm, seed)  # filled epoch by epoch, so an interrupted run keeps what it did

    def train_epoch(self, loader):
        """
        One pass over the loader with a gradient step per batch; the mean batch loss.
        """
        losses = []
        for batch in loader:
            sse, weight = window_sse(predict(self.model, batch["x"]), batch)
            loss = sse.sum() / weight.sum()
            self.optimiser.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.parameters, self.cfg["grad_clip"])
            self.optimiser.step()
            losses.append(loss.item())
        return float(np.mean(losses))

    def fit(self, train_ds, val_ds, on_epoch=None):
        """
        Train until the validation loss has not improved for patience epochs or max_epochs; the best weights are kept.
        """
        history = self.history
        loader = torch.utils.data.DataLoader(
            train_ds, batch_sampler=EqualWorldBatches(train_ds, self.cfg["batch_size"], self.seed))
        assert len(loader) > 0, "fewer training windows than one batch"
        best, best_state, waited = float("inf"), None, 0
        bar = tqdm(range(1, self.cfg["max_epochs"] + 1), desc=f"{self.arm.name} s{self.seed}", leave=False)
        try:
            for epoch in bar:
                start = time.perf_counter()
                train_ds.seed = EPOCH_STRIDE * self.seed + epoch  # a new noise draw each epoch
                train_loss = self.train_epoch(loader)
                with torch.no_grad():
                    val_loss = mean_losses(window_errors(val_ds, lambda batch: predict(self.model, batch["x"])))["all"]
                history["train_loss"].append(train_loss)
                history["val_loss"].append(val_loss)
                history["epoch_seconds"].append(time.perf_counter() - start)
                if val_loss < best:
                    best, waited = val_loss, 0
                    best_state = {key: value.clone() for key, value in self.model.state_dict().items()}
                    history["best_epoch"] = epoch
                else:
                    waited += 1
                bar.set_postfix(train=f"{train_loss:.5f}", val=f"{val_loss:.5f}", best=history["best_epoch"])
                if on_epoch is not None:
                    on_epoch(epoch, self.model, history)
                if waited >= self.cfg["patience"]:
                    history["early_stopped"] = True
                    break
        finally:
            bar.close()
            if best_state is not None:
                self.model.load_state_dict(best_state)
        return history


# ---------------------------------------------------------------------------
# run folders
# ---------------------------------------------------------------------------

def run_dir(arm, seed, cfg):
    """
    Where a run lives: datasets/pilot/runs/<preset>_<data hash>/<arm name>_s<seed>.
    """
    return RUNS_DIR / f"{cfg['name']}_{data_hash(cfg)}" / f"{arm.name}_s{seed}"


def status_of(path):
    """
    The status in the manifest of a run folder (complete, interrupted or failed), or None if there is none.
    """
    manifest = path / "manifest.json"
    return json.loads(manifest.read_text())["status"] if manifest.exists() else None


def load_run(path):
    """
    The manifest and metrics of a run folder as plain dicts.
    """
    return {"manifest": json.loads((path / "manifest.json").read_text()),
            "metrics": json.loads((path / "metrics.json").read_text())}


def load_model(path, cfg):
    """
    The network of a run folder with its saved weights.
    """
    manifest = json.loads((path / "manifest.json").read_text())
    arm = ArmSpec(manifest["arm"]["input_set"], tuple(manifest["arm"]["diet"]), manifest["arm"]["kind"])
    model = make_model(arm, cfg, manifest["seed"])
    model.load_state_dict(torch.load(path / "weights.pt"))
    return model


def settings(cfg):
    """
    The values of the SETTING_KEYS of a preset as plain JSON values, to compare with those a run was made with.
    """
    return json.loads(json.dumps({key: cfg[key] for key in SETTING_KEYS}))


def git(*args):
    """
    The output of a git command in the repository.
    """
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=repo_root()).stdout.strip()


def environment():
    """
    What the run was made with: the commit and whether the tree has changes, the lockfile hash and the torch build.
    """
    lockfile = hashlib.sha256((repo_root() / "pixi.lock").read_bytes()).hexdigest()
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "lockfile_sha256": lockfile, "torch": torch.__version__, "num_threads": NUM_THREADS}


def split_sessions(arm, cfg, sessions):
    """
    The sessions a run uses per job: train and val of its diet, decoder fit (validation) and test of both worlds.
    """
    return {"train": select_sessions(sessions, cfg, "train", arm.diet),
            "val": select_sessions(sessions, cfg, "val", arm.diet),
            "decoder_fit": select_sessions(sessions, cfg, "val", WORLDS),
            "test": select_sessions(sessions, cfg, "test", WORLDS)}


def dataset_info(cfg, splits):
    """
    The preset, the data hash and the seeds of the sessions the run used for each job in splits.
    """
    return {"preset": cfg["name"], "data_hash": data_hash(cfg),
            **{job: [s.seed for s in group] for job, group in splits.items()}}


def save_run(path, model, manifest, metrics):
    """
    Write the weights, metrics and then the manifest; a folder without a manifest is not a finished write.
    """
    path.mkdir(parents=True)
    torch.save(model.state_dict(), path / "weights.pt")
    (path / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2))


def stamp():
    """
    The time now in UTC as a compact string for folder names.
    """
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_arm(arm, seed, cfg, sessions, on_epoch=None):
    """
    Train or fit one arm and seed, evaluate it and write its run folder; a complete run that exists is returned as is.
    """
    path = run_dir(arm, seed, cfg)
    if status_of(path) == "complete":
        assert settings(load_run(path)["manifest"]["cfg"]) == settings(cfg), f"{path} was run with other settings"
        return path
    if path.exists():  # an interrupted or failed attempt is kept, beside the new run
        path.rename(path.with_name(f"{path.name}.{status_of(path) or 'incomplete'}-{stamp()}"))
    torch.set_num_threads(NUM_THREADS)
    started, clock = datetime.now(timezone.utc), time.perf_counter()
    model = make_model(arm, cfg, seed)
    splits = split_sessions(arm, cfg, sessions)  # the manifest records these same lists
    history, metrics, status, failure = empty_history(arm, seed), {}, "complete", None
    try:
        layout = make_feature_layout(arm.input_set, cfg)
        scaler = fit_scaler(splits["train"])
        train_ds = PilotDataset(splits["train"], layout, cfg, cfg["horizon"], scaler, EPOCH_STRIDE * seed)
        val_ds = PilotDataset(splits["val"], layout, cfg, cfg["horizon"], scaler, NOISE_SEEDS["val"])
        if arm.kind == "untrained":
            fit_readout(model, train_ds)
        else:
            trainer = Trainer(model, arm, cfg, seed)
            history = trainer.history
            trainer.fit(train_ds, val_ds, on_epoch)
        metrics["fit_seconds"] = time.perf_counter() - clock
        metrics["test_loss"] = losses_on_test(model, layout, scaler, cfg, splits["test"])
        if arm.kind != "memoryless":
            metrics["decoder"] = decoder_scores(model, layout, scaler, cfg, splits["decoder_fit"], splits["test"])
    except KeyboardInterrupt:
        status = "interrupted"
    except Exception as error:
        status, failure = "failed", error
        metrics["error"] = repr(error)
    metrics = {**history, "epochs": len(history["train_loss"]), **metrics, "seconds": time.perf_counter() - clock}
    manifest = {"arm": {**asdict(arm), "name": arm.name}, "seed": seed, "status": status,
                "started": started.isoformat(timespec="seconds"),
                "ended": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "dataset": dataset_info(cfg, splits), "cfg": cfg, "environment": environment()}
    save_run(path, model, manifest, metrics)
    if failure is not None:
        raise failure
    return path


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------

def arms_for(input_set, diets=DIETS):
    """
    The arms of one input set in running order: the main trained arm, the controls, then trained arms of other diets.
    """
    return ([ArmSpec(input_set, diets[0], "trained"), ArmSpec(input_set, WORLDS, "memoryless"),
             ArmSpec(input_set, WORLDS, "untrained")] + [ArmSpec(input_set, diet, "trained") for diet in diets[1:]])


def seeds_of(arm, cfg):
    """
    The seeds the preset gives to this kind of arm.
    """
    return cfg[f"{arm.kind}_seeds"]


def sweep_jobs(cfg, input_sets, diets=DIETS):
    """
    Every (arm, seed) of the sweep in running order.
    """
    return [(arm, seed) for input_set in input_sets for arm in arms_for(input_set, diets)
            for seed in seeds_of(arm, cfg)]


def load_results(cfg, jobs):
    """
    {(arm, seed): {"manifest": ..., "metrics": ...}} for the jobs that have a complete run folder.
    """
    results = {}
    for arm, seed in jobs:
        path = run_dir(arm, seed, cfg)
        if status_of(path) == "complete":
            results[(arm, seed)] = load_run(path)
    return results


def run_sweep(cfg, sessions, input_sets, diets=DIETS, on_epoch=None):
    """
    Run every arm and seed for these input sets, skipping complete runs; stops at an interrupt. Returns load_results.
    """
    jobs = sweep_jobs(cfg, input_sets, diets)
    with tqdm(total=len(jobs), desc="sweep") as bar:
        for arm, seed in jobs:
            bar.set_postfix(run=f"{arm.name}_s{seed}")
            path = run_arm(arm, seed, cfg, sessions, on_epoch)
            bar.update()
            if status_of(path) == "interrupted":
                print(f"interrupted in {path.name}, which is kept; run the sweep again to continue")
                break
    return load_results(cfg, jobs)


# ---------------------------------------------------------------------------
# tables and the section 2 checks
# ---------------------------------------------------------------------------

def format_rows(rows):
    """
    Rows of cells as lines with the columns padded to the same width.
    """
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    return ["  ".join(str(cell).ljust(width) for cell, width in zip(row, widths)) for row in rows]


def mean_sd(values):
    """
    "mean (sd)" of the values, the mean alone for one value and "-" for none.
    """
    if not values:
        return "-"
    return f"{np.mean(values):.5f}" if len(values) == 1 else f"{np.mean(values):.5f} ({np.std(values):.5f})"


def label(arm):
    """
    The arm's name without its input set.
    """
    return arm.name.removeprefix(arm.input_set + "_")


def losses_of(results, arm, cfg, horizon, world="all"):
    """
    The test losses at this horizon of the complete runs of an arm, one per seed.
    """
    return [results[(arm, seed)]["metrics"]["test_loss"][str(horizon)][world]
            for seed in seeds_of(arm, cfg) if (arm, seed) in results]


def loss_table(cfg, results, persistence, input_sets, world="all"):
    """
    Lines of test loss (mean and sd over seeds) per input set and horizon: both persistence baselines and every arm.
    """
    arms = arms_for("place_only")
    rows = [("input set", "horizon", "persistence", "persistence (noisy)", *(label(arm) for arm in arms))]
    for input_set in input_sets:
        for horizon in cfg["horizons"]:
            rows.append((input_set, horizon, f"{persistence['clean'][str(horizon)][world]:.5f}",
                         f"{persistence['noisy'][str(horizon)][world]:.5f}",
                         *(mean_sd(losses_of(results, arm, cfg, horizon, world)) for arm in arms_for(input_set))))
    return format_rows(rows)


def decoder_table(cfg, results, input_sets):
    """
    Lines of the mean test R-squared of the position and heading decoders per input set and arm with hidden states.
    """
    groups = ("all", *WORLDS)
    rows = [("input set", "arm", *(f"{target} {group}" for target in ("position", "heading") for group in groups))]
    for input_set in input_sets:
        for arm in arms_for(input_set):
            runs = [results[(arm, seed)]["metrics"] for seed in seeds_of(arm, cfg) if (arm, seed) in results]
            if arm.kind != "memoryless" and runs:
                rows.append((input_set, label(arm), *(f"{np.mean([run['decoder'][target][group] for run in runs]):.3f}"
                                                      for target in ("position", "heading") for group in groups)))
    return format_rows(rows)


def section_2_checks(cfg, results, persistence, input_sets, thr):
    """
    The brief's 7.5 checks against the thresholds as (name, passed, numbers): the worst trained seed against clean
    persistence at the training horizon and, for place_only, against the memoryless net; the weakest position decoder.
    """
    horizon, checks = cfg["horizon"], []
    for input_set in input_sets:
        trained, memoryless = arms_for(input_set)[:2]
        runs = [results[(trained, seed)]["metrics"] for seed in seeds_of(trained, cfg) if (trained, seed) in results]
        if len(runs) < len(seeds_of(trained, cfg)):
            checks.append((f"{input_set}: trained runs", False,
                           f"only {len(runs)} of {len(seeds_of(trained, cfg))} trained seeds finished"))
            continue
        losses = [run["test_loss"][str(horizon)]["all"] for run in runs]
        clean, noisy = (persistence[kind][str(horizon)]["all"] for kind in ("clean", "noisy"))
        limit = thr["beat_persistence_ratio"]
        checks.append((f"{input_set}: trained beats persistence at horizon {horizon}", max(losses) <= limit * clean,
                       f"worst seed {max(losses) / clean:.3f} x persistence (mean {np.mean(losses) / clean:.3f}), "
                       f"limit {limit}; against noisy persistence {max(losses) / noisy:.3f}"))
        if input_set == "place_only":
            reference = losses_of(results, memoryless, cfg, horizon)
            limit = thr["beat_memoryless_ratio"]
            if reference:
                checks.append((f"{input_set}: trained beats memoryless at horizon {horizon}",
                               bool(max(losses) <= limit * np.mean(reference)),
                               f"worst seed {max(losses) / np.mean(reference):.3f} x memoryless, limit {limit}"))
            else:
                checks.append((f"{input_set}: trained beats memoryless at horizon {horizon}", False,
                               "the memoryless run did not finish"))
        weakest = min(run["decoder"]["position"]["all"] for run in runs)
        checks.append((f"{input_set}: position decodable from hidden state", weakest >= thr["position_r2_min"],
                       f"weakest seed R2 {weakest:.3f}, limit {thr['position_r2_min']}"))
    return checks
