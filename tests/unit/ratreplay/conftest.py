"""
Fixtures for the RatReplay tests: a synthetic transformed folder of one session and an empty processed root beside it, and a processed dataset the processor built from its own tests' synthetic sessions.
"""

import json

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest

import process_lab_data.__main__ as processor
import proj_helpers.paths
from ratreplay import blocks, data
from tests.unit.process_lab_data import conftest as lab

SESSION = "NS14_rec1_20150101_001"
RATE_HZ, MAX_GAP = 60, 30
STAMP = "2026-10-13T10:00:00+00:00"

# An arena epoch of 2400 frames, then a track epoch of 6600 holding three runs, a stretch with both lights lost at
# 4000 to 4049, a jump of JUMP_PX at frame JUMP and a pause at PAUSE. With the processor's 5 s margins (300 frames)
# trimmed at the epoch bounds, the jump and the pause but not at the gap, the automatic blocks are arena 301 to 2100
# and track 2701 to 3999, 4050 to 5700 and 6301 to 7700, the 400 frames left after the pause too short to keep. The
# front light alone is lost over SHORT_HEADING_GAP (1 s, filled by the processor) and LONG_HEADING_GAP (5 s, kept NaN).
N_FRAMES = 9000
ARENA = {"frame_start": 1, "frame_end": 2400}
TRACK = {"frame_start": 2401, "frame_end": 9000}
GAP = (4000, 4049)
PAUSE = 8001
JUMP, JUMP_PX = 6001, 100.0
SHORT_HEADING_GAP = (5000, 5059)
LONG_HEADING_GAP = (7000, 7299)
MARGINS = [(1, 300), (2101, 2400), (2401, 2700), (5701, 6000), (6001, 6300), (7701, 8000), (8001, 8300), (8701, 9000)]
STRETCHES = [(301, 2100), (2701, 3999), (4050, 5700), (6301, 7700), (8301, 8700)]
AUTO_BLOCKS = STRETCHES[:4]
RUNS = [{"run": 1, "path_id": 3, "clean": True, "frame_start": 2800, "frame_end": 2920},
        {"run": 2, "path_id": 7, "clean": False, "frame_start": 3100, "frame_end": 3200},
        {"run": 3, "path_id": 3, "clean": True, "frame_start": 4500, "frame_end": 4620}]


def write_csv(path, rows):
    """
    Write a list of same-keyed dicts as a csv table.
    """
    pacsv.write_csv(pa.Table.from_pylist(rows), path)


def between(frame, span):
    """
    True on the frames of the (first, last) span.
    """
    return (frame >= span[0]) & (frame <= span[1])


def frames_table():
    """
    The session's frames (tables.md 2.4): a random walk for the mashup light, lost over the gap, t jumping at the pause.
    """
    rng = np.random.default_rng(0)
    frame = np.arange(1, N_FRAMES + 1)
    t = (frame - 1) / RATE_HZ
    t[frame >= PAUSE] += 60.0
    lost = between(frame, GAP)
    one_light = between(frame, SHORT_HEADING_GAP) | between(frame, LONG_HEADING_GAP)
    x, y = np.cumsum(rng.normal(size=(2, N_FRAMES)), axis=1) + 300
    x[frame >= JUMP] += JUMP_PX
    x[frame >= PAUSE] += JUMP_PX
    x[lost] = y[lost] = np.nan
    heading = np.where(lost | one_light, np.nan, rng.uniform(-np.pi, np.pi, N_FRAMES))
    epoch = np.where(frame <= ARENA["frame_end"], "arena", "track")
    return pa.table({
        "session_id": [SESSION] * N_FRAMES, "frame": frame, "t": t,
        "front_x": x, "front_y": y, "back_x": x - 10, "back_y": y, "head_dir": heading,
        "filled_front": np.zeros(N_FRAMES, bool), "filled_back": np.zeros(N_FRAMES, bool),
        "unfilled_front": lost | one_light, "unfilled_back": lost, "painted_label": np.full(N_FRAMES, 99),
        "avg_x": x, "avg_y": y, "mashup_x": x, "mashup_y": y, "epoch": epoch,
    })


def session_row(session_id):
    """
    The sessions table's row for a session with the synthetic frames.
    """
    return {"session_id": session_id, "subject_id": "NS14", "group": "NS14Data", "date": "2015-01-01",
            "protocol": "standard", "rate_hz": RATE_HZ, "max_gap": MAX_GAP, "n_frames": N_FRAMES}


def epoch_rows(session_id):
    """
    The epochs table's rows for a session: the arena, then the track.
    """
    return [{"session_id": session_id, "epoch": "arena", "environment": "open_arena", "condition": "baseline", **ARENA,
             "duration_s": 2400 / RATE_HZ},
            {"session_id": session_id, "epoch": "track", "environment": "triple_t", "condition": "baseline", **TRACK,
             "duration_s": 6600 / RATE_HZ}]


def write_sessions(root, session_ids):
    """
    Write the tables and the frames of these sessions, every one a copy of the synthetic session, into the folder.
    """
    write_csv(root / "sessions.csv", [session_row(s) for s in session_ids])
    write_csv(root / "epochs.csv", [row for s in session_ids for row in epoch_rows(s)])
    write_csv(root / "runs.csv", [{"session_id": s, "epoch": "track", **run} for s in session_ids for run in RUNS])
    for s in session_ids:
        pq.write_table(frames_table(), root / "frames" / f"{s}.parquet")


@pytest.fixture(autouse=True)
def no_local_config(monkeypatch):
    """
    Make reading configs/local.yaml an error, so every test passes its own config.
    """
    def refuse(*args, **kwargs):
        raise AssertionError("a test read configs/local.yaml, pass config instead")
    monkeypatch.setattr(proj_helpers.paths, "local_config", refuse)


def write_lab_transformed(root):
    """
    The processor tests' synthetic transformed root, as their transformed fixture writes it, into the folder.
    """
    (root / "frames").mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"run": {"timestamp": lab.STAMP}}))
    for name, columns in (("sessions", lab.SESSIONS), ("epochs", lab.EPOCHS), ("runs", lab.RUNS), ("annotations", lab.ANNOTATIONS)):
        pacsv.write_csv(pa.table(columns), root / f"{name}.csv")
    for session_id, cuts in lab.FRAMES.items():
        pq.write_table(lab.frames_table(session_id, **cuts), root / "frames" / f"{session_id}.parquet")


@pytest.fixture(autouse=True)
def fresh_counts():
    """
    Empty the automatic block count cache and the block shares cache, so no test sees another's.
    """
    data.AUTOMATIC_COUNTS.clear()
    blocks.CACHE.clear()


@pytest.fixture
def transformed(tmp_path):
    """
    The converter's tables, frames and manifest for the one session.
    """
    root = tmp_path / "transformed"
    (root / "frames").mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"run": {"timestamp": STAMP}}))
    write_sessions(root, [SESSION])
    return root


@pytest.fixture
def processed(tmp_path):
    """
    The processed root the review folder is created under, not existing yet.
    """
    return tmp_path / "processed"


@pytest.fixture
def built(tmp_path):
    """
    A processed dataset under tmp_path: the processor run on its tests' synthetic sessions, two track blocks and one arena block.
    """
    source, root = tmp_path / "lab_transformed", tmp_path / "built"
    write_lab_transformed(source)
    assert processor.main([], config={"TRANSFORMED_LAB_DATA": str(source), "PROCESSED_LAB_DATA": str(root)}) == 0
    return root
