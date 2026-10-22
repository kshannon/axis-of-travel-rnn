"""
The axis of travel measures on a hand made hidden state with a known structure, run along the triple-T's corridors.
"""

import numpy as np
import pytest

from axis_of_travel_rnn import analysis
from proj_helpers.paths import repo_root

from .handmade import corridor_travel, wandering

THRESHOLDS = "configs/analysis/thresholds.yaml"
EAST_WEST = ("cross_e", "cross_w", "bottom_w", "bottom_e", "approach_ee")
NORTH_SOUTH = ("stem", "up_e", "up_w", "side_w", "side_e")
REPEATS = 4

# Units as functions of a frame's direction of travel (0 E, 1 W, 2 N, 3 S) and segment, the way a tuned unit would respond.
UNITS = {
    "axis_east_west": lambda d, s: np.where(d < 2, 1.0, 0.2),
    "axis_north_south": lambda d, s: np.where(d >= 2, 1.0, 0.2),
    "east": lambda d, s: np.where(d == 0, 1.0, 0.1),
    "place": lambda d, s: np.where(s == "cross_e", 1.0, 0.1),
    "silent": lambda d, s: np.zeros(len(d)),
}
ROW = {name: i for i, name in enumerate(UNITS)}


@pytest.fixture(scope="module")
def found():
    thr = analysis.load_thresholds(repo_root() / THRESHOLDS)
    plan = [(name, forward) for _ in range(REPEATS) for name in EAST_WEST + NORTH_SOUTH for forward in (True, False)]
    block, direction, segment = corridor_travel(plan)
    noise = np.random.default_rng(0).normal(0.0, 0.05, (len(direction), len(UNITS)))
    hidden = np.column_stack([unit(direction, segment) for unit in UNITS.values()]) + noise
    passes = analysis.pool_passes([block], [analysis.scale(hidden, analysis.fit_scaling(hidden))], thr)
    rng = np.random.default_rng(0)
    return {"thr": thr, "passes": passes, "direction": analysis.direction_test(passes, thr, rng),
            "axis": analysis.axis_test(passes, thr, rng)}


def test_passes_carry_the_segment_and_direction_they_were_run_in(found):
    passes = found["passes"]
    assert len(passes["segment"]) == 2 * REPEATS * (len(EAST_WEST) + len(NORTH_SOUTH))
    names = np.array(passes["names"])[passes["segment"]]
    assert set(names) == set(EAST_WEST + NORTH_SOUTH)
    assert np.array_equal(passes["direction"] // 2, np.isin(names, NORTH_SOUTH).astype(int))


def test_axis_units_are_axis_units_and_not_direction_units(found):
    assert found["axis"][ROW["axis_east_west"]].tolist() == [True, False]
    assert found["axis"][ROW["axis_north_south"]].tolist() == [False, True]
    assert not found["direction"][[ROW["axis_east_west"], ROW["axis_north_south"]]].any()


def test_a_direction_unit_is_not_an_axis_unit_and_a_place_unit_is_neither(found):
    assert found["direction"][ROW["east"]].tolist() == [True, False] and not found["axis"][ROW["east"]].any()
    for name in ("place", "silent"):
        assert not found["direction"][ROW[name]].any() and not found["axis"][ROW[name]].any()
    assert analysis.population_distances(found["passes"])["opposite_over_cross"] < 1


def test_an_axis_tuned_unit_persists_in_the_arena_and_noise_does_not(found):
    arena = wandering(3000, seed=2, rate_hz=20, kind="arena")
    heading = arena["arrays"]["heading"]
    noise = np.random.default_rng(1).uniform(0.0, 1.0, len(heading))
    hidden = np.column_stack([np.abs(np.cos(heading)), noise])
    persists = analysis.arena_test([arena], [hidden], np.array([True, True]), found["thr"], np.random.default_rng(0))
    assert persists.tolist() == [True, False]
