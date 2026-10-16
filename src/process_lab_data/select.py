"""
The funnel: which sessions, epochs and blocks of the transformed lab data survive, with the count after each step.
"""

from collections import Counter
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

# The block cuts (spec Selection). A step in t over PAUSE_STEP_S is a pause, as in the converter. A stretch with the
# lights unfilled for more than the session's max_gap frames is a tracking gap, GAP_LIGHTS saying which lights:
# "either" cuts when one light is lost (position from the average light), "both" only when both are (position from
# the lab's mashup light, the one good light when the other is lost). A mashup position moving over JUMP_PX in one
# normal step is a jump, a tracking teleport, and cuts like a pause. PAUSE_MARGIN_SEC is trimmed inward from every
# stretch edge with a pause, a jump or an epoch bound between it and the next stretch, where the rat was handled,
# even when a gap holds the pause or the bound, but not at a gap alone. A block shorter than MIN_BLOCK_S is dropped.
# Heading gaps up to HEADING_FILL_SEC with no pause inside are filled along the shortest arc (kind INTERPOLATED). A
# longer gap with no pause inside during which the rat stays still on every frame (the mashup speed, the steps across
# a light switch left out, under RUNNING_FLOOR_M_PER_S, the paper's running floor, at the epoch's LED scale,
# frame.still, the head in a reward well) is filled by holding the last heading before it (kind HELD). Any other gap stays NaN (kind UNTOUCHED). The same floor
# makes a pause label inside a run (labels.py).
PAUSE_STEP_S = 0.1
GAP_LIGHTS = "both"
JUMP_PX = 40.0
PAUSE_MARGIN_SEC = 5.0
MIN_BLOCK_S = 10.0
HEADING_FILL_SEC = 3.0
RUNNING_FLOOR_M_PER_S = 0.03
UNTOUCHED, INTERPOLATED, HELD = 0, 1, 2

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


def runs_of(mask):
    """
    The (first, stop) index pairs of every stretch where the mask is true.
    """
    edges = np.flatnonzero(np.diff(np.concatenate(([False], mask, [False])).astype(np.int8)))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


def spans(frame, mask):
    """
    The (first, last) 1-based frame pairs of every stretch where the mask is true.
    """
    return [(int(frame[first]), int(frame[stop - 1])) for first, stop in runs_of(mask)]


def long_unfilled(unfilled, max_gap):
    """
    True on every frame of an unfilled stretch longer than max_gap frames.
    """
    gap = np.zeros(len(unfilled), bool)
    for first, stop in runs_of(unfilled):
        if stop - first > max_gap:
            gap[first:stop] = True
    return gap


def pauses(frames):
    """
    True on the first frame after a step in t over PAUSE_STEP_S.
    """
    return np.concatenate(([False], np.diff(frames["t"]) > PAUSE_STEP_S))


def jumps(frames):
    """
    True on the frame whose mashup position moved over JUMP_PX from the frame before within one normal step, never across a pause or a lost position.
    """
    step = np.hypot(np.diff(frames["mashup_x"]), np.diff(frames["mashup_y"]))
    return np.concatenate(([False], (step > JUMP_PX) & (np.diff(frames["t"]) <= PAUSE_STEP_S)))


def gaps(frames, max_gap):
    """
    True on every frame of a stretch with the GAP_LIGHTS lights unfilled for more than max_gap frames.
    """
    lost = {"either": np.logical_or, "both": np.logical_and}[GAP_LIGHTS](frames["unfilled_front"], frames["unfilled_back"])
    return long_unfilled(lost, max_gap)


def inside(frames, epoch):
    """
    True on the frames of the epoch.
    """
    return (frames["frame"] >= epoch["frame_start"]) & (frames["frame"] <= epoch["frame_end"])


def handled(cut, first, last):
    """
    Whether a cut lies between each stretch and the one before it, and the one after it, the epoch bounds counting as cuts.
    """
    between = [bool(cut[a + 1:b + 1].any()) for a, b in zip(last[:-1], first[1:])]
    return np.array([True] + between, bool), np.array(between + [True], bool)


def stretches(frames, epoch, max_gap, rate_hz):
    """
    The epoch's stretches as four index arrays, first and last before the margins then after, a vanished stretch having first over last.
    """
    cut = pauses(frames) | jumps(frames)
    cut_next = np.concatenate((cut[1:], [False]))
    kept = inside(frames, epoch) & ~gaps(frames, max_gap)
    before = np.concatenate(([False], kept[:-1]))
    after = np.concatenate((kept[1:], [False]))
    first = np.flatnonzero(kept & (~before | cut))
    last = np.flatnonzero(kept & (~after | cut_next))
    margin = round(PAUSE_MARGIN_SEC * rate_hz)
    handled_first, handled_last = handled(cut, first, last)
    return first, last, first + margin * handled_first, last - margin * handled_last


def cut_at(frames, epoch, max_gap, rate_hz):
    """
    The epoch's stretches between its pauses, jumps, long gaps and bounds with the margins trimmed, as 1-based inclusive frame pairs.
    """
    _, _, first, last = stretches(frames, epoch, max_gap, rate_hz)
    kept = first <= last
    frame = frames["frame"]
    return list(zip(frame[first[kept]].tolist(), frame[last[kept]].tolist()))


def cut_points(frames, epoch, max_gap, rate_hz):
    """
    What cut the epoch, for drawing: its pause and jump frames, its gap spans and the margins trimmed, as 1-based frames.
    """
    frame, here = frames["frame"], inside(frames, epoch)
    margins = []
    for first, last, trimmed_first, trimmed_last in zip(*stretches(frames, epoch, max_gap, rate_hz)):
        if trimmed_first > trimmed_last:
            margins.append((int(frame[first]), int(frame[last])))
            continue
        if trimmed_first > first:
            margins.append((int(frame[first]), int(frame[trimmed_first - 1])))
        if trimmed_last < last:
            margins.append((int(frame[trimmed_last + 1]), int(frame[last])))
    return {"pauses": frame[pauses(frames) & here].tolist(), "jumps": frame[jumps(frames) & here].tolist(),
            "gaps": spans(frame, gaps(frames, max_gap) & here), "margins": margins}


def fill_heading(heading, t, still, rate_hz):
    """
    Heading with its NaN gaps free of pauses filled, up to HEADING_FILL_SEC along the shortest arc between the ends and longer ones by the last heading when the rat is still throughout, and the kind of fill per frame, UNTOUCHED, INTERPOLATED or HELD.
    """
    filled, kind = heading.copy(), np.zeros(len(heading), np.int8)
    pause = np.concatenate(([False], np.diff(t) > PAUSE_STEP_S))
    longest = round(HEADING_FILL_SEC * rate_hz)
    for first, stop in runs_of(np.isnan(heading)):
        if first == 0 or stop == len(heading) or pause[first:stop + 1].any():
            continue
        start = heading[first - 1]
        if stop - first > longest:
            if still[first:stop].all():
                filled[first:stop], kind[first:stop] = start, HELD
            continue
        turn = (heading[stop] - start + np.pi) % (2 * np.pi) - np.pi
        fraction = np.arange(1, stop - first + 1) / (stop - first + 1)
        filled[first:stop] = (start + turn * fraction + np.pi) % (2 * np.pi) - np.pi
        kind[first:stop] = INTERPOLATED
    return filled, kind


def long_enough(block, rate_hz):
    """
    Whether a (frame_start, frame_end) block lasts at least MIN_BLOCK_S.
    """
    return block[1] - block[0] + 1 >= MIN_BLOCK_S * rate_hz


def cut_blocks(frames, epoch, max_gap, rate_hz):
    """
    The epoch's blocks: cut_at with the short stretches dropped.
    """
    return [block for block in cut_at(frames, epoch, max_gap, rate_hz) if long_enough(block, rate_hz)]


def blocks_in(frames, session, epochs):
    """
    The blocks of the session's epochs from its frames, and the tally the funnel counts: stretches cut, stretches left after the margins, jump frames and seconds trimmed.
    """
    session_id, rate_hz, max_gap = session["session_id"], session["rate_hz"], session["max_gap"]
    blocks, tally = [], Counter()
    for e in epochs:
        first, last, trimmed_first, trimmed_last = stretches(frames, e, max_gap, rate_hz)
        tally.update({"cut": len(first), "after_margins": int((trimmed_first <= trimmed_last).sum()),
                      "jump_frames": int((jumps(frames) & inside(frames, e)).sum()),
                      "trimmed_s": float(((last - first + 1) - np.maximum(trimmed_last - trimmed_first + 1, 0)).sum()) / rate_hz})
        for i, (frame_start, frame_end) in enumerate(cut_blocks(frames, e, max_gap, rate_hz), 1):
            n_frames = frame_end - frame_start + 1
            blocks.append({
                "block_id": f"{session_id}_{e['epoch']}_{i:02d}", "session_id": session_id, "epoch": e["epoch"],
                "environment": e["environment"], "frame_start": frame_start, "frame_end": frame_end,
                "n_frames": n_frames, "duration_s": n_frames / rate_hz,
            })
    return blocks, tally


def block_counts(blocks, tally):
    """
    The (step, count) list to append to the funnel from the blocks and the summed tally of blocks_in.
    """
    counts = [("blocks, cut at pauses, gaps and jumps", tally["cut"]), ("blocks, after margins", tally["after_margins"]),
              (f"blocks, at least {MIN_BLOCK_S:g} s", len(blocks))]
    counts += [(f"blocks, kind {kind}", sum(1 for b in blocks if b["epoch"] == kind)) for kind in EPOCHS]
    counts += [("jump frames, in the epochs", tally["jump_frames"]), ("seconds trimmed by margins", round(tally["trimmed_s"], 1))]
    return counts


def blocks_of(source, epochs, sessions):
    """
    The blocks of the surviving epochs, reading each session's frames once, and the (step, count) list to append to the funnel.
    """
    by_id = {s["session_id"]: s for s in sessions}
    blocks, tally = [], Counter()
    for session_id in dict.fromkeys(e["session_id"] for e in epochs):
        found, counted = blocks_in(read_frames(source, session_id), by_id[session_id], [e for e in epochs if e["session_id"] == session_id])
        blocks += found
        tally += counted
    return blocks, block_counts(blocks, tally)
