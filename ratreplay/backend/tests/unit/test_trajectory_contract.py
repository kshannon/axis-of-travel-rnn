"""
The engines' contract: the default rules and settings are today's constants, the operations are exactly the named ones, and each stub names the task that fills it.
"""

import inspect

import pytest
from axis_of_travel_rnn import trajectory, windows

from ratreplay_api.engines.generator import GeneratorEngine
from ratreplay_api.engines.trajectory import RULES, SETTINGS, TrajectoryEngine
from ratreplay_api.engines.trajectory import frame as new_frame

# The rules that come from the project's trajectory module, each with the constant it must equal.
PROJECT = {"smooth_window_s": "SMOOTH_WINDOW_S", "smooth_order": "SMOOTH_ORDER", "kinematics_version": "KINEMATICS_VERSION"}

# The other rules are the constants the engine moved in from the lab data processor, recorded here as they were when it was removed. A change
# to one of them changes which blocks a session gives, so it is a change to this record too.
RECORD = {
    "condition": "baseline", "epochs": ("arena", "track"), "pause_step_s": 0.1, "gap_lights": "both", "jump_px": 40.0,
    "pause_margin_s": 5.0, "min_block_s": 10.0, "snap_s": 1.0, "heading_fill_s": 3.0, "running_floor_m_per_s": 0.03,
    "outbound_paths": (1, 2, 3, 4), "return_paths": (9, 10), "pause_min_s": 1.0,
    "histogram_bin_px": 2.0, "peak_smooth_bins": 5, "peak_prominence": 0.1, "axis_agree": 0.05,
    "camera_height_m": 2.6, "track_height_m": 0.2, "arena_height_m": 0.4, "nominal_led_separation_m": 0.05,
    "extent_percentiles": (1, 99), "led_separation_m": (0.04, 0.08), "speed_smooth_frames": 6, "running_px_per_s": 20.0,
    "offset_warn_deg": 30.0, "t_step_tolerance_s": 1e-6,
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


def test_every_rule_is_the_recorded_default_or_the_project_constant_it_comes_from():
    assert set(RULES) == set(RECORD) | set(PROJECT)
    assert {key: RULES[key] for key in RECORD} == RECORD
    for key, name in PROJECT.items():
        assert RULES[key] == getattr(trajectory, name), f"{key} differs from trajectory.{name}"
    parallax = (RULES["camera_height_m"] - RULES["track_height_m"]) / (RULES["camera_height_m"] - RULES["arena_height_m"])
    assert new_frame.arena_scale(100.0, RULES) == pytest.approx(100.0 * parallax)


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
