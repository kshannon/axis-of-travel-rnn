"""
RatReplay's blocks as pilot sessions: the read-only guard, reading and checking, the split, the data id and the copies.
"""

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from pilot.worlds import SessionData
from proj_helpers.paths import local_config

from . import place
from .config import DATA_KEYS, DATA_ROOT_KEYS, PROCESSED_KEY, RATE_HZ, RUNS_KEY

# blocks/<block_id>.parquet, columns in order (outgoing_data_schema.txt, format version 3)
COLUMNS = ("frame", "t", "x", "y", "heading", "speed", "turn_rate", "n_lights", "heading_filled", "heading_held",
           "filled_front", "filled_back", "phase", "trip", "run", "path_id", "clean")
KEPT_STATUS = ("confirmed", "edited")
SPLITS = ("train", "val", "test")
T_STEP_TOLERANCE_S = 1e-4  # a resampled step may differ from dt by this much (the lab's frame is 0.016667 s)


class LabDataError(Exception):
    pass


@dataclass
class LabSession(SessionData):
    block_id: str = ""
    session_id: str = ""
    split: str = ""  # train, val or test, the split of its recording session; pilot.dataset.select_sessions reads it

    @classmethod
    def load(cls, path):
        """
        The session copy written by save.
        """
        with np.load(path) as z:
            fields = {key: z[key] for key in z.files}
        for key in ("world", "block_id", "session_id", "split"):
            fields[key] = str(fields[key])
        fields["seed"] = int(fields["seed"])
        return cls(**fields)


# ---------------------------------------------------------------------------
# paths and the read-only guard
# ---------------------------------------------------------------------------

def overlaps(a, b):
    """
    Whether folder a is b, is inside b or contains b.
    """
    a, b = Path(a).resolve(), Path(b).resolve()
    return a == b or b in a.parents or a in b.parents


def lab_paths(config=None):
    """
    The processed folder and the runs folder, refused when the runs folder overlaps any data root.
    """
    config = local_config() if config is None else config
    for key in (PROCESSED_KEY, RUNS_KEY):
        if not config.get(key):
            raise LabDataError(f"{key} is missing from configs/local.yaml")
    processed, runs = Path(config[PROCESSED_KEY]), Path(config[RUNS_KEY])
    for key in DATA_ROOT_KEYS:
        if config.get(key) and overlaps(runs, config[key]):
            raise LabDataError(f"{RUNS_KEY} {runs} overlaps {key} {config[key]}, which is never written to")
    if not (processed / "blocks.csv").is_file():
        raise LabDataError(f"no blocks.csv in {processed}")
    return processed, runs


# ---------------------------------------------------------------------------
# the index, the split and the data id
# ---------------------------------------------------------------------------

def read_index(processed, cfg):
    """
    The rows of blocks.csv with a kept status and a world of the preset, as dicts of strings.
    """
    with open(processed / "blocks.csv", newline="") as f:
        return [row for row in csv.DictReader(f) if row["status"] in KEPT_STATUS and row["kind"] in cfg["worlds"]]


def split_by_date(rows, cfg):
    """
    {session_id: split} for the first n_train + n_val + n_test sessions in date order; later sessions are left out.
    """
    sessions = sorted({(row["date"], row["session_id"]) for row in rows})
    sizes = [cfg["n_train"], cfg["n_val"], cfg["n_test"]]
    if len(sessions) < sum(sizes):
        raise LabDataError(f"{len(sessions)} sessions for a split of {sizes}")
    labels = [split for split, size in zip(SPLITS, sizes) for _ in range(size)]
    return {session_id: label for (_, session_id), label in zip(sessions, labels)}


def sha256_of(path):
    """
    The sha256 of a file's bytes, read in binary mode.
    """
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def data_id(processed, rows, split, cfg):
    """
    The first 8 hex digits of a hash of blocks.csv, every block used, the split and the preset's DATA_KEYS.
    """
    digest = hashlib.sha256(sha256_of(processed / "blocks.csv").encode())
    for row in rows:
        digest.update(f"{row['block_id']}:{sha256_of(block_path(processed, row['block_id']))}".encode())
    digest.update(json.dumps({"split": split, **{key: cfg[key] for key in DATA_KEYS}}, sort_keys=True).encode())
    return digest.hexdigest()[:8]


def block_path(processed, block_id):
    """
    Where RatReplay writes a block.
    """
    return processed / "blocks" / f"{block_id}.parquet"


# ---------------------------------------------------------------------------
# blocks to sessions
# ---------------------------------------------------------------------------

def read_block(processed, row, split, cfg):
    """
    A LabSession of every resample-th frame of a block, its place cells still empty; a block off the schema raises.
    """
    table = pq.read_table(block_path(processed, row["block_id"]))
    if tuple(table.column_names) != COLUMNS:
        raise LabDataError(f"{row['block_id']}: columns {table.column_names} are not the schema's {list(COLUMNS)}")
    column = lambda name: table[name].to_numpy()[::cfg["resample"]].astype(np.float64)
    t = column("t")
    assert cfg["resample"] / RATE_HZ == cfg["dt"], (cfg["resample"], cfg["dt"])
    if np.abs(np.diff(t) - cfg["dt"]).max() > T_STEP_TOLERANCE_S:
        raise LabDataError(f"{row['block_id']}: a resampled step is not {cfg['dt']} s")
    seed = int(hashlib.sha256(row["block_id"].encode()).hexdigest()[:8], 16)
    return LabSession(world=row["kind"], seed=seed, t=t, pos=np.column_stack([column("x"), column("y")]),
                      heading=column("heading"), speed=column("speed"),
                      turn_rate=np.full(len(t), np.nan),  # the lab's turn rate comes from heading: never an input
                      place=np.zeros((len(t), 0), np.float32), hd=np.zeros((len(t), 0), np.float32),
                      block_id=row["block_id"], session_id=row["session_id"], split=split[row["session_id"]])


def by_world(sessions, cfg):
    """
    {world: [LabSession]} ordered by split, then block id (which starts with the session id).
    """
    order = lambda s: (SPLITS.index(s.split), s.block_id)
    return {world: sorted((s for s in sessions if s.world == world), key=order) for world in cfg["worlds"]}


def build(processed, rows, split, cfg):
    """
    The sessions of these blocks with their place cells, and the centres drawn per world from the train sessions.
    """
    sessions = [read_block(processed, row, split, cfg) for row in rows]
    centres = {}
    for world in cfg["worlds"]:
        train = np.concatenate([s.pos for s in sessions if s.world == world and s.split == "train"])
        centres[world] = place.draw_centres(train, cfg["place_n"], cfg["layout_seed"][world])
    for s in sessions:
        s.place = place.rates(s.pos, centres[s.world], cfg["place_width"])
    return by_world(sessions, cfg), centres


# ---------------------------------------------------------------------------
# the copies: the sessions as the networks read them, kept beside the runs
# ---------------------------------------------------------------------------

def write_json(path, value):
    """
    Write a JSON file through a part file, so an interrupted write is never read.
    """
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(value, indent=2))
    part.replace(path)


def write_copies(folder, sessions, centres, cfg, processed, rows):
    """
    Write every session, the layouts and then blocks.json, which marks the copies as complete.
    """
    for world_sessions in sessions.values():
        for s in world_sessions:
            path = folder / "sessions" / f"{s.block_id}.npz"
            if not path.exists():  # a copy is never rewritten; one from an interrupted first load has the same data
                s.save(path)
    part = folder / "layouts.npz.part"
    with open(part, "wb") as f:
        np.savez_compressed(f, **{f"centres_{world}": c for world, c in centres.items()},
                            **{f"layout_seed_{world}": cfg["layout_seed"][world] for world in centres})
    part.replace(folder / "layouts.npz")
    hashes = {row["block_id"]: sha256_of(block_path(processed, row["block_id"])) for row in rows}
    write_json(folder / "blocks.json", {
        "data_id": cfg["data_id"], "processed_lab_data": str(processed),
        "blocks_csv_sha256": sha256_of(processed / "blocks.csv"),
        "blocks": [{"block_id": s.block_id, "session_id": s.session_id, "world": s.world, "split": s.split,
                    "seed": s.seed, "sha256": hashes[s.block_id]} for w in sessions.values() for s in w]})


def load_copies(folder, cfg):
    """
    {world: [LabSession]} from a folder's copies alone, in the order blocks.json lists them.
    """
    listed = json.loads((Path(folder) / "blocks.json").read_text())["blocks"]
    sessions = [LabSession.load(Path(folder) / "sessions" / f"{b['block_id']}.npz") for b in listed]
    return {world: [s for s in sessions if s.world == world] for world in cfg["worlds"]}


def load(cfg, config=None):
    """
    The sessions of the preset and the preset with its runs_dir and data_id: the copies when they exist, else built.
    """
    processed, runs = lab_paths(config)
    rows = read_index(processed, cfg)
    split = split_by_date(rows, cfg)
    rows = sorted((row for row in rows if row["session_id"] in split), key=lambda row: row["block_id"])
    # the id covers the bytes of every block used, so a block RatReplay rewrites gets a new folder and the old copies
    # and runs stay as they were
    cfg = {**cfg, "runs_dir": str(runs), "data_id": data_id(processed, rows, split, cfg)}
    folder = runs / f"{cfg['name']}_{cfg['data_id']}"
    if (folder / "blocks.json").exists():
        return load_copies(folder, cfg), cfg
    sessions, centres = build(processed, rows, split, cfg)
    folder.mkdir(parents=True, exist_ok=True)
    write_copies(folder, sessions, centres, cfg, processed, rows)
    return load_copies(folder, cfg), cfg


# ---------------------------------------------------------------------------
# the sweep's summary files
# ---------------------------------------------------------------------------

def write_summary(cfg, persistence, checks, thresholds_sha256):
    """
    baselines.json and checks.json beside the runs; a file that exists with other contents is never overwritten.
    """
    folder = Path(cfg["runs_dir"]) / f"{cfg['name']}_{cfg['data_id']}"
    files = {"baselines.json": persistence,
             "checks.json": {"thresholds_sha256": thresholds_sha256,
                             "checks": [{"name": name, "passed": bool(passed), "numbers": numbers}
                                        for name, passed, numbers in checks]}}
    for name, value in files.items():
        path = folder / name
        if path.exists():
            if json.loads(path.read_text()) != json.loads(json.dumps(value)):
                raise LabDataError(f"{path} exists with other contents")
            continue
        write_json(path, value)
