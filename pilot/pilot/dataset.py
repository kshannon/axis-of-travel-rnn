"""
The input sets, the scaler, noisy windows with clean future place targets, diets, batches and the leakage assert.
"""

from dataclasses import dataclass

import numpy as np
import torch

from .worlds import split_of

INPUT_SETS = {
    "place_only": ("place",),
    "place_motion": ("place", "turn_rate", "speed"),
    "full": ("place", "hd", "turn_rate", "speed"),
}
NOISY_BLOCKS = ("place", "hd")  # the blocks that get Gaussian input noise; turn rate and speed stay exact
TURN_RATE_CLIP_SD = 3.0  # turn rate is clipped at its training mean plus or minus this many standard deviations
LEAKAGE_CORRELATION = 0.999  # an input column correlated this much with a folded heading is a leak
MIN_SD = 1e-12  # a column flatter than this counts as constant when standardising


@dataclass(frozen=True)
class FeatureLayout:
    input_set: str
    columns: dict  # block name -> slice of the input vector, in input set order
    n_in: int
    n_out: int  # always the number of place cells


# ---------------------------------------------------------------------------
# input sets, scaler, features
# ---------------------------------------------------------------------------

def block_widths(cfg):
    """
    The number of input columns of each block.
    """
    return {"place": cfg["place_n"], "hd": cfg["hd_n"], "turn_rate": 1, "speed": 1}


def make_feature_layout(input_set, cfg):
    """
    Where each block of this input set sits in the input vector; the output is always the place cell population.
    """
    widths = block_widths(cfg)
    columns, start = {}, 0
    for name in INPUT_SETS[input_set]:
        columns[name] = slice(start, start + widths[name])
        start += widths[name]
    return FeatureLayout(input_set=input_set, columns=columns, n_in=start, n_out=cfg["place_n"])


def fit_scaler(train_sessions):
    """
    Plain numbers from the training sessions only: the turn rate clip limits, the mean and sd of turn rate and speed.
    """
    turn = np.concatenate([s.turn_rate for s in train_sessions])
    speed = np.concatenate([s.speed for s in train_sessions])
    low = turn.mean() - TURN_RATE_CLIP_SD * turn.std()
    high = turn.mean() + TURN_RATE_CLIP_SD * turn.std()
    clipped = np.clip(turn, low, high)
    return {"turn_rate_low": float(low), "turn_rate_high": float(high), "turn_rate_mean": float(clipped.mean()),
            "turn_rate_sd": float(clipped.std()), "speed_mean": float(speed.mean()), "speed_sd": float(speed.std())}


def session_features(session, layout, scaler):
    """
    The clean input matrix (T, n_in) float32 of a session: the blocks of the input set side by side, motion z-scored.
    """
    turn = np.clip(session.turn_rate, scaler["turn_rate_low"], scaler["turn_rate_high"])
    blocks = {"place": session.place, "hd": session.hd,
              "turn_rate": ((turn - scaler["turn_rate_mean"]) / scaler["turn_rate_sd"])[:, None],
              "speed": ((session.speed - scaler["speed_mean"]) / scaler["speed_sd"])[:, None]}
    return np.concatenate([blocks[name] for name in layout.columns], axis=1).astype(np.float32)


def select_sessions(sessions, cfg, split, worlds):
    """
    The sessions of these worlds in this split (train, val or test): worlds in the order given, then by session index.
    """
    return [s for world in worlds for i, s in enumerate(sessions[world]) if split_of(cfg, i) == split]


# ---------------------------------------------------------------------------
# leakage assert
# ---------------------------------------------------------------------------

def standardise(a):
    """
    The columns of a with mean 0 and sd 1, a constant column left at 0.
    """
    a = a.astype(np.float64)
    return (a - a.mean(axis=0)) / np.maximum(a.std(axis=0), MIN_SD)


def assert_no_leakage(x, heading, layout, cfg):
    """
    Fails unless x has exactly the columns its input set implies and none is a folded heading; x is clean, not noisy.
    """
    assert tuple(layout.columns) == INPUT_SETS[layout.input_set], tuple(layout.columns)
    widths = block_widths(cfg)
    assert x.shape[1] == layout.n_in == sum(widths[name] for name in INPUT_SETS[layout.input_set]), x.shape
    folded = np.column_stack([np.mod(heading, np.pi), np.cos(2 * heading), np.sin(2 * heading)])
    correlation = np.abs(standardise(x).T @ standardise(folded)) / len(x)
    column = int(np.argmax(correlation.max(axis=1)))
    assert correlation.max() <= LEAKAGE_CORRELATION, f"column {column} is a folded heading: {correlation.max():.4f}"


# ---------------------------------------------------------------------------
# dataset and batches
# ---------------------------------------------------------------------------

# An item is x (window, n_in) noisy inputs, y (window, n_out) the clean place vector horizon steps ahead, loss_weight
# (window,), world, session (index into sessions) and start (first step of the window). The noise of an item depends
# only on seed, the session's own seed and start, so a fixed seed gives the same inputs every time; assign a new seed
# to redraw them.
class PilotDataset(torch.utils.data.Dataset):
    """
    Windows of cfg window steps every cfg stride steps over whole sessions, none crossing a session boundary.
    """

    def __init__(self, sessions, layout, cfg, horizon, scaler, seed):
        self.sessions, self.layout, self.horizon, self.seed = sessions, layout, horizon, seed
        self.window, self.noise_sd, self.no_loss_steps = cfg["window"], cfg["input_noise_sd"], cfg["no_loss_steps"]
        self.features = [session_features(s, layout, scaler) for s in sessions]
        for s, x in zip(sessions, self.features):
            assert_no_leakage(x, s.heading, layout, cfg)
        # the last window ends horizon steps before the session does, so every target is inside the session
        self.windows = [(k, start) for k, s in enumerate(sessions)
                        for start in range(0, len(s.t) - self.window - horizon + 1, cfg["stride"])]

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, i):
        k, start = self.windows[i]
        session, stop = self.sessions[k], start + self.window
        x = self.features[k][start:stop].copy()
        rng = np.random.default_rng([self.seed, session.seed, start])
        for name, columns in self.layout.columns.items():
            if name in NOISY_BLOCKS:
                x[:, columns] += rng.normal(0.0, self.noise_sd, size=x[:, columns].shape)
        loss_weight = np.ones(self.window, dtype=np.float32)
        loss_weight[:self.no_loss_steps] = 0.0
        y = session.place[start + self.horizon:stop + self.horizon]
        return {"x": torch.from_numpy(x), "y": torch.from_numpy(y.copy()), "loss_weight": torch.from_numpy(loss_weight),
                "world": session.world, "session": k, "start": start}


# Each pass reshuffles from one seeded generator and ends when the smallest world runs out.
class EqualWorldBatches:
    """
    Batches of dataset indices with an equal share from each world of the dataset, for DataLoader batch_sampler.
    """

    def __init__(self, dataset, batch_size, seed):
        worlds = np.array([dataset.sessions[k].world for k, _ in dataset.windows])
        self.by_world = [np.flatnonzero(worlds == world) for world in sorted(set(worlds))]
        self.share = batch_size // len(self.by_world)
        self.rng = np.random.default_rng(seed)

    def __len__(self):
        return min(len(indices) for indices in self.by_world) // self.share

    def __iter__(self):
        shuffled = [self.rng.permutation(indices) for indices in self.by_world]
        for b in range(len(self)):
            yield np.concatenate([indices[b * self.share:(b + 1) * self.share] for indices in shuffled]).tolist()
