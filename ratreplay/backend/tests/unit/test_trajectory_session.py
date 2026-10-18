"""
TrajectoryEngine.funnel and session over the synthetic fixtures, in parity with the processor, which is imported here as the oracle and nowhere else in the engine.
"""

from pathlib import Path

import numpy as np
import process_lab_data.__main__ as processor
import pytest
from axis_of_travel_rnn import trajectory
from fixtures import S1, S6
from process_lab_data import frame as old_frame
from process_lab_data import select

from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.trajectory import RULES, TrajectoryEngine
from ratreplay_api.engines.trajectory import heading as new_heading
from ratreplay_api.utilities.errors import Invalid

ENVIRONMENTS = Path(__file__).resolve().parents[4] / "configs" / "environments"
SESSION_KEYS = {"rules", "session_id", "rate_hz", "n_frames", "epochs", "runs", "frame", "warnings", "kinematics", "heading_spans",
                "cut_points", "margins", "stretches", "initial_blocks", "occupancy", "stops"}
BLOCK_KEYS = ("block_id", "epoch", "environment", "frame_start", "frame_end")
STILL_FRAMES, LOST_FRAMES = slice(2999, 3399), slice(3049, 3299)
CUT_KEYS = ("pauses", "jumps", "gaps", "margins")


def loaded(transformed, sid):
    """
    The session as TransformedAccess gives it, with writable copies of its arrays, and the geometry of every environment by name.
    """
    found = TransformedAccess(transformed).session(sid)
    access = EnvironmentAccess(ENVIRONMENTS)
    return {**found, "arrays": {name: values.copy() for name, values in found["arrays"].items()}}, {n: access.environment(n) for n in access.environments()}


def processor_epochs(transformed, sid):
    """
    The epochs the processor's funnel selects for the session.
    """
    epochs, _ = select.funnel(TransformedAccess(transformed).sessions(), None)
    return [e for e in epochs if e["session_id"] == sid]


def processor_selected(epochs):
    """
    The epochs the processor cuts into blocks: the arena and track ones under its condition.
    """
    return [e for e in epochs if e["epoch"] in select.EPOCHS and e["condition"] == select.CONDITION]


def processor_cuts(frames, epochs, max_gap, rate_hz):
    """
    The processor's pause and jump frames, gap spans and margins over the selected epochs, merged.
    """
    merged = {key: [] for key in CUT_KEYS}
    for e in processor_selected(epochs):
        for key, values in select.cut_points(frames, e, max_gap, rate_hz).items():
            merged[key] += values
    return merged


def processor_stretches(frames, epochs, max_gap, rate_hz):
    """
    Every stretch the processor's cut_at draws in the selected epochs, short ones included, with its epoch.
    """
    return [{"epoch": e["epoch"], "frame_start": first, "frame_end": last}
            for e in processor_selected(epochs) for first, last in select.cut_at(frames, e, max_gap, rate_hz)]


def lab_shaped(frames):
    """
    The arrays with the rat still for 400 frames of the track, its heading lost for 250 of them after a heading of 1 rad, 0 rad after.
    """
    frames["head_dir"][:] = 0.0
    frames["head_dir"][2949:3049] = 1.0
    frames["head_dir"][LOST_FRAMES] = np.nan
    frames["mashup_x"][STILL_FRAMES] = frames["mashup_x"][2999]
    frames["mashup_y"][STILL_FRAMES] = frames["mashup_y"][2999]


def teleported(frames):
    """
    The arrays with the mashup position jumping 80 px at frame 2000.
    """
    frames["mashup_x"][1999:] += 80.0


def handled_at_pause(frames):
    """
    The arrays with the position and the heading stepping at S6's pause, 80 px and 2 rad, where the rat was picked up and put down.
    """
    frames["mashup_x"][2700:] += 80.0
    frames["head_dir"][2700:] = 2.0


def turning(frames):
    """
    The arrays with a heading that turns, lost where the back light was.
    """
    frames["head_dir"][:] = np.where(frames["unfilled_back"], np.nan, 0.5 + 0.6 * np.sin(frames["frame"] / 40))


def test_the_funnel_decides_as_select_does_and_names_why_a_session_is_out(transformed):
    tables = TransformedAccess(transformed).sessions()
    found = TrajectoryEngine().funnel(tables, RULES)
    epochs, _ = select.funnel(tables, None)
    assert [sid for sid, f in found.items() if f["in_dataset"]] == sorted({e["session_id"] for e in epochs}) == [S1, S6]
    for sid, f in found.items():
        assert f["epochs"] == [e for e in epochs if e["session_id"] == sid]
    assert [f["reason"] for f in found.values()] == [None, "protocol rotation, not standard", "excluded by annotation",
                                                      "group JL1HPCData is excluded", "protocol infusion, not standard", None]
    assert TrajectoryEngine().funnel({**tables, "frames": [S1]}, RULES)[S6] == {"in_dataset": False, "reason": "no frames", "epochs": found[S6]["epochs"]}
    assert TrajectoryEngine().funnel(tables, {**RULES, "condition": "rot45"})[S1]["reason"] == "no arena or track epoch under condition rot45"


@pytest.mark.parametrize("sid, overrides, change, reason", [(S1, {}, None, "epoch"), (S6, {}, None, "pause"), (S1, {"gap_lights": "either"}, None, "gap"),
                                                           (S1, {}, teleported, "jump"),
                                                           (S6, {}, handled_at_pause, "pause")],
                         ids=["S1", "S6 with its pause", "S1 gap on either light", "S1 with a jump", "S6 with a step at its pause"])
def test_cut_points_stretches_and_initial_blocks_equal_the_processors(transformed, monkeypatch, sid, overrides, change, reason):
    found, environment = loaded(transformed, sid)
    if change:
        change(found["arrays"])
    for key, value in overrides.items():
        monkeypatch.setattr(select, key.upper(), value)
    session = TrajectoryEngine().session(found, environment, {**RULES, **overrides})
    frames, row, epochs = found["arrays"], found["session"], found["epochs"]
    old = processor_cuts(frames, epochs, row["max_gap"], row["rate_hz"])
    points = session["cut_points"]
    assert [p["frame"] for p in points if p["reason"] == "pause"] == old["pauses"]
    assert [p["frame"] for p in points if p["reason"] == "jump"] == old["jumps"]
    assert [(p["frame"], p["frame_end"]) for p in points if p["reason"] == "gap"] == old["gaps"]
    assert [p["frame"] for p in points if p["reason"] == "epoch"] == [e["frame_start"] for e in processor_selected(epochs)]
    assert session["margins"] == old["margins"]
    assert session["stretches"] == processor_stretches(frames, epochs, row["max_gap"], row["rate_hz"])
    blocks, _ = select.blocks_in(frames, row, processor_epochs(transformed, sid))
    assert [{k: b[k] for k in BLOCK_KEYS} for b in session["initial_blocks"]] == [{k: b[k] for k in BLOCK_KEYS} for b in blocks]
    assert all(b["status"] == "auto" and b["note"] is None for b in session["initial_blocks"])
    assert any(p["reason"] == reason for p in points) and session["stretches"] and session["initial_blocks"]


def test_the_heading_fills_equal_the_processors(transformed):
    found, environment = loaded(transformed, S1)
    frames, rate_hz = found["arrays"], found["session"]["rate_hz"]
    session = TrajectoryEngine().session(found, environment, RULES)
    filled, kind = select.fill_heading(frames["head_dir"], frames["t"], old_frame.still(frames, found["epochs"]), rate_hz)
    assert session["heading_spans"] == {"lost": select.spans(frames["frame"], np.isnan(filled)), "filled": select.spans(frames["frame"], kind == select.INTERPOLATED),
                                        "held": select.spans(frames["frame"], kind == select.HELD)}
    assert session["heading_spans"] == {"lost": [], "filled": [(2800, 2919)], "held": []}
    parameters = old_frame.frame_parameters(frames, found["epochs"], found["runs"])
    expected = old_frame.heading_to_room(filled, parameters["led_offset_rad"], parameters["track"]["rotation_rad"])
    np.testing.assert_array_equal(session["kinematics"]["heading"], expected)


def test_the_held_fill_fires_on_a_still_stretch_with_the_heading_lost_and_a_moving_rat_keeps_it_missing(transformed):
    found, environment = loaded(transformed, S1)
    circling = {name: found["arrays"][name].copy() for name in ("mashup_x", "mashup_y")}
    lab_shaped(found["arrays"])
    session = TrajectoryEngine().session(found, environment, RULES)
    frames, rate_hz = found["arrays"], found["session"]["rate_hz"]
    filled, kind = select.fill_heading(frames["head_dir"], frames["t"], old_frame.still(frames, found["epochs"]), rate_hz)
    assert (kind == select.HELD).sum() == 250 and np.all(filled[LOST_FRAMES] == 1.0)
    assert session["heading_spans"] == {"lost": [], "filled": [], "held": select.spans(frames["frame"], kind == select.HELD)} == \
        {"lost": [], "filled": [], "held": [(3050, 3299)]}
    parameters = old_frame.frame_parameters(frames, found["epochs"], found["runs"])
    expected = old_frame.heading_to_room(filled, parameters["led_offset_rad"], parameters["track"]["rotation_rad"])
    np.testing.assert_array_equal(session["kinematics"]["heading"], expected)
    found["arrays"].update(circling)
    assert TrajectoryEngine().session(found, environment, RULES)["heading_spans"] == {"lost": [(3050, 3299)], "filled": [], "held": []}


@pytest.mark.parametrize("sid", [S1, S6])
def test_the_registration_equals_the_processors_and_the_positions_are_its_conversion(transformed, sid):
    found, environment = loaded(transformed, sid)
    session = TrajectoryEngine().session(found, environment, RULES)
    frames, epochs = found["arrays"], processor_epochs(transformed, sid)
    assert session["epochs"] == epochs
    assert session["frame"] == old_frame.frame_parameters(frames, epochs, found["runs"])
    assert ("arena" in session["frame"]) == (sid == S1)
    x, y = session["kinematics"]["x"], session["kinematics"]["y"]
    for epoch in epochs:
        p, here = session["frame"][epoch["epoch"]], old_frame.inside(frames, epoch)
        expected = old_frame.to_room(frames["mashup_x"][here], frames["mashup_y"][here], p["scale_px_per_m"], p["flip"], p["rotation_rad"], p["offset_m"])
        np.testing.assert_array_equal([x[here], y[here]], expected)
    registered = np.any([old_frame.inside(frames, e) for e in epochs], axis=0)
    assert np.isfinite(x[registered]).all() and np.isnan(x[~registered]).all()


def test_the_kinematics_equal_the_projects_inside_each_initial_block(transformed):
    found, environment = loaded(transformed, S1)
    turning(found["arrays"])
    session = TrajectoryEngine().session(found, environment, RULES)
    frames, rate_hz, kin = found["arrays"], found["session"]["rate_hz"], session["kinematics"]
    edge = trajectory.smooth_window(rate_hz) // 2
    for block in session["initial_blocks"]:
        at = slice(block["frame_start"] - 1, block["frame_end"])
        p = session["frame"][block["epoch"]]
        x, y = old_frame.to_room(frames["mashup_x"][at], frames["mashup_y"][at], p["scale_px_per_m"], p["flip"], p["rotation_rad"], p["offset_m"])
        measured = old_frame.heading_to_room(frames["head_dir"][at], old_frame.led_offset(frames)[0], p["rotation_rad"])
        speed, turn_rate = trajectory.kinematics(frames["t"][at] - frames["t"][at.start], x, y, measured, rate_hz)
        inner = slice(edge, -edge)
        np.testing.assert_allclose(kin["speed"][at][inner], speed[inner], rtol=0, atol=1e-9)
        np.testing.assert_allclose(kin["turn_rate"][at][inner], turn_rate[inner], rtol=0, atol=1e-9, equal_nan=True)
        assert np.isfinite(speed[inner]).all() and np.nanmax(np.abs(turn_rate[inner])) > 0.01 and np.isnan(turn_rate[inner]).any() == (block["epoch"] == "track")


def test_the_kinematics_do_not_differentiate_across_a_pause(transformed):
    found, environment = loaded(transformed, S6)
    handled_at_pause(found["arrays"])
    session = TrajectoryEngine().session(found, environment, RULES)
    kin, near = session["kinematics"], slice(2690, 2712)
    assert [p["reason"] for p in session["cut_points"]] == ["epoch", "pause"]
    assert np.ptp(kin["speed"][near]) < 1e-2 and np.abs(kin["turn_rate"][near]).max() < 1e-6


def test_a_changed_rule_changes_the_output_so_no_rule_is_a_constant_of_a_module(transformed):
    found, environment = loaded(transformed, S1)
    engine = TrajectoryEngine()
    base = engine.session(found, environment, RULES)
    assert base["rules"] == RULES and [b["frame_start"] for b in base["initial_blocks"]] == [301, 2101]
    longer = engine.session(found, environment, {**RULES, "min_block_s": 25.0})
    assert longer["initial_blocks"] == [] and longer["rules"]["min_block_s"] == 25.0
    untrimmed = engine.session(found, environment, {**RULES, "pause_margin_s": 0.0})
    assert [(b["frame_start"], b["frame_end"]) for b in untrimmed["initial_blocks"]] == [(1, 1800), (1801, 3600)] and untrimmed["margins"] == []
    assert engine.session(found, environment, {**RULES, "heading_fill_s": 1.0})["heading_spans"] == {"lost": [(2800, 2919)], "filled": [], "held": []}


def test_the_occupancy_counts_every_frame_inside_the_room_and_the_stops_find_the_still_stretch(transformed):
    found, environment = loaded(transformed, S1)
    lab_shaped(found["arrays"])
    session = TrajectoryEngine().session(found, environment, RULES)
    occupancy = session["occupancy"]
    assert occupancy["x"] == occupancy["y"] == [0.0, 1.8] and occupancy["bins"] ** 2 == len(occupancy["counts"]["track"])
    x, y = session["kinematics"]["x"], session["kinematics"]["y"]
    in_room = (x >= 0) & (x <= 1.8) & (y >= 0) & (y <= 1.8)
    assert {kind: sum(counts) for kind, counts in occupancy["counts"].items()} == {"arena": in_room[:1800].sum(), "track": in_room[1800:3600].sum()}
    assert 0 < in_room[1800:3600].sum() < 1800 and occupancy["outside"] == 3600 - in_room[:3600].sum()
    (first, last), = session["stops"]
    assert 3000 <= first <= 3010 and 3390 <= last <= 3400
    assert TrajectoryEngine().session(found, environment, {**RULES, "pause_min_s": 10.0})["stops"] == []


def test_the_session_carries_what_apply_reads_and_only_the_epochs_the_rules_select(transformed):
    found, environment = loaded(transformed, S6)
    session = TrajectoryEngine().session(found, environment, RULES)
    assert set(session) == SESSION_KEYS and session["session_id"] == S6 and session["rate_hz"] == 60 and session["n_frames"] == 5400
    assert [e["epoch"] for e in session["epochs"]] == ["track"] and session["runs"] == found["runs"]
    assert session["rules"] == RULES and session["rules"] is not RULES
    assert set(session["kinematics"]) == {"t", "x", "y", "heading", "speed", "turn_rate", "motion", "n_lights"}
    assert {len(values) for values in session["kinematics"].values()} == {5400}


@pytest.mark.parametrize("separation, count", [((0.04, 0.08), 1), ((0.065, 0.08), 2)])
def test_the_warnings_equal_the_processors_for_the_axes_and_a_led_separation_out_of_range(transformed, monkeypatch, separation, count):
    found, environment = loaded(transformed, S1)
    parameters = old_frame.frame_parameters(found["arrays"], found["epochs"], found["runs"])
    monkeypatch.setattr(processor, "LED_SEPARATION_M", separation)
    warnings = TrajectoryEngine().session(found, environment, {**RULES, "led_separation_m": separation})["warnings"]
    assert warnings == processor.session_warnings(S1, processor.session_checks(parameters), None) and len(warnings) == count
    assert count == 1 or warnings[1].startswith(f"{S1} arena LED separation")


def test_a_session_with_no_selected_track_epoch_is_refused_by_name(transformed):
    found, environment = loaded(transformed, S6)
    message = f"^session {S6} has no track epoch under condition rot45, registration needs one$"
    with pytest.raises(Invalid, match=message):
        TrajectoryEngine().session(found, environment, {**RULES, "condition": "rot45"})


def test_a_heading_fill_across_the_wrap_takes_the_short_arc_through_pi():
    heading = np.concatenate([np.full(10, 3.0), np.full(5, np.nan), np.full(10, -3.0)])
    filled, kind = new_heading.fill(heading, np.arange(len(heading)) / 60, np.zeros(len(heading), bool), 60, RULES)
    assert (kind[10:15] == new_heading.INTERPOLATED).all() and (kind[:10] == new_heading.UNTOUCHED).all()
    assert np.cos(filled[10:15]).max() < -0.98
    np.testing.assert_allclose(np.diff(np.unwrap(filled[9:16])), (2 * np.pi - 6.0) / 6)


@pytest.mark.parametrize("injected", [0.7, -2.5])
def test_an_injected_led_mounting_angle_is_recovered_from_running_frames(injected):
    n, angle = 1200, 2 * np.pi * np.arange(1200) / 600
    noise = np.random.default_rng(0).normal(0, 0.1, n)
    frames = {"t": np.arange(n) / 60, "mashup_x": 300 + 100 * np.cos(angle), "mashup_y": 200 + 100 * np.sin(angle),
              "head_dir": np.angle(np.exp(1j * (angle + np.pi / 2 + injected + noise)))}
    offset, concentration, running = new_heading.led_offset(frames, RULES)
    assert abs(np.angle(np.exp(1j * (offset - injected)))) < 0.02 and concentration > 0.98 and running > 0.99 * n
