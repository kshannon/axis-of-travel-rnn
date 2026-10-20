"""
The versioned kinematics on a known path: a constant-speed circle gives its speed and turn rate back, and a lost heading gives no turn rate. The reader of a processed dataset on a synthetic one.
"""

import json

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest

from axis_of_travel_rnn import trajectory

RATE_HZ, N_FRAMES = 60, 600
RADIUS_M, ANGULAR_RATE = 0.3, 1.5
LOST = (200, 260)
ISLAND = ((300, 310), (315, 320))

# A synthetic processed dataset in the layout the reader expects: two track blocks and one arena block, the csv rows holding
# only what the reader and the window logic touch, the rest None. A block parquet holds the lab frame, then trajectory.COLUMNS.
CSV_COLUMNS = ("block_id", "session_id", "date", "epoch", "frame_start", "frame_end", "n_frames", "duration_s", "reviewed_by")
BLOCK_SCHEMA = pa.schema([(trajectory.FRAME_COLUMN, pa.int32())]
                         + [(name, pa.string() if dtype == "U8" else pa.from_numpy_dtype(np.dtype(dtype))) for name, dtype in trajectory.COLUMNS.items()])
TRACK_IDS, ARENA_IDS = ("S1_track_01", "S1_track_02"), ("S1_arena_01",)
FIRST_FRAME = 2101
MANIFEST = {"run": {"timestamp": "2026-10-16T10:00:00+00:00", "rules": {"select": {"JUMP_PX": 40.0}}}, "sessions": {}}


def block_arrays(n_frames):
    """
    A block's arrays over n_frames of the circle, the lab frame from FIRST_FRAME, the heading lost over LOST, one complete and one partial trip.
    """
    t, x, y, heading = circle()
    heading[LOST[0]:LOST[1]] = np.nan
    at, falses = slice(0, n_frames), np.zeros(n_frames, bool)
    half = n_frames // 2
    return {"frame": np.arange(FIRST_FRAME, FIRST_FRAME + n_frames, dtype=np.int32), "t": t[at], "x": x[at], "y": y[at],
            "heading": heading[at], "speed": np.ones(n_frames), "turn_rate": np.ones(n_frames),
            "n_lights": np.full(n_frames, 2, np.int8), "heading_filled": falses, "heading_held": falses,
            "filled_front": falses, "filled_back": falses, "phase": np.where(np.arange(n_frames) < half, "outbound", "dwell"),
            "trip": np.where(np.arange(n_frames) < half, 1, -2).astype(np.int32), "run": np.ones(n_frames, np.int32),
            "path_id": np.ones(n_frames, np.int16), "clean": ~falses}


def csv_row(block_id, kind, n_frames):
    """
    One blocks csv row with the block's identity, frames and duration, the other columns None.
    """
    return {**dict.fromkeys(CSV_COLUMNS), "block_id": block_id, "session_id": "S1", "date": "2015-01-01",
            "epoch": kind, "frame_start": FIRST_FRAME, "frame_end": FIRST_FRAME + n_frames - 1, "n_frames": n_frames,
            "duration_s": n_frames / RATE_HZ}


@pytest.fixture
def processed(tmp_path):
    """
    The synthetic processed root.
    """
    root = tmp_path / "processed"
    columns = block_arrays(N_FRAMES)
    table = pa.Table.from_arrays([pa.array(columns[field.name], type=field.type) for field in BLOCK_SCHEMA], schema=BLOCK_SCHEMA)
    for kind, ids in (("track", TRACK_IDS), ("arena", ARENA_IDS)):
        for block_id in ids:
            trajectory.block_path(root, kind, block_id).parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(table, trajectory.block_path(root, kind, block_id))
        pacsv.write_csv(pa.Table.from_pylist([csv_row(block_id, kind, N_FRAMES) for block_id in ids]), root / kind / trajectory.BLOCKS_CSV)
    (root / trajectory.MANIFEST).write_text(json.dumps(MANIFEST))
    return root


def circle():
    """
    A circle of RADIUS_M run at ANGULAR_RATE with the heading along the tangent, as t, x, y and heading arrays.
    """
    t = np.arange(N_FRAMES) / RATE_HZ
    angle = ANGULAR_RATE * t
    heading = (angle + np.pi / 2 + np.pi) % (2 * np.pi) - np.pi
    return t, RADIUS_M * np.cos(angle), RADIUS_M * np.sin(angle), heading


def test_the_window_is_an_odd_number_of_samples_at_the_rate():
    assert trajectory.smooth_window(60) == 9 and trajectory.smooth_window(20) == 3 and trajectory.KINEMATICS_VERSION == 1


def test_a_constant_speed_circle_gives_its_speed_and_turn_rate_back_through_the_wrap():
    speed, turn_rate = trajectory.kinematics(*circle(), RATE_HZ)
    assert np.allclose(speed, RADIUS_M * ANGULAR_RATE, rtol=0.02) and np.allclose(turn_rate, ANGULAR_RATE, rtol=0.02)


def test_a_lost_heading_gives_no_turn_rate_there_and_an_island_shorter_than_the_window_none_either():
    t, x, y, heading = circle()
    heading[LOST[0]:LOST[1]] = np.nan
    for first, stop in ISLAND:
        heading[first:stop] = np.nan
    speed, turn_rate = trajectory.kinematics(t, x, y, heading, RATE_HZ)
    gone = np.zeros(N_FRAMES, bool)
    gone[LOST[0]:LOST[1]] = gone[ISLAND[0][0]:ISLAND[1][1]] = True
    assert np.array_equal(np.isnan(turn_rate), gone) and np.isfinite(speed).all()
    assert np.allclose(turn_rate[~gone], ANGULAR_RATE, rtol=0.02)
    assert list(trajectory.COLUMNS) == ["t", "x", "y", "heading", "speed", "turn_rate", "n_lights", "heading_filled", "heading_held",
                                        "filled_front", "filled_back", "phase", "trip", "run", "path_id", "clean"]


def test_load_block_gives_the_written_arrays_back_in_the_schema_dtypes_with_the_block_id(processed):
    block = trajectory.load_block(trajectory.block_path(processed, "track", TRACK_IDS[0]))
    written = block_arrays(N_FRAMES)
    assert block["block_id"] == TRACK_IDS[0] and list(block) == ["frame"] + list(trajectory.COLUMNS) + ["block_id"]
    assert block["frame"].dtype == np.int32 and block["frame"][0] == FIRST_FRAME
    assert all(block[name].dtype == np.dtype(dtype) for name, dtype in trajectory.COLUMNS.items())
    for name in trajectory.COLUMNS:
        assert np.array_equal(block[name], written[name], equal_nan=name == "heading"), name


def test_list_blocks_gives_every_kinds_rows_in_csv_order_with_the_kind_and_the_parquet_path_and_the_manifest_reads(processed):
    rows = trajectory.list_blocks(processed)
    assert [(row["block_id"], row["kind"]) for row in rows] == [(b, "track") for b in TRACK_IDS] + [(b, "arena") for b in ARENA_IDS]
    assert all(row["path"].is_file() and row["path"].stem == row["block_id"] for row in rows)
    assert (rows[0]["n_frames"], rows[0]["duration_s"], rows[0]["date"], rows[0]["reviewed_by"]) == (N_FRAMES, N_FRAMES / RATE_HZ, "2015-01-01", None)
    assert trajectory.read_manifest(processed) == MANIFEST
