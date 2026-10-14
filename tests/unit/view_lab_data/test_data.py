"""
Data access on a synthetic processed folder and a synthetic transformed folder: listing, loading, the verdicts file.
"""

import csv
import json
import shutil

import numpy as np
import pyarrow.parquet as pq
import pytest

from view_lab_data import data

from .conftest import RATE_HZ, SESSION, TRACK


def test_transformed_blocks_and_runs_come_from_the_tables(transformed):
    blocks = data.list_blocks(transformed, True)
    assert [b["block_id"] for b in blocks] == [f"{SESSION}_arena", f"{SESSION}_track"]
    assert [b["n_runs"] for b in blocks] == [0, 2]
    assert blocks[1]["group"] == "NS14Data"
    runs = data.list_runs(transformed, True, blocks[1])
    assert [(r["run"], r["path_id"], r["clean"], r["start"], r["end"]) for r in runs] == [
        (1, 3, True, 99, 219), (2, 7, False, 299, 399)]
    assert data.list_runs(transformed, True, blocks[0]) == []
    assert data.manifest_timestamp(transformed, True) == "2026-10-13T10:00:00+00:00"


def test_processed_blocks_and_runs_come_from_the_blocks_tables_and_labels(processed):
    blocks = data.list_blocks(processed, False)
    assert [b["epoch"] for b in blocks] == ["track", "arena"]
    runs = data.list_runs(processed, False, blocks[0])
    assert [(r["run"], r["path_id"], r["clean"], r["start"], r["end"]) for r in runs] == [
        (1, 3, True, 99, 219), (2, 7, False, 299, 399)]
    assert runs[0]["duration_s"] == pytest.approx(121 / RATE_HZ)
    assert data.list_runs(processed, False, blocks[1]) == []
    assert data.manifest_timestamp(processed, False) == "2026-10-13T11:00:00+00:00"


def test_a_processed_kind_without_its_table_is_skipped(processed):
    shutil.rmtree(processed / "arena")
    assert [b["epoch"] for b in data.list_blocks(processed, False)] == ["track"]


@pytest.mark.parametrize("source, is_transformed", [("transformed", True), ("processed", False)])
def test_a_block_loads_as_json_ready_lists(request, source, is_transformed):
    root = request.getfixturevalue(source)
    block = next(b for b in data.list_blocks(root, is_transformed) if b["epoch"] == "track")
    loaded = data.load_block(root, is_transformed, block)
    n = TRACK["frame_end"] - TRACK["frame_start"] + 1
    assert all(len(loaded[name]) == n for name in (*data.BLOCK_ARRAYS, "motion"))
    assert loaded["x"][10] is None and loaded["x"][20] is not None
    assert loaded["units"] == ("px" if is_transformed else "m") and loaded["y_down"] is is_transformed
    json.dumps(loaded)


def test_transformed_speed_is_the_smoothed_step_over_dt_of_the_whole_session(transformed):
    block = data.list_blocks(transformed, True)[0]
    frames = pq.read_table(transformed / "frames" / f"{SESSION}.parquet").to_pandas()
    step = np.hypot(np.diff(frames["mashup_x"]), np.diff(frames["mashup_y"])) / np.diff(frames["t"])
    expected = np.convolve(np.concatenate([step[:1], step]), np.ones(6) / 6, mode="same")
    expected = expected[block["frame_start"] - 1:block["frame_end"]]
    speed = np.array(data.load_block(transformed, True, block)["speed"], dtype=float)
    assert np.allclose(speed[np.isfinite(expected)], expected[np.isfinite(expected)])


def test_transformed_position_and_speed_come_from_the_mashup_light(transformed):
    block = data.list_blocks(transformed, True)[1]
    loaded = data.load_block(transformed, True, block)
    assert loaded["x"][10] is None and loaded["speed"][10] is None
    assert loaded["x"][30] is not None and loaded["speed"][30] is not None and loaded["motion"][30] is not None
    assert set(loaded["led_offset"]) == {"rad", "r"} and 0 <= loaded["led_offset"]["r"] <= 1


def test_the_led_offset_recovers_a_known_mounting_angle():
    n, radius, mounting = 1200, 150.0, np.deg2rad(105)
    t = np.arange(n) / RATE_HZ
    x, y = radius * np.cos(t), radius * np.sin(t)
    heading = np.arctan2(np.gradient(y), np.gradient(x)) + mounting + np.random.default_rng(0).normal(0, 0.1, n)
    offset = data.led_offset(heading, data.motion_direction(t, x, y), data.speed_from_positions(t, x, y))
    assert abs(np.rad2deg(offset["rad"]) - 105) < 3 and offset["r"] > 0.9
    assert data.led_offset(heading, data.motion_direction(t, x, y), np.zeros(n)) == {"rad": 0.0, "r": 0.0}


def test_the_latest_verdict_per_run_wins_and_a_save_is_one_full_row(processed):
    block_id = f"{SESSION}_track_1"
    assert data.latest_verdicts(processed) == {}
    data.append_verdict(processed, block_id, SESSION, 1, "tracking artifact", "jump", "2026-10-13T11:00:00+00:00")
    data.append_verdict(processed, block_id, SESSION, 1, "fine", "fine on review", "2026-10-13T11:00:00+00:00")
    data.append_verdict(processed, f"{SESSION}_arena_1", SESSION, None, "unsure", "", "2026-10-13T11:00:00+00:00")
    latest = data.latest_verdicts(processed)
    assert latest[(block_id, 1)]["tag"] == "fine" and latest[(block_id, 1)]["comment"] == "fine on review"
    assert latest[(f"{SESSION}_arena_1", None)]["tag"] == "unsure"
    with (processed / data.VERDICTS).open(newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 3 and tuple(rows[0]) == data.VERDICT_COLUMNS
    assert rows[2]["run"] == "" and rows[0]["who"] and rows[0]["saved_at"].endswith("+00:00")
