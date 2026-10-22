"""
The engine's contract: the default rules and settings are the recorded constants, and the operations are exactly the named ones.
"""

import inspect

import pytest

from axis_of_travel_rnn.blocks import RULES, SETTINGS, BlockEngine
from axis_of_travel_rnn.blocks import frame as new_frame

# The rules as they were when the engine came in from the review tool, which built the blocks with them. A change to one of
# them changes which blocks a session gives, so it is a change to this record too.
RECORD = {
    "condition": "baseline", "epochs": ("arena", "track"), "pause_step_s": 0.1, "gap_lights": "both", "jump_px": 40.0,
    "pause_margin_s": 5.0, "min_block_s": 10.0, "snap_s": 1.0, "heading_fill_s": 3.0, "running_floor_m_per_s": 0.03,
    "outbound_paths": (1, 2, 3, 4), "return_paths": (9, 10), "pause_min_s": 1.0,
    "histogram_bin_px": 2.0, "peak_smooth_bins": 5, "peak_prominence": 0.1, "axis_agree": 0.05,
    "camera_height_m": 2.6, "track_height_m": 0.2, "arena_height_m": 0.4, "nominal_led_separation_m": 0.05,
    "extent_percentiles": (1, 99), "led_separation_m": (0.04, 0.08), "speed_smooth_frames": 6, "running_px_per_s": 20.0,
    "offset_warn_deg": 30.0, "t_step_tolerance_s": 1e-6, "smooth_window_s": 0.15, "smooth_order": 2, "kinematics_version": 1,
}
SETTINGS_RECORD = {"window_s": 40.0, "stride_s": 10.0, "burn_in_s": 1.0, "horizon_s": 0.5, "rate_hz": 20,
                   "min_heading_measured": 0.8, "min_complete_trips": 1}

# Each operation and its parameters.
OPERATIONS = {
    "funnel": ("tables", "rules"), "session": ("arrays", "environment", "rules"), "apply": ("blocks", "edits", "session"),
    "blocks": ("arrays", "review", "environment", "rules"), "windows": ("block", "settings", "rules"),
}


def test_every_rule_and_setting_is_the_recorded_default():
    assert RULES == RECORD and SETTINGS == SETTINGS_RECORD
    parallax = (RULES["camera_height_m"] - RULES["track_height_m"]) / (RULES["camera_height_m"] - RULES["arena_height_m"])
    assert new_frame.arena_scale(100.0, RULES) == pytest.approx(100.0 * parallax)


def test_the_engine_has_exactly_its_named_operations_and_no_state():
    assert sorted(name for name in dir(BlockEngine) if not name.startswith("_")) == sorted(OPERATIONS)
    for name, parameters in OPERATIONS.items():
        assert list(inspect.signature(getattr(BlockEngine, name)).parameters) == ["self", *parameters], name
    assert vars(BlockEngine()) == {}
