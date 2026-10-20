"""
GeneratorEngine over a hand made recipe: deterministic in its seed, in the transformed schema, inside the geometry, its runs from site to site, blocked by TrajectoryEngine.blocks like a real session with the camera recovered, its lateral spread and lean toward the outer wall, tracking noise, varied runs with reversals, wandering dwells, the arena's distance from the wall and speed dependent heading the recipe's, and refusing what it cannot generate from.
"""

import datetime
from pathlib import Path

import numpy as np
import pytest

from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.transformed import FRAMES
from ratreplay_api.engines.generator import GOALS, START, GeneratorEngine
from ratreplay_api.engines.trajectory import RULES, TrajectoryEngine
from ratreplay_api.engines.trajectory.kinematics import kinematics
from ratreplay_api.engines.trajectory.recipe import circular_std, outward_offset, reversal_frames
from ratreplay_api.engines.trajectory.room import to_room
from ratreplay_api.utilities.errors import Invalid

ENVIRONMENTS = Path(__file__).resolve().parents[4] / "configs" / "environments"
SEED, LENGTH_S, SESSION_ID, DATE = 7, {"arena": 120.0, "track": 300.0}, "syn_test", datetime.date(2026, 10, 19)
TEN_MINUTES = {"arena": 600.0, "track": 600.0}
LEAN_TOLERANCE, REVERSAL_FACTOR = 0.3, 2.0

# The arena walk hugs the wall with its midpoint on the boundary, so over thousands of frames the tracking noise carries it
# past by up to about four of its spreads.
WALL_NOISES = 5
LED_SEPARATION_M = 0.05
SITE_TOLERANCE_M, SCALE_TOLERANCE, ROTATION_TOLERANCE_RAD = 0.03, 0.05, 0.01
RECIPE_TOLERANCE, MIN_RUN_CV, MIN_DWELL_SPAN_M = 0.3, 0.1, 0.02
FAST_M_PER_S, MAX_FAST_SPREAD_RAD, MIN_STILL_SPREAD_RAD, MAX_FLIP_SHARE = 0.3, 0.6, 1.5, 1e-3
NOISE_M = 0.002
TRACK_SCALE = 300.0
CAMERA = {
    "track": {"scale_px_per_m": TRACK_SCALE, "rotation_rad": 0.1, "flip": True, "offset_m": [-0.3, 2.1]},
    "arena": {"scale_px_per_m": TRACK_SCALE * 2.4 / 2.2, "rotation_rad": 0.1, "flip": True, "offset_m": [-0.25, 2.0]},
    "led_separation_m": LED_SEPARATION_M, "rate_hz": 60, "max_gap": 30,
}


def q(q05, q25, q50, q75, q95):
    """
    A quantile dict with its mean the median.
    """
    return {"q05": q05, "q25": q25, "q50": q50, "q75": q75, "q95": q95, "mean": q50}


def curve(degrees):
    """
    A heading spread by speed list over the speeds of Kyle's real curves, the spreads given in degrees.
    """
    return [{"speed_m_per_s": s, "spread_rad": float(np.radians(d)), "n": 1000} for s, d in zip((0.05, 0.1, 0.17, 0.23, 0.33, 0.67), degrees)]


OUTBOUND, RETURN = q(4.0, 4.5, 5.0, 5.5, 6.0), q(6.0, 7.0, 7.5, 8.0, 9.0)
RECIPE = {
    "track": {
        "speed": q(0.0, 0.1, 0.3, 0.45, 0.6), "turn_rate": q(-2.0, -0.5, 0.0, 0.5, 2.0), "turn_rate_abs_mean": 0.8,
        "still_fraction": 0.3, "heading_spread_rad": 0.3, "pauses": {"per_min": 0.0, "duration_s": q(*[None] * 5)},
        "runs": {**{str(p): {"count": 10, "duration_s": OUTBOUND} for p in (1, 2, 3, 4)}, "9": {"count": 20, "duration_s": RETURN},
                 "10": {"count": 20, "duration_s": RETURN}},
        "dwell_s": {"start": q(1.0, 1.5, 2.0, 2.5, 3.0), "goal": q(1.0, 1.5, 2.0, 2.5, 3.0)},
        "trips_per_min": 3.0, "goal_share": {"1": 0.25, "2": 0.25, "3": 0.25, "4": 0.25},
        "lateral_m": q(0.0014, 0.0070, 0.0148, 0.0253, 0.0431), "speed_cv_run": 0.25, "tracking_noise_m": NOISE_M,
        "lateral_outward_m": {"perimeter": q(-0.008, 0.005, 0.015, 0.025, 0.038), "inner": q(-0.03, -0.012, 0.0, 0.012, 0.03)},
        "reversals_per_min": 10.0, "run_reversals_per_min": 1.0, "phase_share": {"outbound": 0.25, "dwell": 0.5, "return": 0.25, "pause": 0.0},
        "heading_spread_by_speed": curve((145, 120, 90, 60, 30, 15)), "heading_lag_s": 0.044,
    },
    "arena": {
        "speed": q(0.0, 0.05, 0.12, 0.2, 0.35), "turn_rate": q(-2.5, -0.8, 0.0, 0.8, 2.5), "turn_rate_abs_mean": 1.0,
        "still_fraction": 0.2, "heading_spread_rad": 0.4, "pauses": {"per_min": 2.0, "duration_s": q(1.0, 1.5, 2.0, 2.5, 3.0)},
        "speed_cv": 0.3, "tracking_noise_m": NOISE_M, "heading_spread_by_speed": curve((150, 125, 95, 70, 50, 50)), "heading_lag_s": 0.149,
        "boundary_distance_m": q(0.0, 0.015, 0.03, 0.045, 0.07), "reversals_per_min": 5.0,
    },
}


@pytest.fixture(scope="module")
def environments():
    """
    The geometry of the arena and the track by kind.
    """
    access = EnvironmentAccess(ENVIRONMENTS)
    return {"arena": access.environment("open_arena"), "track": access.environment("triple_t")}


@pytest.fixture(scope="module")
def made(environments):
    """
    One generated session.
    """
    return GeneratorEngine().session(RECIPE, environments, CAMERA, SEED, LENGTH_S, SESSION_ID, DATE)


@pytest.fixture(scope="module")
def built(made, environments):
    """
    The generated session blocked by TrajectoryEngine.blocks.
    """
    return TrajectoryEngine().blocks(made, None, {g["name"]: g for g in environments.values()}, RULES)


@pytest.fixture(scope="module")
def ten(environments):
    """
    A session of ten minutes of arena and ten of track, and its blocks.
    """
    made = GeneratorEngine().session(RECIPE, environments, CAMERA, SEED, TEN_MINUTES, SESSION_ID, DATE)
    return made, TrajectoryEngine().blocks(made, None, {g["name"]: g for g in environments.values()}, RULES)


def room_of(made, kind):
    """
    The mashup positions of the kind's epoch in room metres under the camera, and the epoch's slice.
    """
    epoch = next(e for e in made["epochs"] if e["epoch"] == kind)
    at = slice(epoch["frame_start"] - 1, epoch["frame_end"])
    p = CAMERA[kind]
    x, y = to_room(made["arrays"]["mashup_x"][at], made["arrays"]["mashup_y"][at], p["scale_px_per_m"], p["flip"], p["rotation_rad"], p["offset_m"])
    return np.column_stack([x, y]), at


def segment_distance(points, p0, p1):
    """
    The distance of every point to the segment from p0 to p1.
    """
    p0, p1 = np.array(p0), np.array(p1)
    along = p1 - p0
    t = np.clip((points - p0) @ along / (along @ along), 0, 1)
    return np.hypot(*(points - p0 - t[:, None] * along).T)


def test_the_same_seed_gives_equal_arrays_and_another_seed_differs(made, environments):
    again = GeneratorEngine().session(RECIPE, environments, CAMERA, SEED, LENGTH_S, SESSION_ID, DATE)
    other = GeneratorEngine().session(RECIPE, environments, CAMERA, SEED + 1, LENGTH_S, SESSION_ID, DATE)
    for name in made["arrays"]:
        np.testing.assert_array_equal(made["arrays"][name], again["arrays"][name])
    assert made["runs"] == again["runs"] and not np.array_equal(made["arrays"]["mashup_x"], other["arrays"]["mashup_x"])
    assert made["session"]["date"] == DATE and made["session"]["subject_id"] == "synthetic"


def test_the_arrays_carry_every_frames_column_with_its_length_and_dtype(made):
    n = round(60 * sum(LENGTH_S.values()))
    kinds = {"double": "f", "int64": "i", "bool": "b", "string": "O"}
    assert list(made["arrays"]) == [name for name in FRAMES if name != "session_id"]
    for name, kind in FRAMES.items():
        if name != "session_id":
            assert len(made["arrays"][name]) == n and made["arrays"][name].dtype.kind == kinds[kind], name
    np.testing.assert_allclose(np.diff(made["arrays"]["t"]), 1 / 60, rtol=0, atol=1e-9)


def test_every_position_lies_inside_the_geometry(made, environments):
    track, _ = room_of(made, "track")
    allowed = environments["track"]["params"]["corridor_width"] / 2 + LED_SEPARATION_M / 2 + 3 * NOISE_M
    nearest = np.min([segment_distance(track, s["p0"], s["p1"]) for s in environments["track"]["centerline"]], axis=0)
    assert nearest.max() <= allowed
    arena, _ = room_of(made, "arena")
    assert np.hypot(*(arena - np.array(environments["arena"]["room"]) / 2).T).max() <= environments["arena"]["params"]["diameter"] / 2 + WALL_NOISES * NOISE_M


def test_every_run_starts_at_its_site_and_ends_at_the_other(made, environments):
    xy, at = room_of(made, "track")
    sites = environments["track"]["reward_sites"]
    for run in made["runs"]:
        first, last = xy[run["frame_start"] - 1 - at.start], xy[run["frame_end"] - 1 - at.start]
        if run["path_id"] in GOALS:
            assert np.hypot(*(first - sites[START])) < SITE_TOLERANCE_M and np.hypot(*(last - sites[GOALS[run["path_id"]]])) < SITE_TOLERANCE_M
        else:
            assert min(np.hypot(*(first - sites[g])) for g in GOALS.values()) < SITE_TOLERANCE_M and np.hypot(*(last - sites[START])) < SITE_TOLERANCE_M


def test_the_session_blocks_like_a_real_one_with_trips_and_the_camera_recovered(built):
    track = [b for b in built["blocks"] if b["row"]["kind"] == "track"]
    assert track and all(b["row"]["n_complete_trips"] >= 1 and (b["arrays"]["trip"] > 0).any() for b in track)
    assert all(b["problems"] == [] for b in built["blocks"])
    for kind in ("track", "arena"):
        assert abs(built["frame"][kind]["scale_px_per_m"] / CAMERA[kind]["scale_px_per_m"] - 1) < SCALE_TOLERANCE
        assert abs(built["frame"][kind]["rotation_rad"] - CAMERA[kind]["rotation_rad"]) < ROTATION_TOLERANCE_RAD


def recipe_of(built, environments):
    """
    The recipe of the generated blocks.
    """
    return TrajectoryEngine().recipe([{"row": b["row"], "arrays": b["arrays"]} for b in built["blocks"]], {g["name"]: g for g in environments.values()}, RULES)


def test_the_blocks_measure_back_to_the_recipe_with_wandering_dwells_and_varied_runs(made, built, environments):
    found = recipe_of(built, environments)
    assert abs(found["track"]["lateral_m"]["q50"] / RECIPE["track"]["lateral_m"]["q50"] - 1) < RECIPE_TOLERANCE
    for kind in ("track", "arena"):
        assert abs(found[kind]["tracking_noise_m"] / NOISE_M - 1) < RECIPE_TOLERANCE
        assert found[kind]["still_fraction"] > 0.05
    durations = np.array([run["duration_s"] for run in made["runs"] if run["path_id"] in GOALS])
    assert durations.std() / durations.mean() > MIN_RUN_CV
    track = next(b for b in built["blocks"] if b["row"]["kind"] == "track")
    dwelling = np.flatnonzero(track["arrays"]["phase"] == "dwell")
    longest = max(np.split(dwelling, np.flatnonzero(np.diff(dwelling) > 1) + 1), key=len)
    assert max(np.ptp(track["arrays"]["x"][longest]), np.ptp(track["arrays"]["y"][longest])) > MIN_DWELL_SPAN_M


def test_on_the_perimeter_a_run_leans_toward_the_outer_wall_by_the_recipes_mean(made, environments):
    xy, at = room_of(made, "track")
    inside_runs = np.zeros(len(xy), bool)
    for run in made["runs"]:
        inside_runs[run["frame_start"] - 1 - at.start:run["frame_end"] - at.start] = True
    speed = np.hypot(*np.gradient(xy, axis=0).T) * CAMERA["rate_hz"]
    here = inside_runs & (speed >= RULES["running_floor_m_per_s"])
    signed, perimeter = outward_offset(xy[here, 0], xy[here, 1], environments["track"]["centerline"], environments["track"]["room"])
    expected = RECIPE["track"]["lateral_outward_m"]["perimeter"]["mean"]
    assert abs(signed[perimeter].mean() / expected - 1) < LEAN_TOLERANCE


def test_runs_reverse_at_about_the_recipes_rate_and_a_run_that_reverses_is_not_clean(ten, environments):
    made, built = ten
    found = recipe_of(built, environments)["track"]["run_reversals_per_min"]
    expected = RECIPE["track"]["run_reversals_per_min"]
    assert expected / REVERSAL_FACTOR < found < expected * REVERSAL_FACTOR
    assert any(not run["clean"] for run in made["runs"]) and any(run["clean"] for run in made["runs"])
    reversed_runs = {(b["row"]["block_id"], int(b["arrays"]["run"][k])) for b in built["blocks"] for k in reversal_frames(b, RULES, in_runs=True)}
    for b in built["blocks"]:
        for number in np.unique(b["arrays"]["run"][(b["arrays"]["run"] > 0) & ~b["arrays"]["clean"]]):
            assert (b["row"]["block_id"], int(number)) in reversed_runs


def test_the_arena_walk_keeps_the_recipes_distance_from_the_wall(ten, environments):
    xy, _ = room_of(ten[0], "arena")
    distance = environments["arena"]["params"]["diameter"] / 2 - np.hypot(*(xy - np.array(environments["arena"]["room"]) / 2).T)
    assert abs(np.median(distance) / RECIPE["arena"]["boundary_distance_m"]["q50"] - 1) < RECIPE_TOLERANCE


def test_the_heading_is_tight_at_a_run_wide_when_still_and_seldom_flips(built):
    track = next(b for b in built["blocks"] if b["row"]["kind"] == "track")
    arrays = track["arrays"]
    _, motion, _ = kinematics(arrays["x"], arrays["y"], arrays["heading"], np.zeros(len(arrays["x"]), bool), 60, RULES)
    residual = np.angle(np.exp(1j * (arrays["heading"] - motion)))
    fast, still = arrays["speed"] > FAST_M_PER_S, arrays["speed"] < RULES["running_floor_m_per_s"]
    assert circular_std(residual[fast & np.isfinite(residual)]) < MAX_FAST_SPREAD_RAD
    assert circular_std(residual[still & np.isfinite(residual)]) > MIN_STILL_SPREAD_RAD
    assert np.mean(np.abs(np.angle(np.exp(1j * np.diff(arrays["heading"])))) > np.pi / 2) < MAX_FLIP_SHARE


def test_a_track_that_is_not_the_triple_t_an_arena_that_is_not_a_circle_and_an_empty_track_recipe_are_refused(environments):
    plus = EnvironmentAccess(ENVIRONMENTS).environment("plus_maze")
    with pytest.raises(Invalid, match="triple T alone, plus_maze lacks"):
        GeneratorEngine().session(RECIPE, {**environments, "track": plus}, CAMERA, SEED, {"track": 60.0}, SESSION_ID, DATE)
    with pytest.raises(Invalid, match="circle alone, triple_t is a triple_t"):
        GeneratorEngine().session(RECIPE, {**environments, "arena": environments["track"]}, CAMERA, SEED, {"arena": 60.0}, SESSION_ID, DATE)
    no_goals = {**RECIPE, "track": {**RECIPE["track"], "goal_share": {"1": 0.0, "2": 0.0, "3": 0.0, "4": 0.0}}}
    with pytest.raises(Invalid, match="no outbound runs"):
        GeneratorEngine().session(no_goals, environments, CAMERA, SEED, {"track": 60.0}, SESSION_ID, DATE)
    no_dwells = {**RECIPE, "track": {**RECIPE["track"], "dwell_s": {**RECIPE["track"]["dwell_s"], "goal": q(*[None] * 5)}}}
    with pytest.raises(Invalid, match="no dwells at the goal"):
        GeneratorEngine().session(no_dwells, environments, CAMERA, SEED, {"track": 60.0}, SESSION_ID, DATE)
