"""
The pilot's worlds: sessions, save and load, steering, the hole, HD peaks, segments, cache key and splits.
"""

from dataclasses import replace

import numpy as np
import pytest

from pilot import worlds
from pilot.config import CORRIDOR, DATA_KEYS, DRIFT_RATIO, PILOT, REPEL_FRACTION, ROOM, SMOKE, WORLDS
from pilot.worlds import (
    SEGMENTS, SessionData, bleed, cell_seconds, classify_segment, data_hash, hd_rates, hole_bounds, in_hole, make_agent,
    make_layout, make_layouts, n_sessions, place_rates, run_agent, simulate, split_of, travel_direction,
)
from ratinabox.Neurons import HeadDirectionCells

CFG = {**SMOKE, "session_s": 20.0, "burn_in_s": 2.0}
LAYOUTS = make_layouts(CFG)


def test_session_shapes_and_no_position_in_the_hole():
    session = simulate(CFG, LAYOUTS["loop"], seed=7)
    steps = round(CFG["session_s"] / CFG["dt"])
    assert session.pos.shape == (steps, 2)
    for field in (session.t, session.heading, session.speed, session.turn_rate):
        assert field.shape == (steps,)
    assert session.place.shape == (steps, CFG["place_n"]) and session.place.dtype == np.float32
    assert session.hd.shape == (steps, CFG["hd_n"]) and session.hd.dtype == np.float32
    assert 0.0 <= session.place.min() and session.place.max() <= 1.0
    assert not in_hole(session.pos).any()
    assert (session.pos >= 0).all() and (session.pos <= np.array(ROOM)).all()


def test_session_channels_match_the_path():
    """
    Heading, speed, turn rate, time and the cell rates of a session each agree with the path they come from.
    """
    layout, dt = LAYOUTS["loop"], CFG["dt"]
    session = simulate(CFG, layout, seed=7)
    step = np.diff(session.pos, axis=0)
    moving = session.speed[1:] > 0.03
    travel = np.arctan2(step[:, 1], step[:, 0])
    assert np.cos(travel - session.heading[1:])[moving].mean() > 0.8  # heading is the direction of travel
    assert np.allclose(session.speed[1:], np.linalg.norm(step, axis=1) / dt)
    heading_change = np.angle(np.exp(1j * np.diff(session.heading))) / dt
    assert np.corrcoef(session.turn_rate[1:], heading_change)[0, 1] > 0.2  # turn rate has the sign of the turning
    assert np.isclose(session.t[0], dt) and np.isclose(session.t[-1], CFG["session_s"])
    some = np.arange(0, len(session.t), 40)
    assert np.allclose(session.place[some], place_rates(CFG, layout, session.pos[some]), atol=1e-6)
    assert np.allclose(session.hd[some], hd_rates(CFG, layout, session.heading[some]), atol=1e-6)
    assert np.isclose(make_agent(CFG, "loop").speed_mean * np.sqrt(np.pi / 2), CFG["speed_mean"])  # trap 3


def test_same_seed_gives_identical_output():
    layout = LAYOUTS["loop"]
    first, again, other = simulate(CFG, layout, 3), simulate(CFG, layout, 3), simulate(CFG, layout, 4)
    for name in ("t", "pos", "heading", "speed", "turn_rate", "place", "hd"):
        assert np.array_equal(getattr(first, name), getattr(again, name))
    assert not np.array_equal(first.pos, other.pos)


def test_steered_smoke_session_visits_every_segment_in_both_directions():
    seed = SMOKE["session_seed_base"]["loop"]
    path = run_agent(SMOKE, "loop", seed, repel=CORRIDOR * REPEL_FRACTION, ratio=DRIFT_RATIO)
    seconds = cell_seconds(path["pos"], path["heading"], path["speed"], SMOKE["dt"])
    assert seconds.min() >= 1.0, seconds


def test_layouts_are_deterministic():
    np.random.seed(123)  # the global generator must not matter
    again = make_layouts(CFG)
    for world in WORLDS:
        assert np.array_equal(again[world].place_centres, LAYOUTS[world].place_centres)


def test_session_save_and_load_round_trip(tmp_path):
    session = simulate(CFG, LAYOUTS["open_field"], seed=7)
    session.save(tmp_path / "sessions" / "session.npz")
    loaded = SessionData.load(tmp_path / "sessions" / "session.npz")
    for name, value in vars(session).items():
        again = getattr(loaded, name)
        assert np.array_equal(value, again) and np.asarray(value).dtype == np.asarray(again).dtype, name
    assert [path.name for path in (tmp_path / "sessions").iterdir()] == ["session.npz"]  # no part file left behind


def test_no_place_cell_centre_in_the_hole():
    for seed in range(5):
        assert not in_hole(make_layout("loop", CFG, seed).place_centres).any()


def test_place_cells_do_not_bleed_across_the_hole():
    x0, _, y0, _ = hole_bounds()
    centres = np.array([[x0 - 0.04, y0 + 0.08]])  # in the left segment, next to the bottom left corner of the hole
    corner_cut = np.array([[x0 + 0.08, y0 - 0.04]])  # in the bottom segment; the line to it runs through the hole
    loop = replace(LAYOUTS["loop"], place_centres=centres)
    field = replace(LAYOUTS["open_field"], place_centres=centres)
    assert place_rates(CFG, field, corner_cut)[0, 0] > 0.01  # without walls the field reaches it
    assert place_rates(CFG, loop, corner_cut)[0, 0] == 0.0
    assert place_rates(CFG, loop, centres)[0, 0] > 0.99  # intact where there is line of sight
    probes = np.random.default_rng(0).uniform([0, 0], ROOM, size=(300, 2))
    probes = probes[~in_hole(probes)]
    n_through, n_reached, worst = bleed(CFG, LAYOUTS["loop"], probes)
    assert n_through > 0 and worst == 0.0


def test_head_direction_cells_have_one_peak_at_the_preferred_direction():
    layout = LAYOUTS["open_field"]
    preferred = HeadDirectionCells(make_agent(CFG, "open_field"), params={"n": layout.n_hd}).preferred_angles
    angles = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    rates = hd_rates(CFG, layout, angles)
    for cell, angle in enumerate(preferred):
        curve = rates[:, cell]
        peak = angles[np.argmax(curve)]
        assert abs(np.angle(np.exp(1j * (peak - angle)))) <= np.deg2rad(1)
        assert curve.max() > 0.99
        assert np.sum((curve > np.roll(curve, 1)) & (curve >= np.roll(curve, -1))) == 1


def test_segment_classifier_and_travel_direction():
    mid_x, mid_y, half = ROOM[0] / 2, ROOM[1] / 2, CORRIDOR / 2
    middles = np.array([[mid_x, half], [mid_x, ROOM[1] - half], [half, mid_y], [ROOM[0] - half, mid_y]])
    corners = np.array([[half, half], [ROOM[0] - half, half], [half, ROOM[1] - half], [ROOM[0] - half, ROOM[1] - half]])
    centre = np.array([[mid_x, mid_y]])
    edge = np.array([[CORRIDOR, half]])  # on the boundary between the bottom segment and the bottom left corner
    assert [SEGMENTS[s] for s in classify_segment(middles)] == ["bottom", "top", "left", "right"]
    assert (classify_segment(corners) == -1).all()
    assert classify_segment(centre)[0] == -1 and classify_segment(edge)[0] == -1 and in_hole(centre)[0]
    segment = classify_segment(np.vstack([middles, corners]))
    heading = np.array([0.1, np.pi - 0.1, np.pi / 2 + 0.1, -np.pi / 2, 0.0, 0.0, 0.0, 0.0])
    assert list(travel_direction(heading, segment)) == [1, -1, 1, -1, 0, 0, 0, 0]
    assert travel_direction(np.array([np.pi / 2]), np.array([0]))[0] == 0  # across the corridor


def changed(value):
    """
    A different value of the same kind, for a setting that is a number, a string or a dict of them.
    """
    if isinstance(value, dict):
        return {key: changed(item) for key, item in value.items()}
    return value + "x" if isinstance(value, str) else value + 1


@pytest.mark.parametrize("key", DATA_KEYS)
def test_data_hash_changes_with_each_data_key(key):
    assert data_hash({**SMOKE, key: changed(SMOKE[key])}) != data_hash(SMOKE)


def test_data_hash_follows_the_room_and_steering_but_not_a_training_setting():
    folder = data_hash(SMOKE)
    assert data_hash({**SMOKE, "max_epochs": 99, "n_hidden": 64}) == folder
    for name in ("ROOM", "CORRIDOR", "DRIFT_RATIO", "REPEL_FRACTION", "WAYPOINT_RADIUS", "MEAN_LAPS", "STEER_SPEED"):
        old = getattr(worlds, name)
        setattr(worlds, name, tuple(1.01 * v for v in old) if isinstance(old, tuple) else 1.01 * old)
        try:
            assert data_hash(SMOKE) != folder, name
        finally:
            setattr(worlds, name, old)


@pytest.mark.parametrize("cfg, first_val, first_test, n", [(PILOT, 14, 16, 20), (SMOKE, 2, 3, 4)],
                         ids=["pilot", "smoke"])
def test_split_of_boundaries(cfg, first_val, first_test, n):
    assert n_sessions(cfg) == n
    indices = (0, first_val - 1, first_val, first_test - 1, first_test, n - 1)
    assert [split_of(cfg, i) for i in indices] == ["train", "train", "val", "val", "test", "test"]
