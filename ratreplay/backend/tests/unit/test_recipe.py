"""
TrajectoryEngine.recipe on hand made blocks whose statistics are computed by hand: a track block with two trips and an arena block with a pause.
"""

import json

import numpy as np
import pytest

from ratreplay_api.engines.trajectory import RULES, TrajectoryEngine
from ratreplay_api.engines.trajectory.labels import DWELL, FORAGE, OUTBOUND, PAUSE, RETURN

RATE_HZ = 60
FLOOR = RULES["running_floor_m_per_s"]

# The track block, 600 frames (10 s): two trips, each an outbound run, a dwell at the goal, a return run and a dwell at
# the start, the first trip to goal 2 and back on 9, the second to goal 1 and back on 9. Spans are (first, stop) indices.
TRACK_FRAMES = 600
TRACK_RUNS = ((1, 2, 30, 150), (2, 9, 210, 300), (3, 1, 330, 420), (4, 9, 450, 570))
TRACK_TRIPS = ((1, 30, 330), (2, 330, 600))

# The arena block, 300 frames (5 s), one still stretch of 66 frames (1.1 s, over pause_min_s), positions on the corners
# and the centre of the 2 m square the environment's boundary and room are.
ARENA_FRAMES = 300
ARENA_PAUSE = (120, 186)
ENVIRONMENTS = {"e": {"boundary": None, "room": [1.8, 1.8]},
                "square": {"boundary": [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)], "room": [2.0, 2.0]}}


def labels(n_frames, kind):
    """
    Empty label and kinematic arrays of a block of the kind, every frame dwelling or foraging at a still finite position with a finite heading.
    """
    arrays = {name: np.zeros(n_frames) for name in ("x", "y", "heading", "speed", "turn_rate")}
    arrays |= {"trip": np.zeros(n_frames, np.int32), "run": np.zeros(n_frames, np.int32), "path_id": np.zeros(n_frames, np.int16),
               "phase": np.full(n_frames, FORAGE if kind == "arena" else DWELL, "U8")}
    return arrays


def block(kind, arrays, environment="e"):
    """
    A block of the kind with the arrays and the row fields the recipe reads.
    """
    n = len(arrays["x"])
    return {"row": {"kind": kind, "environment": environment, "n_frames": n, "duration_s": n / RATE_HZ, "rate_hz": RATE_HZ}, "arrays": arrays}


@pytest.fixture
def track():
    """
    The track block with its speed a ramp from 0 to 0.599 m/s over the frames, so the quantiles are known.
    """
    arrays = labels(TRACK_FRAMES, "track")
    arrays["speed"] = np.arange(TRACK_FRAMES) / 1000.0
    arrays["turn_rate"] = np.where(np.arange(TRACK_FRAMES) % 2 == 0, 1.0, -3.0)
    for number, path, first, stop in TRACK_RUNS:
        arrays["run"][first:stop], arrays["path_id"][first:stop] = number, path
        arrays["phase"][first:stop] = OUTBOUND if path in RULES["outbound_paths"] else RETURN
    for number, first, stop in TRACK_TRIPS:
        arrays["trip"][first:stop] = number
    arrays["phase"][500:560] = PAUSE
    return block("track", arrays)


@pytest.fixture
def arena():
    """
    The arena block: a still stretch, and the position stepping over the corners and the centre of the 2 m square so the grid and the boundary distance are known.
    """
    arrays = labels(ARENA_FRAMES, "arena")
    arrays["speed"][:] = FLOOR * 2
    arrays["speed"][slice(*ARENA_PAUSE)] = 0.0
    corners = np.array([(0.0, 0.0), (2.0, 0.0), (0.0, 2.0), (2.0, 2.0), (1.0, 1.0)])
    at = corners[np.arange(ARENA_FRAMES) % len(corners)]
    arrays["x"], arrays["y"] = at[:, 0], at[:, 1]
    return block("arena", arrays, environment="square")


def recipe_of(blocks):
    """
    The recipe of the blocks over the test environments under the default rules.
    """
    return TrajectoryEngine().recipe(blocks, ENVIRONMENTS, RULES)


def test_empty_and_absent_kind(arena):
    """
    No blocks give {}, and a list with only arena blocks has no track key.
    """
    assert recipe_of([]) == {}
    assert set(recipe_of([arena])) == {"arena"}


def test_output_is_json_ready(track, arena):
    """
    The recipe serialises as JSON without a numpy scalar anywhere.
    """
    json.dumps(recipe_of([track, arena]))


def test_track_counts_speed_and_turn_rate(track):
    """
    The counts, the speed quantiles of the known ramp, the signed turn rate quantiles and its absolute mean, and the still fraction.
    """
    found = recipe_of([track])["track"]
    assert found["counts"] == {"blocks": 1, "frames": TRACK_FRAMES, "seconds": 10.0}
    assert found["speed"]["q50"] == pytest.approx(np.median(np.arange(TRACK_FRAMES) / 1000.0))
    assert found["speed"]["q05"] == pytest.approx(np.percentile(np.arange(TRACK_FRAMES) / 1000.0, 5))
    assert found["speed"]["mean"] == pytest.approx(0.2995)
    assert found["turn_rate"]["mean"] == pytest.approx(-1.0)
    assert found["turn_rate_abs_mean"] == pytest.approx(2.0)
    assert found["still_fraction"] == pytest.approx(30 / TRACK_FRAMES)


def test_track_runs_dwells_trips_and_goals(track):
    """
    Run counts and durations per path, dwell durations at the goal and the start by the run before, trips per minute, the goal share and the phase share.
    """
    found = recipe_of([track])["track"]
    assert found["runs"]["2"]["count"] == 1 and found["runs"]["2"]["duration_s"]["q50"] == pytest.approx(2.0)
    assert found["runs"]["1"]["count"] == 1 and found["runs"]["1"]["duration_s"]["mean"] == pytest.approx(1.5)
    assert found["runs"]["9"]["count"] == 2 and found["runs"]["9"]["duration_s"]["mean"] == pytest.approx(1.75)
    assert found["dwell_s"]["goal"]["mean"] == pytest.approx(0.75)
    assert found["dwell_s"]["goal"]["q50"] == pytest.approx(0.75)
    assert found["dwell_s"]["start"]["q50"] == pytest.approx((30 / RATE_HZ + 30 / RATE_HZ) / 2)
    assert found["trips_per_min"] == pytest.approx(2 / (10 / 60))
    assert found["goal_share"] == {"1": 0.5, "2": 0.5, "3": 0.0, "4": 0.0}
    assert found["phase_share"]["outbound"] == pytest.approx(210 / TRACK_FRAMES)
    assert found["phase_share"]["return"] == pytest.approx(150 / TRACK_FRAMES)
    assert found["phase_share"]["pause"] == pytest.approx(60 / TRACK_FRAMES)
    assert found["phase_share"]["dwell"] == pytest.approx(180 / TRACK_FRAMES)
    assert found["pauses"]["per_min"] == pytest.approx(6.0)
    assert found["pauses"]["duration_s"]["q50"] == pytest.approx(1.0)


def test_heading_spread_is_zero_when_heading_follows_motion():
    """
    A block running along a straight line with the heading equal to the direction of motion has a heading spread of 0, a heading off by a constant also 0, and a frame whose step is zero adds no residual whatever its heading.
    """
    arrays = labels(100, "track")
    arrays["x"] = np.arange(100) * 0.01
    arrays["speed"][:] = 0.6
    assert recipe_of([block("track", arrays)])["track"]["heading_spread_rad"] == pytest.approx(0.0)
    arrays["heading"][:] = 1.0
    assert recipe_of([block("track", arrays)])["track"]["heading_spread_rad"] == pytest.approx(0.0)
    arrays["x"][50] = arrays["x"][49]
    arrays["heading"][49] = np.pi
    assert recipe_of([block("track", arrays)])["track"]["heading_spread_rad"] == pytest.approx(0.0)


def test_arena_pauses_boundary_and_grid(arena):
    """
    The pauses as still stretches with their rate and duration, the distance to the environment's boundary, the occupancy grid over its room summing to 1 with the corners and the centre filled, and the phase share, which has no pause since the labels paint none in the arena.
    """
    found = recipe_of([arena])["arena"]
    assert found["counts"]["seconds"] == pytest.approx(5.0)
    assert found["pauses"]["per_min"] == pytest.approx(12.0)
    assert found["pauses"]["duration_s"]["mean"] == pytest.approx(1.1)
    assert found["still_fraction"] == pytest.approx(66 / ARENA_FRAMES)
    assert found["environment"] == "square"
    assert found["boundary_distance_m"]["q95"] == pytest.approx(1.0)
    assert found["boundary_distance_m"]["q25"] == pytest.approx(0.0)
    assert found["boundary_distance_m"]["mean"] == pytest.approx(0.2)
    grid = np.array(found["occupancy_grid"])
    assert grid.shape == (10, 10) and grid.sum() == pytest.approx(1.0)
    assert grid[0, 0] == pytest.approx(60 / ARENA_FRAMES) and grid[0, 9] == pytest.approx(60 / ARENA_FRAMES)
    assert grid[9, 0] == pytest.approx(60 / ARENA_FRAMES) and grid[9, 9] == pytest.approx(60 / ARENA_FRAMES)
    assert grid[5, 5] == pytest.approx(60 / ARENA_FRAMES)
    assert found["phase_share"] == {"forage": pytest.approx(1.0), "pause": 0.0}


def test_two_blocks_pool_frames_and_count_stretches_per_block(track):
    """
    Two copies of the track block double the counts, runs and trips, and keep the per minute rates and quantiles.
    """
    one = recipe_of([track])["track"]
    two = recipe_of([track, track])["track"]
    assert two["counts"] == {"blocks": 2, "frames": 2 * TRACK_FRAMES, "seconds": 20.0}
    assert two["runs"]["9"]["count"] == 4 and two["trips_per_min"] == pytest.approx(one["trips_per_min"])
    assert two["speed"] == one["speed"] and two["pauses"]["per_min"] == pytest.approx(one["pauses"]["per_min"])
