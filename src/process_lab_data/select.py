"""
The funnel: which sessions, epochs and blocks of the transformed lab data survive, with the count after each step.
"""

from pathlib import Path

import numpy as np
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

# The spec's Selection: sessions of this protocol, outside these groups and not excluded by hand, then their epochs
# of these kinds under this condition.
PROTOCOL = "standard"
CONDITION = "baseline"
EPOCHS = ("arena", "track")
EXCLUDED_GROUPS = ("JL1HPCData",)

# The block cuts (spec Overview): a step in t over this is a pause, as in the converter, and a stretch with the lights
# unfilled for more than the session's max_gap frames is a tracking gap. GAP_LIGHTS says which lights: "either" cuts
# when one light is lost (position from the average light), "both" only when both are (position from the lab's
# mashup light, the one good light when the other is lost). A block shorter than MIN_BLOCK_S is dropped.
PAUSE_STEP_S = 0.1
GAP_LIGHTS = "both"
MIN_BLOCK_S = 10.0

# The converter's tables (tables.md 2) and the folder of frames files, all required, and the two files made by hand,
# each optional.
TABLES = ("sessions", "epochs", "runs")
FRAMES = "frames"
ANNOTATIONS = "annotations.csv"
VERDICTS = "verdicts.csv"


def read_csv(path):
    """
    A csv file as a list of dicts, one per row, with blanks as None.
    """
    return pacsv.read_csv(path).to_pylist()


def read_tables(root):
    """
    The three tables plus annotations and verdicts (empty when the file is absent), each a list of row dicts.
    """
    root = Path(root)
    tables = {name: read_csv(root / f"{name}.csv") for name in TABLES}
    for name, file in (("annotations", ANNOTATIONS), ("verdicts", VERDICTS)):
        tables[name] = read_csv(root / file) if (root / file).is_file() else []
    return tables


def matches(session_id, only):
    """
    Whether a session id is PREFIX or continues it after an underscore, and always when there is no PREFIX.
    """
    return only is None or session_id == only or session_id.startswith(only + "_")


def funnel(tables, only):
    """
    Apply the Selection steps in order and return the surviving epochs and the (step, count) list the steps produce.
    """
    excluded = {row["session_id"] for row in tables["annotations"] if row.get("exclude")}
    session_steps = (
        ("all sessions", lambda s: True),
        (f"protocol {PROTOCOL}", lambda s: s["protocol"] == PROTOCOL),
        ("group allowed", lambda s: s["group"] not in EXCLUDED_GROUPS),
        ("not excluded by annotations", lambda s: s["session_id"] not in excluded),
        ("--only", lambda s: matches(s["session_id"], only)),
    )
    counts = []
    sessions = tables["sessions"]
    for step, keep in session_steps:
        sessions = [s for s in sessions if keep(s)]
        counts.append((f"sessions, {step}", len(sessions)))
    kept = {s["session_id"] for s in sessions}
    epoch_steps = (
        ("of those sessions", lambda e: e["session_id"] in kept),
        ("kind " + " or ".join(EPOCHS), lambda e: e["epoch"] in EPOCHS),
        (f"condition {CONDITION}", lambda e: e["condition"] == CONDITION),
    )
    epochs = tables["epochs"]
    for step, keep in epoch_steps:
        epochs = [e for e in epochs if keep(e)]
        counts.append((f"epochs, {step}", len(epochs)))
    tracks = {(e["session_id"], e["epoch"]) for e in epochs if e["epoch"] == "track"}
    runs = [r for r in tables["runs"] if (r["session_id"], r["epoch"]) in tracks]
    counts.append(("runs, of surviving track epochs", len(runs)))
    counts.append(("runs, clean", sum(1 for r in runs if r["clean"])))
    return epochs, counts


def read_frames(root, session_id):
    """
    The session's frames file (tables.md 2.4) as a dict of column name to numpy array.
    """
    table = pq.read_table(Path(root) / FRAMES / f"{session_id}.parquet")
    return {name: table.column(name).to_numpy() for name in table.column_names}


def long_unfilled(unfilled, max_gap):
    """
    True on every frame of an unfilled stretch longer than max_gap frames.
    """
    edges = np.flatnonzero(np.diff(np.concatenate(([False], unfilled, [False])).astype(np.int8)))
    gap = np.zeros(len(unfilled), bool)
    for first, stop in zip(edges[::2], edges[1::2]):
        if stop - first > max_gap:
            gap[first:stop] = True
    return gap


def cut_at(frames, epoch, max_gap):
    """
    The stretches of the epoch between its pauses, long unfilled stretches and bounds, as 1-based inclusive frame pairs.
    """
    frame = frames["frame"]
    pause = np.concatenate(([False], np.diff(frames["t"]) > PAUSE_STEP_S))
    kept = (frame >= epoch["frame_start"]) & (frame <= epoch["frame_end"])
    lost = {"either": np.logical_or, "both": np.logical_and}[GAP_LIGHTS](frames["unfilled_front"], frames["unfilled_back"])
    kept &= ~long_unfilled(lost, max_gap)
    before = np.concatenate(([False], kept[:-1]))
    after = np.concatenate((kept[1:], [False]))
    starts = kept & (~before | pause)
    ends = kept & (~after | np.concatenate((pause[1:], [False])))
    return list(zip(frame[starts].tolist(), frame[ends].tolist()))


def long_enough(block, rate_hz):
    """
    Whether a (frame_start, frame_end) block lasts at least MIN_BLOCK_S.
    """
    return block[1] - block[0] + 1 >= MIN_BLOCK_S * rate_hz


def cut_blocks(frames, epoch, max_gap, rate_hz):
    """
    The epoch's blocks: cut_at with the short stretches dropped.
    """
    return [block for block in cut_at(frames, epoch, max_gap) if long_enough(block, rate_hz)]


def blocks_of(source, epochs, sessions):
    """
    The blocks of the surviving epochs, reading each session's frames once, and the (step, count) list to append to the funnel.
    """
    by_id = {s["session_id"]: s for s in sessions}
    blocks, n_cut = [], 0
    for session_id in dict.fromkeys(e["session_id"] for e in epochs):
        session, frames = by_id[session_id], read_frames(source, session_id)
        for e in [e for e in epochs if e["session_id"] == session_id]:
            cut = cut_at(frames, e, session["max_gap"])
            n_cut += len(cut)
            kept = [block for block in cut if long_enough(block, session["rate_hz"])]
            for i, (frame_start, frame_end) in enumerate(kept, 1):
                n_frames = frame_end - frame_start + 1
                blocks.append({
                    "block_id": f"{session_id}_{e['epoch']}_{i:02d}", "session_id": session_id, "epoch": e["epoch"],
                    "environment": e["environment"], "frame_start": frame_start, "frame_end": frame_end,
                    "n_frames": n_frames, "duration_s": n_frames / session["rate_hz"],
                })
    counts = [("blocks, cut at pauses and gaps", n_cut), (f"blocks, at least {MIN_BLOCK_S:g} s", len(blocks))]
    counts += [(f"blocks, kind {kind}", sum(1 for b in blocks if b["epoch"] == kind)) for kind in EPOCHS]
    return blocks, counts
