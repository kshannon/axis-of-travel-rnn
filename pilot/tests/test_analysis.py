"""
The analysis: fake units with known tuning through the real tests, the null, the population measure, the decoders.
"""

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter1d

from pilot import worlds
from pilot.analysis import (
    analyse_units, arena_test, axis_of, axis_test, cell_labels, cell_masks, cell_means, decode_heading, decode_position,
    direction_null, direction_test, fit_scaling, fractions, load_thresholds, mean_by_cell, pca_scores, pool_passes,
    population_distances, ridge_r2, scale, selectivity_null, session_passes,
)
from pilot.config import CORRIDOR, ROOM, SMOKE
from pilot.worlds import classify_segment

THR = load_thresholds()  # the pre-registered numbers, unchanged
SESSIONS = worlds.load_sessions(SMOKE, worlds.make_layouts(SMOKE))
LOOP, FIELD = SESSIONS["loop"], SESSIONS["open_field"]


def east_peak(s):
    return np.exp(3 * (np.cos(s.heading) - 1))


def faint_east(s):
    unit = 0.01 * east_peak(s)
    unit[0] += 1.0  # one burst sets the range, so after scaling the tuning is faint
    return unit


def faint_east_west(s):
    unit = 0.01 * np.abs(np.cos(s.heading))
    unit[0] += 1.0
    return unit


# Fake units as functions of a session's position and heading, the way a tuned unit would respond.
UNITS = {
    "hd_east": east_peak,
    "hd_north": lambda s: np.exp(3 * (np.sin(s.heading) - 1)),
    "place": lambda s: np.exp(-((s.pos - [ROOM[0] / 2, CORRIDOR / 2]) ** 2).sum(axis=1) / (2 * 0.1 ** 2)),
    "east_west": lambda s: np.abs(np.cos(s.heading)),
    "north_south": lambda s: np.abs(np.sin(s.heading)),
    "east_west_loop_only": lambda s: np.abs(np.cos(s.heading)) * (s.world == "loop"),
    "east_west_bottom_heavy": lambda s: np.abs(np.cos(s.heading)) * np.where(classify_segment(s.pos) == 0, 1, 0.3),
    "faint_east": faint_east,
    "faint_east_west": faint_east_west,
    "silent": lambda s: np.zeros(len(s.t)),
}
ROW = {name: i for i, name in enumerate(UNITS)}


def hidden_of(sessions):
    return [np.column_stack([unit(s) for unit in UNITS.values()]) for s in sessions]


@pytest.fixture(scope="module")
def result():
    return analyse_units(LOOP, hidden_of(LOOP), FIELD, hidden_of(FIELD), THR, np.random.default_rng(0))


def loop_passes(result):
    return pool_passes(LOOP, [scale(h, result["scaling"]) for h in hidden_of(LOOP)], THR)


def test_scaling_maps_each_unit_to_the_unit_range_and_is_reusable():
    h = np.array([[1.0, 5.0, -2.0], [3.0, 5.0, 2.0], [2.0, 5.0, 0.0]])
    scaling = fit_scaling(h)
    assert np.allclose(scale(h, scaling), [[0, 0, 0], [1, 0, 1], [0.5, 0, 0.5]])  # the constant unit goes to 0
    assert np.allclose(scale(np.array([[5.0, 5.0, 6.0]]), scaling), [[2.0, 0, 2.0]])  # another array, same scaling


def test_cells_are_named_in_order_and_passes_are_maximal_runs_of_one_cell():
    mid_x, mid_y, half = ROOM[0] / 2, ROOM[1] / 2, CORRIDOR / 2
    pos = np.array([[mid_x, half], [mid_x, half], [mid_x, ROOM[1] - half], [half, mid_y], [ROOM[0] - half, mid_y],
                    [half, half], [mid_x, half]])
    heading = np.array([0.0, np.pi, 0.0, np.pi / 2, -np.pi / 2, 0.0, 0.0])
    speed = np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.01])
    labels = cell_labels(cell_masks(pos, heading, speed, THR))
    assert labels.tolist() == [0, 1, 2, 4, 7, -1, -1]  # bottom_E, bottom_W, top_E, left_N, right_S, a corner, too slow

    labels = np.array([-1, 0, 0, 0, 1, 1, -1, 0, 0, -1, -1, 4])
    masks = labels[:, None] == np.arange(8)
    h = np.arange(24.0).reshape(12, 2)
    means, cells, steps = session_passes(h, masks)
    assert cells.tolist() == [0, 1, 0, 4] and steps.tolist() == [3, 2, 2, 1]
    assert np.allclose(means[0], h[1:4].mean(axis=0)) and np.allclose(means[3], h[11])
    by_step = cell_means(h, masks)
    assert np.allclose(by_step[:, 0], h[[1, 2, 3, 7, 8]].mean(axis=0)) and np.isnan(by_step[:, 7]).all()


def test_pass_means_weighted_by_steps_are_the_cell_means_of_the_steps():
    hidden = [s.place for s in LOOP]
    masks = np.concatenate([cell_masks(s.pos, s.heading, s.speed, THR) for s in LOOP])
    assert np.allclose(mean_by_cell(*pool_passes(LOOP, hidden, THR)), cell_means(np.concatenate(hidden), masks))


def test_hd_like_units_are_direction_units_and_not_axis_units(result):
    for name, direction in (("hd_east", [True, False]), ("hd_north", [False, True])):
        assert result["direction"][ROW[name]].tolist() == direction
        assert not result["axis"][ROW[name]].any()


def test_place_like_unit_is_neither(result):
    assert not result["direction"][ROW["place"]].any() and not result["axis"][ROW["place"]].any()


def test_east_plus_west_unit_is_an_axis_unit_that_persists_in_the_arena(result):
    assert not result["direction"][ROW["east_west"]].any()
    assert axis_of(result["axis"])[ROW["east_west"]] == 0 and axis_of(result["axis"])[ROW["north_south"]] == 1
    assert result["persists"][ROW["east_west"]] and result["persists"][ROW["north_south"]]


def test_axis_unit_active_only_on_the_loop_is_released_in_the_arena(result):
    assert axis_of(result["axis"])[ROW["east_west_loop_only"]] == 0
    assert not result["persists"][ROW["east_west_loop_only"]]


def test_silent_unit_passes_nothing(result):
    assert not result["direction"][ROW["silent"]].any() and not result["axis"][ROW["silent"]].any()
    assert not result["persists"][ROW["silent"]]


def test_each_rule_removes_the_units_it_is_for(result):
    """
    Relaxing one threshold lets through exactly the unit that rule exists to remove, so the rule is what held it back.
    """
    passes, rng = loop_passes(result), np.random.default_rng(1)
    assert not result["axis"][ROW["east_west_bottom_heavy"]].any() and not result["direction"][ROW["faint_east"]].any()
    balance_off = axis_test(passes, {**THR, "balance_index_max": 1.01}, rng)
    assert balance_off[ROW["hd_east"]].tolist() == [True, False]  # rule 2 removes direction-like units
    general_off = axis_test(passes, {**THR, "place_general_min": 0.0}, rng)
    assert general_off[ROW["east_west_bottom_heavy"]].tolist() == [True, False]  # rule 3 removes place-like units
    floor_off = direction_test(passes, {**THR, "activity_floor": 0.0}, rng)
    assert floor_off[ROW["faint_east"]].tolist() == [True, False]  # the floor removes near-silent units
    assert not result["axis"][ROW["faint_east_west"]].any()
    axis_floor_off = axis_test(passes, {**THR, "activity_floor": 0.0}, rng)
    assert axis_floor_off[ROW["faint_east_west"]].tolist() == [True, False]  # and from the axis test too


def passes_of(values):
    """
    The passes of one unit from the values of its passes in each of the 8 cells, every pass one step long.
    """
    cells = np.repeat(np.arange(8), [len(v) for v in values])
    return np.concatenate(values)[:, None], cells, np.ones(len(cells))


def by_levels(bottom, top, left=(0.5, 0.5), right=(0.5, 0.5), n=10):
    """
    A unit with n passes in each cell at these (first, second direction) levels per segment, plus a little noise.
    """
    noise = np.random.default_rng(0)
    return passes_of([level + 0.02 * noise.standard_normal(n) for level in (*bottom, *top, *left, *right)])


def test_a_direction_unit_prefers_the_same_direction_on_both_segments():
    rng = np.random.default_rng(0)
    assert direction_test(by_levels((0.9, 0.3), (0.9, 0.3)), THR, rng)[0, 0]
    assert not direction_test(by_levels((0.9, 0.3), (0.3, 0.9)), THR, rng)[0, 0]  # east on the bottom, west on the top


def test_a_unit_inside_the_null_fails_although_it_meets_the_fixed_limits():
    """
    Two passes per cell cannot show a tuning: these units pass every fixed limit, only the null stops them.
    """
    rng, no_null = np.random.default_rng(0), {**THR, "null_percentile": 0}
    direction = passes_of([[1.0, 0.6], [0.3, 0.4], [1.0, 0.6], [0.3, 0.4]] + [[0.5, 0.5]] * 4)
    axis = passes_of([[1.0, 0.2]] * 4 + [[0.4, 0.16]] * 4)
    assert not direction_test(direction, THR, rng)[0, 0] and direction_test(direction, no_null, rng)[0, 0]
    assert not axis_test(axis, THR, rng)[0, 0] and axis_test(axis, no_null, rng)[0, 0]


def test_the_direction_null_shuffles_directions_within_each_segment():
    """
    A unit that differs between segments but not between directions has a direction null near 0.
    """
    unit = by_levels((0.9, 0.9), (0.12, 0.12), (0.5, 0.5), (0.2, 0.2))
    assert (direction_null(unit, THR, np.random.default_rng(0))[1] < 0.1).all()


class RecordingRng:
    def __init__(self):
        self.rng, self.shifts = np.random.default_rng(0), []

    def integers(self, low, high):
        self.shifts.append((low, high))
        return self.rng.integers(low, high)


def test_arena_shifts_keep_the_minimum_shift_from_both_ends_of_a_session():
    rng = RecordingRng()
    arena_test(FIELD, [np.abs(np.cos(s.heading))[:, None] for s in FIELD], np.ones(1, dtype=bool), THR, rng)
    least, steps = round(THR["min_shift_s"] / (FIELD[0].t[1] - FIELD[0].t[0])), len(FIELD[0].t)
    assert rng.shifts and all(shift == (least, steps - least + 1) for shift in rng.shifts)


def test_units_are_scaled_over_both_worlds_together():
    loop_h = [np.abs(np.cos(s.heading))[:, None] for s in LOOP]
    field_h = [5 * np.abs(np.cos(s.heading))[:, None] for s in FIELD]
    span = analyse_units(LOOP, loop_h, FIELD, field_h, THR, np.random.default_rng(0))["scaling"][1]
    assert span[0] > 4  # the range of the open field, not the loop's 1


def test_nulls_give_about_one_percent_false_positives_on_units_unrelated_to_the_labels():
    rng, n = np.random.default_rng(0), 500
    noise = lambda sessions: [gaussian_filter1d(rng.standard_normal((len(s.t), n)), 20, axis=0, mode="wrap")
                              for s in sessions]
    loop_h, field_h = noise(LOOP), noise(FIELD)
    scaling = fit_scaling(np.concatenate(loop_h + field_h))
    loop_h, field_h = [scale(h, scaling) for h in loop_h], [scale(h, scaling) for h in field_h]
    passes = pool_passes(LOOP, loop_h, THR)
    for statistic, cutoff in (direction_null(passes, THR, rng), selectivity_null(passes, THR, rng)):
        assert 0.002 < (statistic > cutoff).mean() < 0.03
    assert not direction_test(passes, THR, rng).any() and not axis_test(passes, THR, rng).any()
    assert arena_test(FIELD, field_h, np.ones(n, dtype=bool), THR, rng).mean() < 0.05
    assert not arena_test(FIELD, field_h, np.zeros(n, dtype=bool), THR, rng).any()


def test_population_distances_read_the_right_pairs():
    direction_like = np.array([[1, 0, 1, 0, 1, 0, 1, 0], [0, 1, 0, 1, 1, 0, 1, 0]], dtype=float)
    d = population_distances(direction_like)  # same direction, same vector, on parallel segments
    assert np.isclose(d["opposite"], np.sqrt(2)) and d["parallel"] == 0 and np.isclose(d["cross"], 1)
    assert np.isclose(d["opposite_over_cross"], np.sqrt(2)) and d["parallel_over_cross"] == 0
    axis_like = np.array([[1, 1, 1, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 1, 1, 1]], dtype=float)
    d = population_distances(axis_like)  # both directions, one vector, per axis
    assert d["opposite"] == 0 and d["parallel"] == 0 and np.isclose(d["cross"], np.sqrt(2))


def test_pca_scores_are_ordered_by_variance_and_keep_the_moving_steps():
    s = LOOP[0]
    h = np.random.default_rng(0).standard_normal((len(s.t), 5)) * [1, 5, 2, 0.5, 3]
    out = pca_scores(h, s.pos, s.heading, s.speed, THR)
    moving = (s.speed > THR["moving_speed_m_s"]).sum()
    assert out["scores"].shape == (moving, 3) and len(out["heading"]) == len(out["segment"]) == moving
    assert np.allclose(out["explained"], np.array([25, 9, 4]) / 39.25, atol=0.03)


def test_ridge_decoder_recovers_a_linear_map_and_scores_nothing_on_noise():
    rng = np.random.default_rng(0)
    h = rng.standard_normal((2000, 20))
    y = h @ rng.standard_normal((20, 2)) + 3.0
    assert ridge_r2(h[:1000], y[:1000], h[1000:], y[1000:]) > 0.99
    assert ridge_r2(h[:1000], rng.standard_normal((1000, 2)), h[1000:], rng.standard_normal((1000, 2))) < 0.05


def test_decoders_read_position_and_heading_from_the_cells_that_encode_them():
    fit, test = FIELD[:3], FIELD[3:]
    cat = lambda group, name: np.concatenate([getattr(s, name) for s in group])
    assert decode_position(cat(fit, "place"), cat(fit, "pos"), cat(test, "place"), cat(test, "pos")) > 0.5
    assert decode_heading(cat(fit, "hd"), cat(fit, "heading"), cat(test, "hd"), cat(test, "heading")) > 0.9
    assert decode_heading(cat(fit, "place"), cat(fit, "heading"), cat(test, "place"), cat(test, "heading")) < 0.5
    cosine_fit, cosine_test = (np.cos(cat(group, "heading"))[:, None] for group in (fit, test))
    half = decode_heading(cosine_fit, cat(fit, "heading"), cosine_test, cat(test, "heading"))
    assert 0.4 < half < 0.6  # a state holding only cos(heading) explains cos but not sin


def test_fractions_separate_released_axis_units_of_axis_units_and_of_all_units():
    direction = np.array([[True, False], [False, False], [False, True], [False, False]])
    axis = np.array([[False, False], [True, False], [False, True], [True, False]])
    persists = np.array([False, True, False, False])
    out = fractions(direction, axis, persists)
    assert out == {"direction": 0.5, "axis": 0.75, "released_of_axis": 2 / 3, "released": 0.5}
    assert np.isnan(fractions(direction, np.zeros((4, 2), dtype=bool), persists)["released_of_axis"])
