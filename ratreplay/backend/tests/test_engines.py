"""
The algorithms the tool adds to the project's: run length spans and the occupancy grid. The checks of each window are the project's, tested in tests/unit/test_windows.py.
"""

import numpy as np

from ratreplay_api.engines import occupancy, spans


def test_value_spans_split_at_every_change_and_skip_zero_runs():
    block = {"run": np.array([0, 0, 1, 1, 1, 0, 2, 2]), "path_id": np.arange(8), "clean": np.ones(8, bool)}
    assert spans.value_spans(block["run"]) == [(0, 0, 1), (1, 2, 4), (0, 5, 5), (2, 6, 7)]
    assert [(r["run"], r["first"], r["last"]) for r in spans.run_spans(block)] == [(1, 2, 4), (2, 6, 7)]


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
