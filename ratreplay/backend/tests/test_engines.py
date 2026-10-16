"""
The algorithms the tool adds to the project's: run length spans, the checks of each window, the occupancy grid.
"""

import numpy as np

from ratreplay_api.engines import occupancy, spans, windows

RATE_HZ = 60
SETTINGS = {**windows.DEFAULTS, "window_s": 20.0, "stride_s": 10.0, "horizon_s": 0.0, "burn_in_s": 1.0, "min_heading_measured": 0.9}


def block_of(seconds, **columns):
    """
    A still block with a finite position and a measured heading throughout, the columns given replacing the defaults.
    """
    n = seconds * RATE_HZ
    still = {"t": np.arange(n) / RATE_HZ, "x": np.zeros(n), "y": np.zeros(n), "heading": np.zeros(n), "heading_filled": np.zeros(n, bool),
             "heading_held": np.zeros(n, bool), "trip": np.zeros(n, np.int32)}
    return {**still, **columns}


def test_value_spans_split_at_every_change_and_skip_zero_runs():
    block = {"run": np.array([0, 0, 1, 1, 1, 0, 2, 2]), "path_id": np.arange(8), "clean": np.ones(8, bool)}
    assert spans.value_spans(block["run"]) == [(0, 0, 1), (1, 2, 4), (0, 5, 5), (2, 6, 7)]
    assert [(r["run"], r["first"], r["last"]) for r in spans.run_spans(block)] == [(1, 2, 4), (2, 6, 7)]


def test_windows_are_checked_one_by_one():
    heading = np.zeros(50 * RATE_HZ)
    heading[1100:1300] = np.nan
    trip = np.zeros(50 * RATE_HZ, np.int32)
    trip[0:300], trip[300:600], trip[600:900], trip[900:1200] = 1, -2, 3, -4
    rows = windows.window_rows(block_of(50, heading=heading, trip=trip), RATE_HZ, SETTINGS)
    assert len(rows) == windows.window_count(50 * RATE_HZ, RATE_HZ, SETTINGS) == 4
    assert (rows[1]["first"], rows[1]["burn_in_stop"], rows[1]["window_stop"], rows[1]["stop"]) == (600, 660, 1800, 1800)
    assert [row["ok"] for row in rows] == [True, False, True, True]
    assert rows[1]["heading_measured"] == 1000 / 1200
    assert (rows[0]["trips_complete"], rows[0]["trips_partial"]) == (2, 2)  # trips 1 and 3 are complete, -2 and -4 are partial


def test_a_window_is_ok_at_exactly_the_minimum_heading_share():
    heading = np.zeros(20 * RATE_HZ)
    heading[:120] = np.nan  # 1080 of 1200 frames measured, 0.9
    assert windows.window_rows(block_of(20, heading=heading), RATE_HZ, SETTINGS)[0]["ok"]


def test_the_horizon_extends_each_window_past_its_training_part():
    rows = windows.window_rows(block_of(50), RATE_HZ, {**SETTINGS, "horizon_s": 5.0})
    assert [(row["window_stop"], row["stop"]) for row in rows] == [(1200, 1500), (1800, 2100), (2400, 2700)]


def test_occupancy_counts_each_epoch_over_one_shared_grid():
    frames = {"frame": np.arange(1, 11), "mashup_x": np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, np.nan]), "mashup_y": np.arange(10.0)}
    epochs = [{"epoch": "arena", "frame_start": 1, "frame_end": 5}, {"epoch": "track", "frame_start": 6, "frame_end": 10}]
    grid = occupancy.occupancy(frames, epochs)
    assert grid["x"] == [0.0, 8.0] and grid["y"] == [0.0, 8.0]
    assert [sum(grid["counts"][name]) for name in ("arena", "track")] == [5, 4]


def test_occupancy_rows_run_from_the_lowest_y():
    frames = {"frame": np.arange(1, 4), "mashup_x": np.array([0.0, 8.0, 0.0]), "mashup_y": np.array([0.0, 8.0, 8.0])}
    counts = occupancy.occupancy(frames, [{"epoch": "arena", "frame_start": 1, "frame_end": 3}])["counts"]["arena"]
    assert counts[(occupancy.BINS - 1) * occupancy.BINS] == 1  # lowest x, highest y: the first cell of the last row
