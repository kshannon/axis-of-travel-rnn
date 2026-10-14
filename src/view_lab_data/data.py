"""
Data access for the viewer: blocks and runs from either source, one block's arrays as JSON-ready lists, the verdicts file.
"""

import csv
import getpass
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

# Both sources run at the camera's rate. The processed blocks (docs/process_lab_data/spec.md) live in one folder per
# epoch kind, the converter's frames (docs/transform_lab_data/tables.md 2) in one file per session.
RATE_HZ = 60
KINDS = ("track", "arena")
BLOCK_ARRAYS = ("t", "x", "y", "heading", "speed", "phase")
RUN_COLUMNS = ("run", "path_id", "clean")
MANIFEST = "manifest.json"

# The transformed position shown is the lab's mashup light, defined whenever at least one light is present. Speed and
# direction of motion are the position difference over dt, averaged over this many frames, the lab's window. The LED
# offset of a session is the circular mean of heading minus motion direction over frames faster than this, in px/s.
POSITION_COLUMNS = ("mashup_x", "mashup_y")
SPEED_SMOOTH_FRAMES = 6
RUNNING_SPEED = 20

# The verdicts file beside the data, one appended row per save, never edited. A tag marks a tracking or labelling
# problem, never a behaviour.
VERDICTS = "verdicts.csv"
VERDICT_COLUMNS = ("block_id", "session_id", "run", "tag", "comment", "saved_at", "who", "dataset_manifest_timestamp")
TAGS = ("fine", "tracking artifact", "run mislabelled", "unsure")


def read_csv(path):
    """
    A csv file as a list of dicts, one per row, with blanks as None.
    """
    return pacsv.read_csv(path).to_pylist()


def floats(column):
    """
    A float column as a list with NaN as None, so it survives JSON.
    """
    return [None if value != value else value for value in column.tolist()]


def manifest_timestamp(root, transformed):
    """
    The timestamp of the dataset's manifest: the converter writes it under run, the processor at the top level.
    """
    manifest = json.loads((Path(root) / MANIFEST).read_text())
    if transformed:
        return manifest["run"]["timestamp"]
    return manifest.get("timestamp", "")


def list_blocks(root, transformed):
    """
    Every block in order, each a dict with block_id, session_id, subject_id, date, group, epoch, environment,
    frame_start, frame_end, duration_s and n_runs, with the lab frame numbers 1-based as the tables carry them.
    The processed kinds are built separately, so a kind without its table is skipped.
    """
    root = Path(root)
    if transformed:
        return transformed_blocks(root)
    blocks = []
    for kind in KINDS:
        table = root / kind / "blocks.csv"
        if not table.is_file():
            continue
        for row in read_csv(table):
            blocks.append({**row, "date": str(row["date"]), "group": ""})
    return blocks


def transformed_blocks(root):
    """
    The arena and track epochs of every session as blocks, block_id = session_id_epoch, with the session's labels.
    """
    sessions = {row["session_id"]: row for row in read_csv(root / "sessions.csv")}
    runs = read_csv(root / "runs.csv")
    blocks = []
    for epoch in read_csv(root / "epochs.csv"):
        if epoch["epoch"] not in KINDS:
            continue
        session = sessions[epoch["session_id"]]
        n_runs = sum(1 for run in runs if run["session_id"] == epoch["session_id"] and run["epoch"] == epoch["epoch"])
        blocks.append({
            "block_id": f"{epoch['session_id']}_{epoch['epoch']}", "session_id": epoch["session_id"],
            "subject_id": session["subject_id"], "date": str(session["date"]), "group": session["group"],
            "epoch": epoch["epoch"], "environment": epoch["environment"],
            "frame_start": epoch["frame_start"], "frame_end": epoch["frame_end"],
            "duration_s": epoch["duration_s"], "n_runs": n_runs})
    return blocks


def list_runs(root, transformed, block):
    """
    The runs of a block in order, each a dict with run, path_id, clean, start and end (frame indices into the block's
    arrays, inclusive) and duration_s.
    """
    root = Path(root)
    if transformed:
        rows = [row for row in read_csv(root / "runs.csv")
                if row["session_id"] == block["session_id"] and row["epoch"] == block["epoch"]]
        spans = [(row["run"], row["path_id"], row["clean"], row["frame_start"] - block["frame_start"],
                  row["frame_end"] - block["frame_start"]) for row in rows]
    else:
        table = pq.read_table(block_file(root, block), columns=list(RUN_COLUMNS))
        spans = labelled_spans(table.column("run").to_pylist(), table.column("path_id").to_pylist(),
                               table.column("clean").to_pylist())
    last = block["frame_end"] - block["frame_start"]
    runs = []
    for run, path_id, clean, start, end in spans:
        start, end = max(start, 0), min(end, last)
        runs.append({"run": run, "path_id": path_id, "clean": bool(clean), "start": start, "end": end,
                     "duration_s": (end - start + 1) / RATE_HZ})
    return runs


def labelled_spans(labels, path_ids, cleans):
    """
    The (run, path_id, clean, start, end) of each stretch of frames carrying the same run label, label 0 or null being no run.
    """
    spans = []
    for index, label in enumerate(labels):
        if not label:
            continue
        if spans and spans[-1][0] == label:
            spans[-1][4] = index
        else:
            spans.append([label, path_ids[index], cleans[index], index, index])
    return [tuple(span) for span in spans]


def block_file(root, block):
    """
    The parquet file of a processed block.
    """
    return Path(root) / block["epoch"] / "blocks" / f"{block['block_id']}.parquet"


def load_block(root, transformed, block):
    """
    One block's arrays as lists ready for JSON (t, x, y, heading, motion, speed, phase) with its units, rate, whether
    the image y axis points down and the session's LED offset (None in the processed data, whose heading is corrected).
    """
    root = Path(root)
    if transformed:
        arrays = transformed_arrays(root, block)
    else:
        table = pq.read_table(block_file(root, block), columns=list(BLOCK_ARRAYS))
        t, x, y = (table.column(name).to_numpy() for name in ("t", "x", "y"))
        arrays = {name: floats(table.column(name).to_numpy()) for name in BLOCK_ARRAYS if name != "phase"}
        arrays.update(phase=table.column("phase").to_pylist(), motion=floats(motion_direction(t, x, y)), led_offset=None)
    return {**arrays, "units": "px" if transformed else "m", "y_down": transformed, "rate_hz": RATE_HZ}


def transformed_arrays(root, block):
    """
    The converter's frames of one epoch: the lab's mashup light in pixels, its heading, the speed and direction of
    motion from the positions, and the LED offset over the whole session the epoch belongs to.
    """
    table = pq.read_table(root / "frames" / f"{block['session_id']}.parquet", columns=["t", *POSITION_COLUMNS, "head_dir"])
    t, x, y, heading = (table.column(name).to_numpy() for name in ("t", *POSITION_COLUMNS, "head_dir"))
    speed, motion = speed_from_positions(t, x, y), motion_direction(t, x, y)
    s = slice(block["frame_start"] - 1, block["frame_end"])
    return {"t": floats(t[s]), "x": floats(x[s]), "y": floats(y[s]), "heading": floats(heading[s]),
            "motion": floats(motion[s]), "speed": floats(speed[s]), "phase": [""] * (s.stop - s.start),
            "led_offset": led_offset(heading, motion, speed)}


def smoothed(steps):
    """
    A per-step series as a per-frame series, the first frame repeating the second, averaged over SPEED_SMOOTH_FRAMES frames.
    """
    kernel = np.ones(SPEED_SMOOTH_FRAMES) / SPEED_SMOOTH_FRAMES
    return np.convolve(np.concatenate([steps[:1], steps]), kernel, mode="same")


def speed_from_positions(t, x, y):
    """
    The step length over dt, smoothed.
    """
    return smoothed(np.hypot(np.diff(x), np.diff(y)) / np.diff(t))


def motion_direction(t, x, y):
    """
    The direction of the smoothed velocity, atan2(dy, dx) in the data's own axes.
    """
    dt = np.diff(t)
    return np.arctan2(smoothed(np.diff(y) / dt), smoothed(np.diff(x) / dt))


def led_offset(heading, motion, speed):
    """
    The circular mean (rad) and concentration r of heading minus motion direction over running frames: the light bar's
    mounting angle on the head, r near 1 when the head follows travel. Both 0 when no frame is running.
    """
    running = (speed > RUNNING_SPEED) & np.isfinite(heading) & np.isfinite(motion)
    z = np.exp(1j * (heading[running] - motion[running])).sum() / max(running.sum(), 1)
    return {"rad": float(np.angle(z)), "r": float(np.abs(z))}


def latest_verdicts(root):
    """
    The latest verdict row per (block_id, run), run None for a whole block, empty when no verdict was saved yet.
    """
    path = Path(root) / VERDICTS
    if not path.is_file():
        return {}
    latest = {}
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            run = int(row["run"]) if row["run"] else None
            latest[(row["block_id"], run)] = {**row, "run": run}
    return latest


def append_verdict(root, block_id, session_id, run, tag, comment, dataset_manifest_timestamp):
    """
    Append one row to the verdicts file, writing the header when the file is new, run blank for a whole block.
    """
    path = Path(root) / VERDICTS
    new = not path.is_file()
    row = {"block_id": block_id, "session_id": session_id, "run": "" if run is None else run, "tag": tag,
           "comment": comment, "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "who": getpass.getuser(), "dataset_manifest_timestamp": dataset_manifest_timestamp}
    with path.open("a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=VERDICT_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow(row)
    return row
