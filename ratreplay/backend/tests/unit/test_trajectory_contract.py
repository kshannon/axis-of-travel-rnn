"""
The engines' contract: the default rules and settings are today's constants, the operations are exactly the named ones, and each stub names the task that fills it.
"""

import inspect

import process_lab_data.__main__ as processor
import pytest
from axis_of_travel_rnn import trajectory, windows
from process_lab_data import frame, labels, select
from ratreplay import data as dash

from ratreplay_api.engines.generator import GeneratorEngine
from ratreplay_api.engines.trajectory import RULES, SETTINGS, TrajectoryEngine

# Each rule key and the project constant it comes from (snap_s from the old Dash tool, led_separation_m
# from the processor's checks, as t_step_tolerance_s is).
SOURCES = {
    "condition": (select, "CONDITION"), "epochs": (select, "EPOCHS"), "pause_step_s": (select, "PAUSE_STEP_S"),
    "gap_lights": (select, "GAP_LIGHTS"), "jump_px": (select, "JUMP_PX"), "pause_margin_s": (select, "PAUSE_MARGIN_SEC"),
    "min_block_s": (select, "MIN_BLOCK_S"), "snap_s": (dash, "SNAP_S"), "heading_fill_s": (select, "HEADING_FILL_SEC"),
    "running_floor_m_per_s": (select, "RUNNING_FLOOR_M_PER_S"),
    "outbound_paths": (labels, "OUTBOUND_PATHS"), "return_paths": (labels, "RETURN_PATHS"), "pause_min_s": (labels, "PAUSE_MIN_S"),
    "histogram_bin_px": (frame, "HISTOGRAM_BIN_PX"), "peak_smooth_bins": (frame, "PEAK_SMOOTH_BINS"),
    "peak_prominence": (frame, "PEAK_PROMINENCE"), "axis_agree": (frame, "AXIS_AGREE"),
    "camera_height_m": (frame, "CAMERA_HEIGHT_M"), "track_height_m": (frame, "TRACK_HEIGHT_M"),
    "arena_height_m": (frame, "ARENA_HEIGHT_M"), "nominal_led_separation_m": (frame, "NOMINAL_LED_SEPARATION_M"),
    "extent_percentiles": (frame, "EXTENT_PERCENTILES"), "led_separation_m": (processor, "LED_SEPARATION_M"),
    "speed_smooth_frames": (frame, "SPEED_SMOOTH_FRAMES"),
    "running_px_per_s": (frame, "RUNNING_PX_PER_S"), "offset_warn_deg": (frame, "OFFSET_WARN_DEG"),
    "smooth_window_s": (trajectory, "SMOOTH_WINDOW_S"), "smooth_order": (trajectory, "SMOOTH_ORDER"),
    "kinematics_version": (trajectory, "KINEMATICS_VERSION"), "t_step_tolerance_s": (processor, "T_STEP_TOLERANCE_S"),
}

# Each operation and its parameters as architecture.md names them, and the task that fills it.
TRAJECTORY = {
    "funnel": (("tables", "rules"), "E1"),
    "session": (("arrays", "environment", "rules"), "E1"), "apply": (("blocks", "edits", "session"), "E2"),
    "blocks": (("arrays", "review", "environment", "rules"), "E3"), "windows": (("block", "settings", "rules"), "E4"),
    "recipe": (("blocks", "environment", "rules"), "E5"),
}
GENERATOR = {"session": (("recipe", "environments", "camera", "seed", "length_s", "session_id", "date"), "E6")}
ENGINES = ((TrajectoryEngine, TRAJECTORY), (GeneratorEngine, GENERATOR))
DONE = ("E1", "E2", "E3", "E4", "E5", "E6")


def test_every_rule_equals_the_project_constant_it_comes_from():
    assert set(RULES) == set(SOURCES)
    for key, (module, name) in SOURCES.items():
        assert RULES[key] == getattr(module, name), f"{key} differs from {module.__name__}.{name}"
    assert RULES["outbound_paths"] == frame.OUTBOUND_PATHS
    parallax = (RULES["camera_height_m"] - RULES["track_height_m"]) / (RULES["camera_height_m"] - RULES["arena_height_m"])
    assert parallax == frame.PARALLAX_RATIO


def test_the_settings_equal_the_projects_window_defaults_with_rate_hz_for_train_rate_hz():
    assert SETTINGS == {"rate_hz" if key == "train_rate_hz" else key: value for key, value in windows.DEFAULTS.items()}


def test_an_engine_has_exactly_its_named_operations_and_no_state():
    for engine, contract in ENGINES:
        assert sorted(name for name in dir(engine) if not name.startswith("_")) == sorted(contract)
        for name, (parameters, _) in contract.items():
            assert list(inspect.signature(getattr(engine, name)).parameters) == ["self", *parameters], f"{engine.__name__}.{name}"
        assert vars(engine()) == {}


def test_every_operation_not_yet_built_raises_not_implemented_naming_its_task():
    for engine, contract in ENGINES:
        for name, (parameters, task) in contract.items():
            if task in DONE:
                continue
            with pytest.raises(NotImplementedError, match=f"^task {task}$"):
                getattr(engine(), name)(*[None] * len(parameters))
