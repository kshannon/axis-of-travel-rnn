"""
The dataset: inputs are position only by default, heading is an input as its sine and cosine only when asked, the target is the position a horizon ahead, the leakage assertion fires, and the seams with the block engine's windows and the resampling hold.
"""

import numpy as np
import pytest

from axis_of_travel_rnn import data
from axis_of_travel_rnn.blocks.windows import windows as block_windows
from axis_of_travel_rnn.dataset import DEFAULT_INPUTS, TARGETS, WindowDataset, assert_no_leakage, fit_scaler, make_windows

from .handmade import TRAINING_RATE_HZ, wandering

# Small windows at 20 Hz: 4 s windows every 2 s, a 1 s burn in, a 0.5 s horizon (10 steps), no block checks.
SETTINGS = {"window_s": 4.0, "stride_s": 2.0, "burn_in_s": 1.0, "horizon_s": 0.5, "min_heading_measured": 0.0,
            "min_complete_trips": 0}
HORIZON = 10
BOUNDS = ("first", "burn_in_stop", "window_stop", "stop")  # the frame bounds of a window


def blocks():
    return [data.resample(wandering(1801, seed), TRAINING_RATE_HZ) for seed in (0, 1)]


def test_the_target_is_the_scaled_position_a_horizon_ahead_and_heading_never_enters():
    found = blocks()
    windows, verdicts = make_windows(found, SETTINGS)
    assert all(v["ok"] for v in verdicts.values()) and windows
    dataset = WindowDataset(found, windows, DEFAULT_INPUTS, fit_scaler(found[:1], DEFAULT_INPUTS))
    assert dataset.columns == ("x", "y") and dataset.skipped == 0
    item = dataset[3]
    assert item["x"].shape == (80, 2) and item["y"].shape == (80, 2)
    assert np.array_equal(item["y"][:-HORIZON].numpy(), item["x"][HORIZON:].numpy())  # with x, y in, input t + h is target t
    assert np.array_equal(item["current"].numpy(), item["x"].numpy())
    assert item["loss_weight"][:20].sum() == 0 and item["loss_weight"][20:].min() == 1  # no loss in the burn in


def test_the_leakage_assertion_fires_on_a_folded_heading_or_a_column_not_allowed():
    found = blocks()
    windows, _ = make_windows(found, SETTINGS)
    heading = found[0]["arrays"]["heading"]
    for signal in (np.mod(heading, np.pi), np.cos(2 * heading), np.sin(2 * heading)):
        found[0]["arrays"]["speed"] = 0.3 * signal + 0.2  # a speed column that is really the folded heading
        with pytest.raises(AssertionError, match="folded heading"):
            WindowDataset(found, windows, ("x", "y", "speed"), fit_scaler(found, ("x", "y", "speed")))
    with pytest.raises(AssertionError, match="not allowed"):
        WindowDataset(found, windows, ("x", "y", "path_id"), fit_scaler(found, ("x", "y", "path_id")))
    x = np.column_stack([found[1]["arrays"]["x"], found[1]["arrays"]["y"]])
    assert_no_leakage(x, found[1]["arrays"]["heading"], ("x", "y"))


def test_heading_as_an_input_is_a_sine_and_cosine_and_the_target_is_still_the_future_position():
    found = blocks()
    windows, _ = make_windows(found, SETTINGS)
    columns = ("x", "y", "heading")
    scaler = fit_scaler(found[:1], columns)
    dataset = WindowDataset(found, windows, columns, scaler)
    assert "heading" not in scaler and dataset.layout == ("x", "y", "heading_sin", "heading_cos") and dataset.skipped == 0
    item = dataset[3]
    assert item["x"].shape == (80, 4) and item["y"].shape == (80, 2)
    assert np.abs(item["x"][:, 2:].numpy()).max() <= 1
    assert np.array_equal(item["y"][:-HORIZON].numpy(), item["x"][HORIZON:, :2].numpy())  # the target is x, y ahead, heading is not in it
    lost = 100  # one frame without a heading drops every window that holds it, and no other
    held = sum(w["block"] == 0 and w["first"] <= lost < w["window_stop"] for w in windows)
    found[0]["arrays"]["heading"][lost] = np.nan
    assert held > 0
    assert WindowDataset(found, windows, columns, scaler).skipped == held
    assert WindowDataset(found, windows, DEFAULT_INPUTS, fit_scaler(found[:1], DEFAULT_INPUTS)).skipped == 0


def test_the_datasets_windows_are_exactly_the_ones_the_block_engine_admits():
    block = data.resample(wandering(1801, seed=2), TRAINING_RATE_HZ)
    block["arrays"]["x"][150] = np.nan  # one frame without a position refuses the windows that hold it, and no other
    rows = block_windows(block, SETTINGS, block["rules"])["rows"]
    admitted = [{"block": 0, **{key: row[key] for key in BOUNDS}} for row in rows if row["ok"]]
    assert 0 < len(admitted) < len(rows)
    windows, _ = make_windows([block], SETTINGS)
    dataset = WindowDataset([block], windows, DEFAULT_INPUTS, fit_scaler([block], DEFAULT_INPUTS))
    assert windows == admitted and dataset.windows == admitted and dataset.skipped == 0


def test_the_target_of_every_window_is_its_blocks_position_a_horizon_ahead_frame_for_frame():
    block = data.resample(wandering(1801, seed=3), TRAINING_RATE_HZ)
    scaler = fit_scaler([block], DEFAULT_INPUTS)
    windows, _ = make_windows([block], SETTINGS)
    dataset = WindowDataset([block], windows, DEFAULT_INPUTS, scaler)
    position = np.column_stack([(block["arrays"][c] - scaler[c]["mean"]) / scaler[c]["sd"] for c in TARGETS]).astype(np.float32)
    for i, w in enumerate(dataset.windows):
        item = dataset[i]
        assert w["stop"] - w["window_stop"] == HORIZON
        assert np.array_equal(item["y"].numpy(), position[w["first"] + HORIZON:w["window_stop"] + HORIZON])
        assert np.array_equal(item["x"].numpy(), position[w["first"]:w["window_stop"]])


def test_resampling_from_60_to_20_hz_keeps_the_window_and_the_horizon_in_seconds():
    lab = wandering(1801, seed=4)
    at_lab, at_training = (block_windows(b, SETTINGS, b["rules"])["rows"] for b in (lab, data.resample(lab, TRAINING_RATE_HZ)))
    assert len(at_lab) == len(at_training) > 0
    for fast, slow in zip(at_lab, at_training):
        assert (fast["start_s"], fast["stop_s"]) == (slow["start_s"], slow["stop_s"])
        assert all(fast[key] == 3 * slow[key] for key in BOUNDS)  # every frame count a third at 20 Hz
        assert fast["stop"] - fast["window_stop"] == 3 * HORIZON
