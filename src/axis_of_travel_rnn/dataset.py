"""
Windows of blocks at the window settings, the scaler fitted on train only, a torch Dataset of inputs and future positions, and the leakage assertion.
"""

import numpy as np
import torch

from .blocks import BlockEngine

# The columns a network may be given (AGENTS.md rule 1): position, and speed, which is derived from position alone. No
# heading, turn rate, phase, trip, run, path or anything derived from them. Position only is the default.
ALLOWED_INPUTS = ("x", "y", "speed")
DEFAULT_INPUTS = ("x", "y")
TARGETS = ("x", "y")  # the future position, scaled as the position inputs are

LEAKAGE_CORRELATION = 0.999  # an input column correlated this much with a folded heading is a leak
MIN_SD = 1e-12  # a column flatter than this counts as constant when standardising


def make_windows(blocks, settings):
    """
    The windows of every block that passes its verdict, each a dict of the block's index and frame bounds, and the verdict of every block by id.
    """
    windows, verdicts = [], {}
    for k, block in enumerate(blocks):
        found = BlockEngine().windows(block, settings, block["rules"])
        verdicts[block["row"]["block_id"]] = {**found["verdict"], "count": found["count"]}
        if found["verdict"]["ok"]:
            windows += [{"block": k, **{key: row[key] for key in ("first", "burn_in_stop", "window_stop", "stop")}}
                        for row in found["rows"] if row["ok"]]
    return windows, verdicts


def fit_scaler(train_blocks, columns):
    """
    The mean and sd of each column over the finite frames of the training blocks only, as plain numbers.
    """
    scaler = {}
    for name in columns:
        values = np.concatenate([block["arrays"][name] for block in train_blocks]).astype(np.float64)
        values = values[np.isfinite(values)]
        scaler[name] = {"mean": float(values.mean()), "sd": float(max(values.std(), MIN_SD))}
    return scaler


def scaled(block, columns, scaler):
    """
    The columns of a block side by side (T, n) float32, each standardised by the scaler.
    """
    return np.column_stack([(block["arrays"][name] - scaler[name]["mean"]) / scaler[name]["sd"]
                            for name in columns]).astype(np.float32)


def standardise(a):
    """
    The columns of a with mean 0 and sd 1, a constant column left at 0.
    """
    a = a.astype(np.float64)
    return (a - a.mean(axis=0)) / np.maximum(a.std(axis=0), MIN_SD)


def assert_no_leakage(x, heading, columns):
    """
    Fails unless every input column is allowed, x has exactly those columns and none of them is a folded heading.
    """
    assert set(columns) <= set(ALLOWED_INPUTS), f"inputs {sorted(set(columns) - set(ALLOWED_INPUTS))} are not allowed"
    assert x.shape[1] == len(columns), x.shape
    keep = np.isfinite(heading) & np.isfinite(x).all(axis=1)
    if keep.sum() < 2:
        return
    folded = np.column_stack([np.mod(heading[keep], np.pi), np.cos(2 * heading[keep]), np.sin(2 * heading[keep])])
    correlation = np.abs(standardise(x[keep]).T @ standardise(folded)) / keep.sum()
    column = columns[int(np.argmax(correlation.max(axis=1)))]
    assert correlation.max() <= LEAKAGE_CORRELATION, f"{column} is a folded heading: {correlation.max():.4f}"


# An item is x (window, n_in) the scaled inputs, y (window, 2) the scaled position horizon steps ahead of each step,
# current (window, 2) the scaled position at each step for the persistence baseline, loss_weight (window,) 0 in the burn
# in, block (index into blocks) and first (the window's first frame).
class WindowDataset(torch.utils.data.Dataset):
    """
    The windows of these blocks as tensors, a window whose inputs or targets are not all finite left out and counted.
    """

    def __init__(self, blocks, windows, columns, scaler):
        self.blocks, self.columns = blocks, tuple(columns)
        self.features = [scaled(block, self.columns, scaler) for block in blocks]
        self.targets = [scaled(block, TARGETS, scaler) for block in blocks]
        for block, x in zip(blocks, self.features):
            assert_no_leakage(x, block["arrays"]["heading"], self.columns)
        finite = [np.isfinite(self.features[w["block"]][w["first"]:w["window_stop"]]).all()
                  and np.isfinite(self.targets[w["block"]][w["first"]:w["stop"]]).all() for w in windows]
        self.windows = [w for w, ok in zip(windows, finite) if ok]
        self.skipped = len(windows) - len(self.windows)

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, i):
        w = self.windows[i]
        k, first, stop = w["block"], w["first"], w["window_stop"]
        horizon = w["stop"] - stop
        loss_weight = np.ones(stop - first, dtype=np.float32)
        loss_weight[:w["burn_in_stop"] - first] = 0.0
        return {"x": torch.from_numpy(self.features[k][first:stop]),
                "y": torch.from_numpy(self.targets[k][first + horizon:stop + horizon]),
                "current": torch.from_numpy(self.targets[k][first:stop]),
                "loss_weight": torch.from_numpy(loss_weight), "block": k, "first": first}
