"""
Windows of blocks at the window settings, the scaler fitted on train only, a torch Dataset of inputs and future positions, and the leakage assertion.
"""

import numpy as np
import torch

from .blocks import BlockEngine

# The columns a network may be given (AGENTS.md rule 1), the experiment's config choosing among them: position, speed
# (derived from position), and the measured head signals heading and turn rate. Never phase, trip, run, path, clean or
# anything else that labels axis of travel. Position only is the default and the control.
ALLOWED_INPUTS = ("x", "y", "speed", "heading", "turn_rate")
DEFAULT_INPUTS = ("x", "y")
TARGETS = ("x", "y")  # the future position, scaled as the position inputs are

# The one angle input is given as two feature columns, its sine and cosine, so heading in the config is two inputs of the
# network. A frame without a heading gives NaN in both and the window holding it is dropped and counted.
HEADING = "heading"
HEADING_FEATURES = ("heading_sin", "heading_cos")

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


def layout(columns):
    """
    The feature columns the network sees for these input columns, heading becoming heading_sin and heading_cos.
    """
    names = []
    for name in columns:
        names.extend(HEADING_FEATURES if name == HEADING else (name,))
    return tuple(names)


def fit_scaler(train_blocks, columns):
    """
    The mean and sd of each column but heading over the finite frames of the training blocks only, as plain numbers.
    """
    scaler = {}
    for name in columns:
        if name == HEADING:  # sine and cosine are already within -1 and 1, so heading is not scaled
            continue
        values = np.concatenate([block["arrays"][name] for block in train_blocks]).astype(np.float64)
        values = values[np.isfinite(values)]
        scaler[name] = {"mean": float(values.mean()), "sd": float(max(values.std(), MIN_SD))}
    return scaler


def scaled(block, columns, scaler):
    """
    The feature columns of a block side by side (T, n) float32, position, speed and turn rate standardised by the scaler and heading as its sine and cosine, unscaled.
    """
    features = []
    for name in columns:
        values = block["arrays"][name]
        if name == HEADING:
            features += [np.sin(values), np.cos(values)]
        else:
            features.append((values - scaler[name]["mean"]) / scaler[name]["sd"])
    return np.column_stack(features).astype(np.float32)


def standardise(a):
    """
    The columns of a with mean 0 and sd 1, a constant column left at 0.
    """
    a = a.astype(np.float64)
    return (a - a.mean(axis=0)) / np.maximum(a.std(axis=0), MIN_SD)


def assert_no_leakage(x, heading, columns):
    """
    Fails unless every input column is allowed, x has exactly their feature columns and none of them but heading's own sine and cosine is a folded heading.
    """
    assert set(columns) <= set(ALLOWED_INPUTS), f"inputs {sorted(set(columns) - set(ALLOWED_INPUTS))} are not allowed"
    names = layout(columns)
    assert x.shape[1] == len(names), x.shape
    others = [i for i, name in enumerate(names) if name not in HEADING_FEATURES]  # the sine and cosine are the allowed heading
    keep = np.isfinite(heading) & np.isfinite(x).all(axis=1)
    if not others or keep.sum() < 2:
        return
    folded = np.column_stack([np.mod(heading[keep], np.pi), np.cos(2 * heading[keep]), np.sin(2 * heading[keep])])
    correlation = np.abs(standardise(x[keep][:, others]).T @ standardise(folded)) / keep.sum()
    column = names[others[int(np.argmax(correlation.max(axis=1)))]]
    assert correlation.max() <= LEAKAGE_CORRELATION, f"{column} is a folded heading: {correlation.max():.4f}"


# An item is x (window, n_in) the inputs, n_in being len(layout), y (window, 2) the scaled position horizon steps ahead of
# each step, current (window, 2) the scaled position at each step for the persistence baseline, loss_weight (window,) 0
# in the burn in, block (index into blocks) and first (the window's first frame).
class WindowDataset(torch.utils.data.Dataset):
    """
    The windows of these blocks as tensors, a window whose inputs or targets are not all finite left out and counted.
    """

    def __init__(self, blocks, windows, columns, scaler):
        self.blocks, self.columns = blocks, tuple(columns)
        self.layout = layout(self.columns)  # the network's input width is len(self.layout)
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
