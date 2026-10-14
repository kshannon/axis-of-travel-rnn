"""
Fixtures for the viewer tests: a synthetic processed folder and a synthetic transformed folder of one session.
"""

import json

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest

SESSION = "NS14_rec1_20150101_001"
RATE_HZ = 60

# A track epoch of 600 frames holding two runs, and an arena epoch of 300 frames, lab frame numbers 1-based.
TRACK = {"frame_start": 301, "frame_end": 900}
ARENA = {"frame_start": 1, "frame_end": 300}
RUNS = [{"run": 1, "path_id": 3, "clean": True, "frame_start": 400, "frame_end": 520},
        {"run": 2, "path_id": 7, "clean": False, "frame_start": 600, "frame_end": 700}]


def write_csv(path, rows):
    """
    Write a list of same-keyed dicts as a csv table.
    """
    pacsv.write_csv(pa.Table.from_pylist(rows), path)


def walk(n, seed, hole):
    """
    A random walk of n frames with a NaN hole of three frames starting at index hole, plus a random heading.
    """
    rng = np.random.default_rng(seed)
    x, y = np.cumsum(rng.normal(size=(2, n)), axis=1)
    x[hole:hole + 3] = np.nan
    return x, y, rng.uniform(-np.pi, np.pi, n)


@pytest.fixture
def transformed(tmp_path):
    """
    The converter's tables and frames of one session: the mashup light loses both lights for three frames at block
    index 10 of the track, the average light also loses one light for four frames at index 30.
    """
    root = tmp_path / "transformed"
    (root / "frames").mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"run": {"timestamp": "2026-10-13T10:00:00+00:00"}}))
    write_csv(root / "sessions.csv", [{"session_id": SESSION, "subject_id": "NS14", "group": "NS14Data",
                                       "date": "2015-01-01", "protocol": "standard", "rate_hz": RATE_HZ}])
    write_csv(root / "epochs.csv", [
        {"session_id": SESSION, "epoch": "arena", "environment": "open_arena", "condition": "baseline",
         **ARENA, "duration_s": 5.0},
        {"session_id": SESSION, "epoch": "track", "environment": "triple_t", "condition": "baseline",
         **TRACK, "duration_s": 10.0}])
    write_csv(root / "runs.csv", [{"session_id": SESSION, "epoch": "track", **run} for run in RUNS])
    n = TRACK["frame_end"]
    hole = TRACK["frame_start"] - 1 + 10
    x, y, heading = walk(n, 0, hole)
    avg_x, avg_y = x.copy(), y.copy()
    avg_x[hole + 20:hole + 24] = avg_y[hole + 20:hole + 24] = np.nan
    pq.write_table(pa.table({"frame": np.arange(1, n + 1), "t": np.arange(n) / RATE_HZ, "avg_x": avg_x, "avg_y": avg_y,
                             "mashup_x": x, "mashup_y": y, "head_dir": heading}),
                   root / "frames" / f"{SESSION}.parquet")
    return root


@pytest.fixture
def processed(tmp_path):
    root = tmp_path / "processed"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"timestamp": "2026-10-13T11:00:00+00:00"}))
    n = TRACK["frame_end"] - TRACK["frame_start"] + 1
    run = np.zeros(n, dtype=int)
    path_id = np.zeros(n, dtype=int)
    clean = np.zeros(n, dtype=bool)
    for row in RUNS:
        span = slice(row["frame_start"] - TRACK["frame_start"], row["frame_end"] - TRACK["frame_start"] + 1)
        run[span], path_id[span], clean[span] = row["run"], row["path_id"], row["clean"]
    x, y, heading = walk(n, 1, 10)
    for kind, frames, n_runs in (("track", TRACK, 2), ("arena", ARENA, 0)):
        (root / kind / "blocks").mkdir(parents=True)
        block_id = f"{SESSION}_{kind}_1"
        write_csv(root / kind / "blocks.csv", [{
            "block_id": block_id, "session_id": SESSION, "subject_id": "NS14", "date": "2015-01-01",
            "environment": "triple_t", "epoch": kind, **frames,
            "duration_s": (frames["frame_end"] - frames["frame_start"] + 1) / RATE_HZ, "n_runs": n_runs}])
        m = frames["frame_end"] - frames["frame_start"] + 1
        pq.write_table(pa.table({
            "t": np.arange(m) / RATE_HZ, "x": x[:m], "y": y[:m], "heading": heading[:m], "speed": np.ones(m),
            "turn_rate": np.zeros(m), "filled_front": np.zeros(m, dtype=bool), "filled_back": np.zeros(m, dtype=bool),
            "phase": ["outbound"] * m, "run": run[:m] if kind == "track" else np.zeros(m, dtype=int),
            "path_id": path_id[:m], "clean": clean[:m]}), root / kind / "blocks" / f"{block_id}.parquet")
    return root
