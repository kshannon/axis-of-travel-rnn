"""
A built blocks folder read for training: the folder by blueprint name, its manifest and data id, the blocks, the read only guard, the split by date and the resampling to the training rate.
"""

import json
from pathlib import Path

import numpy as np

from proj_helpers.paths import local_config, repo_root

from .blocks import io

# The configs/local.yaml key of the folder the builds go under, and the three data roots this package never writes to.
PROCESSED_KEY = "PROCESSED_LAB_DATA"
DATA_ROOT_KEYS = (PROCESSED_KEY, "TRANSFORMED_LAB_DATA", "LAB_DATA")
MANIFEST = "manifest.json"

# The three splits in the order fractions are given, and the most a resampled step may differ from one training step
# (the lab's frame is 0.016667 s, so three of them are 0.05 s only to this precision).
SPLITS = ("train", "validation", "test")
T_STEP_TOLERANCE_S = 1e-4


class LabDataError(Exception):
    """
    A built folder that is missing, a split that cannot be made, or a write that would touch the data.
    """


def built_folder(name, config=None):
    """
    The built folder PROCESSED_LAB_DATA/<name>/ of a blueprint, refused when it has no manifest.
    """
    config = local_config() if config is None else config
    if not config.get(PROCESSED_KEY):
        raise LabDataError(f"{PROCESSED_KEY} is missing from configs/local.yaml")
    folder = Path(str(config[PROCESSED_KEY])).expanduser() / name
    if not (folder / MANIFEST).is_file():
        raise LabDataError(f"no {MANIFEST} in {folder}, build it with pixi run build-blocks --blueprint {name}")
    return folder


def manifest(folder):
    """
    The manifest of a built folder as a dict.
    """
    return json.loads((Path(folder) / MANIFEST).read_text())


def data_id(folder):
    """
    The data id the build wrote into the manifest, the sha256 over blocks.csv and every block parquet.
    """
    return manifest(folder)["data_id"]


def block_rows(folder):
    """
    The rows of blocks.csv, one per block, sorted by session.
    """
    return io.blocks(folder)


def read_block(folder, row):
    """
    A block as its row, its arrays at the lab rate, and the rules and start offset its session was built with.
    """
    meta = io.metadata(folder, row["session_id"])
    return {**io.block(folder, row["block_id"]), "rules": meta["rules"], "start_offset_m": meta["start_offset_m"]}


def overlaps(a, b):
    """
    Whether folder a is b, is inside b or contains b.
    """
    a, b = Path(a).expanduser().resolve(), Path(b).expanduser().resolve()
    return a == b or b in a.parents or a in b.parents


def guard(path, config):
    """
    The folder a run writes to, refused when it overlaps a data root of the config or lies in the repository.
    """
    for key in DATA_ROOT_KEYS:
        if config.get(key) and overlaps(path, config[key]):
            raise LabDataError(f"{path} overlaps {key} {config[key]}, which is never written to")
    if overlaps(path, repo_root()):
        raise LabDataError(f"{path} overlaps the repository {repo_root()}, checkpoints stay outside git")
    return Path(path)


def split_by_date(rows, fractions, seed):
    """
    {session_id: split} with every session of a recording date in one split, the dates shuffled by the seed and cut by the train, validation and test fractions.
    """
    dates = sorted({row["date"] for row in rows})
    order = [dates[i] for i in np.random.default_rng(seed).permutation(len(dates))]
    n_validation, n_test = round(fractions[1] * len(dates)), round(fractions[2] * len(dates))
    sizes = (len(dates) - n_validation - n_test, n_validation, n_test)
    if any(size == 0 and fraction > 0 for size, fraction in zip(sizes, fractions)):
        raise LabDataError(f"{len(dates)} recording dates cannot be split by {tuple(fractions)}")
    by_date = {date: split for split, size, start in zip(SPLITS, sizes, np.cumsum((0,) + sizes))
               for date in order[start:start + size]}
    return {row["session_id"]: by_date[row["date"]] for row in rows}


def resample(block, rate_hz):
    """
    The block at rate_hz by taking every k-th frame (k the lab rate over rate_hz, a whole number), as lab_rnn did, its row's rate, frame count and duration updated.
    """
    row = block["row"]
    k, remainder = divmod(row["rate_hz"], rate_hz)
    if remainder:
        raise LabDataError(f"{row['block_id']}: {row['rate_hz']} Hz is not a whole multiple of {rate_hz} Hz")
    arrays = {name: values[::k] for name, values in block["arrays"].items()}
    if len(arrays["t"]) > 1 and np.abs(np.diff(arrays["t"]) - 1 / rate_hz).max() > T_STEP_TOLERANCE_S:
        raise LabDataError(f"{row['block_id']}: a resampled step is not {1 / rate_hz} s")
    n_frames = len(arrays["t"])
    return {**block, "row": {**row, "rate_hz": rate_hz, "n_frames": n_frames, "duration_s": n_frames / rate_hz},
            "arrays": arrays}
