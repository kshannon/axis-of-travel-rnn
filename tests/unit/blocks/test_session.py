"""
BlockEngine.funnel and session over the synthetic fixtures: the epochs the funnel selects, the cut points and stretches, the heading fills, the registration and the kinematics, with the values the fixtures give recorded as literals.
"""

import numpy as np
import pytest

from axis_of_travel_rnn.blocks import RULES, BlockEngine, cuts, io, room
from axis_of_travel_rnn.blocks import frame as new_frame
from axis_of_travel_rnn.blocks import heading as new_heading
from axis_of_travel_rnn.blocks import kinematics as new_kinematics

from .fixtures import CIRCLE_PX, S1, S2, S3, S4, S5, S6, loaded

NOISE_PX = 1.0
SESSION_KEYS = {"rules", "session_id", "rate_hz", "n_frames", "epochs", "runs", "frame", "warnings", "kinematics", "heading_spans",
                "cut_points", "margins", "stretches", "initial_blocks", "stops"}
STILL_FRAMES, LOST_FRAMES = slice(2999, 3399), slice(3049, 3299)
# The fixtures' rat circles CIRCLE_PX about (300, 200) in front light pixels, the mashup position being 5 px behind that.
CIRCLE_CENTRE_PX = np.array([295.0, 200.0])
START_OFFSET_KEY = "start_offset_measured_m"
# The epochs the funnel selects for the sessions with frames, as (epoch, first frame, last frame): S1's baseline arena and track, and S6's
# baseline track alone, its arena being under rot45.
SELECTED = {S1: [("arena", 1, 1800), ("track", 1801, 3600)], S6: [("track", 1801, 4500)]}
# The registration of each session as the engine measures it: the LED offset, and the track's scale, rotation and offset in metres.
REGISTERED = {S1: (3.0699729433209866, 146.0182395463913, -0.0007556771113748084, (-0.776837054051421, 1.6859594389835018)),
              S6: (3.1217325654496677, 145.87753297973615, -2.35095850243565, (3.9600195812419012, 0.6140941022997033))}
# The reasons a heading span carries, as the rules' 3 s fill limit words them.
OVER_LIMIT = "over the fill limit of 3 s"
ARC = "along the shortest arc"


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


def test_the_funnel_leaves_out_only_what_the_tool_cannot_work_with_and_shows_the_annotation_as_a_note(transformed):
    tables = io.sessions(transformed)
    found = BlockEngine().funnel(tables, RULES)
    # Only S1 and S6 have frames, S5 has no baseline arena or track epoch. No protocol, group or annotation rule applies.
    assert [sid for sid, f in found.items() if f["in_dataset"]] == [S1, S6]
    for sid in (S1, S6):
        assert [(e["epoch"], e["frame_start"], e["frame_end"]) for e in found[sid]["epochs"]] == SELECTED[sid]
        assert {e["condition"] for e in found[sid]["epochs"]} == {"baseline"}
    assert [e["epoch"] for e in found[S2]["epochs"]] == ["arena", "track"] and found[S5]["epochs"] == []
    assert [f["reason"] for f in found.values()] == [None, "no frames", "no frames", "no frames", "no arena or track epoch under condition baseline", None]
    assert [f["annotated_exclude"] for f in found.values()] == [False, False, True, False, False, False]
    assert BlockEngine().funnel({**tables, "annotations": []}, RULES)[S3]["annotated_exclude"] is False
    assert BlockEngine().funnel({**tables, "frames": [S1]}, RULES)[S6] == {"in_dataset": False, "reason": "no frames", "epochs": found[S6]["epochs"],
                                                                                "annotated_exclude": False}
    assert BlockEngine().funnel(tables, {**RULES, "condition": "rot45"})[S1]["reason"] == "no arena or track epoch under condition rot45"


def test_a_rotation_protocol_a_group_and_an_annotation_exclude_do_not_keep_a_session_out_of_the_funnel(transformed):
    tables = io.sessions(transformed)
    found = BlockEngine().funnel({**tables, "frames": [S1, S2, S3, S4, S6]}, RULES)
    by_id = {s["session_id"]: s for s in tables["sessions"]}
    assert by_id[S2]["protocol"] == "rotation" and by_id[S4]["group"] == "JL1HPCData" and found[S3]["annotated_exclude"] is True
    assert [found[sid]["in_dataset"] for sid in (S1, S2, S3, S4, S5, S6)] == [True, True, True, True, False, True]
    assert [found[sid]["reason"] for sid in (S2, S3, S4)] == [None, None, None]


# The cut points, margins, stretches and initial blocks the engine gives each case, as (pauses, jumps, gaps, margins, stretches, blocks): the first
# frames of the pauses and jumps, the (first, last) frames of the gaps and margins, the stretches as (epoch, first, last), the blocks as (id suffix, first, last).
CASES = [
    (S1, {}, None, "epoch", [], [], [], [(1, 300), (1501, 1800), (1801, 2100), (3301, 3600)],
     [("arena", 301, 1500), ("track", 2101, 3300)], [("arena_01", 301, 1500), ("track_01", 2101, 3300)]),
    (S6, {}, None, "pause", [2701], [], [], [(1801, 2100), (2401, 2700), (2701, 3000), (4201, 4500)],
     [("track", 2101, 2400), ("track", 3001, 4200)], [("track_01", 3001, 4200)]),
    (S1, {"gap_lights": "either"}, None, "gap", [], [], [(2800, 2919)], [(1, 300), (1501, 1800), (1801, 2100), (3301, 3600)],
     [("arena", 301, 1500), ("track", 2101, 2799), ("track", 2920, 3300)], [("arena_01", 301, 1500), ("track_01", 2101, 2799)]),
    (S1, {}, teleported, "jump", [], [2000], [], [(1, 300), (1501, 1800), (1801, 1999), (2000, 2299), (3301, 3600)],
     [("arena", 301, 1500), ("track", 2300, 3300)], [("arena_01", 301, 1500), ("track_01", 2300, 3300)]),
    (S6, {}, handled_at_pause, "pause", [2701], [], [], [(1801, 2100), (2401, 2700), (2701, 3000), (4201, 4500)],
     [("track", 2101, 2400), ("track", 3001, 4200)], [("track_01", 3001, 4200)]),
]


@pytest.mark.parametrize("sid, overrides, change, reason, pauses, jumps, gaps, margins, stretches, blocks", CASES,
                         ids=["S1", "S6 with its pause", "S1 gap on either light", "S1 with a jump", "S6 with a step at its pause"])
def test_cut_points_stretches_and_initial_blocks_are_the_recorded_ones(transformed, sid, overrides, change, reason, pauses, jumps, gaps, margins, stretches, blocks):
    found, environment = loaded(transformed, sid)
    if change:
        change(found["arrays"])
    session = BlockEngine().session(found, environment, {**RULES, **overrides})
    points = session["cut_points"]
    assert [p["frame"] for p in points if p["reason"] == "pause"] == pauses
    assert [p["frame"] for p in points if p["reason"] == "jump"] == jumps
    assert [(p["frame"], p["frame_end"]) for p in points if p["reason"] == "gap"] == gaps
    assert [p["frame"] for p in points if p["reason"] == "epoch"] == [first for _, first, _ in SELECTED[sid]]
    assert session["margins"] == margins
    assert [(x["epoch"], x["frame_start"], x["frame_end"]) for x in session["stretches"]] == stretches
    assert [(b["block_id"].removeprefix(f"{sid}_"), b["frame_start"], b["frame_end"]) for b in session["initial_blocks"]] == blocks
    assert all(b["status"] == "auto" and b["note"] is None for b in session["initial_blocks"])
    assert any(p["reason"] == reason for p in points)


def test_the_heading_fills_are_the_recorded_spans_and_the_filled_heading_is_measured_everywhere_in_the_room(transformed):
    found, environment = loaded(transformed, S1)
    session = BlockEngine().session(found, environment, RULES)
    assert session["heading_spans"] == {"lost": [], "filled": [{"first": 2800, "last": 2919, "seconds": 2.0, "reason": ARC}], "held": []}
    heading = session["kinematics"]["heading"]
    assert np.isfinite(heading[2799:2919]).all() and np.abs(heading).max() <= np.pi


def test_the_held_fill_fires_on_a_still_stretch_with_the_heading_lost_and_a_moving_rat_keeps_it_missing(transformed):
    found, environment = loaded(transformed, S1)
    circling = {name: found["arrays"][name].copy() for name in ("mashup_x", "mashup_y")}
    lab_shaped(found["arrays"])
    session = BlockEngine().session(found, environment, RULES)
    assert session["heading_spans"] == {"lost": [], "filled": [], "held": [{"first": 3050, "last": 3299, "seconds": 250 / 60, "reason": "the rat was still"}]}
    held = session["kinematics"]["heading"][LOST_FRAMES]
    assert np.isfinite(held).all() and np.ptp(held) == 0.0
    found["arrays"].update(circling)
    assert BlockEngine().session(found, environment, RULES)["heading_spans"] == \
        {"lost": [{"first": 3050, "last": 3299, "seconds": 250 / 60, "reason": OVER_LIMIT}], "filled": [], "held": []}


@pytest.mark.parametrize("sid", [S1, S6])
def test_the_registration_is_the_recorded_one_and_the_positions_are_its_conversion(transformed, sid):
    found, environment = loaded(transformed, sid)
    session = BlockEngine().session(found, environment, RULES)
    frames, epochs = found["arrays"], session["epochs"]
    assert [(e["epoch"], e["frame_start"], e["frame_end"]) for e in epochs] == SELECTED[sid]
    led_offset, scale, rotation, offset = REGISTERED[sid]
    track = session["frame"]["track"]
    assert session["frame"]["led_offset_rad"] == pytest.approx(led_offset, rel=1e-9)
    assert (track["scale_px_per_m"], track["rotation_rad"]) == (pytest.approx(scale, rel=1e-9), pytest.approx(rotation, rel=1e-9))
    assert track["offset_m"] == pytest.approx(offset, rel=1e-9) and track["flip"] is True
    assert ("arena" in session["frame"]) == (sid == S1)
    x, y = session["kinematics"]["x"], session["kinematics"]["y"]
    for epoch in epochs:
        p, here = session["frame"][epoch["epoch"]], cuts.inside(frames, epoch)
        expected = room.to_room(frames["mashup_x"][here], frames["mashup_y"][here], p["scale_px_per_m"], p["flip"], p["rotation_rad"], p["offset_m"])
        np.testing.assert_array_equal([x[here], y[here]], expected)
    registered = np.any([cuts.inside(frames, e) for e in epochs], axis=0)
    assert np.isfinite(x[registered]).all() and np.isnan(x[~registered]).all()


@pytest.mark.parametrize("sid", [S1, S6])
def test_the_measured_start_offset_is_the_start_over_the_bottom_of_the_fixtures_circle(transformed, sid):
    found, environment = loaded(transformed, sid)
    registration = BlockEngine().session(found, environment, RULES)["frame"]
    track, start_px = registration["track"], registration["start_px"]
    # The bottom outer peak of a circle lies a radius under its centre in the room axes (camera y flipped, track rotation taken out). The peak
    # is the centroid of its smoothing bins, which sit on the side of the extreme the rat visits, so it may lie half their window inside it.
    dx, dy = np.array(start_px) - CIRCLE_CENTRE_PX
    expected_px = CIRCLE_PX + dx * np.sin(track["rotation_rad"]) - dy * np.cos(track["rotation_rad"])
    window_px = RULES["peak_smooth_bins"] * RULES["histogram_bin_px"] / 2
    assert track[START_OFFSET_KEY] * track["scale_px_per_m"] == pytest.approx(expected_px, abs=window_px)
    assert START_OFFSET_KEY not in registration.get("arena", {})


def test_the_measured_start_offset_of_a_hand_made_track_is_the_start_height_over_the_bottom_corridor_and_negative_under_it():
    # Two corridors of running frames at 100 and 900 px up the room's y axis, the camera's y pointing down, 200 px per metre, no rotation.
    spread = np.repeat(np.arange(-4.0, 5.0), 50)
    axes = (np.zeros(2 * len(spread)), np.concatenate([100 + spread, 900 + spread]))
    one_bin_m = RULES["histogram_bin_px"] / 200
    assert new_frame.start_offset_measured(axes, (0.0, -400.0), 0.0, 200.0, RULES) == pytest.approx(1.5, abs=one_bin_m)
    assert new_frame.start_offset_measured(axes, (0.0, -50.0), 0.0, 200.0, RULES) == pytest.approx(-0.25, abs=one_bin_m)


def test_the_session_kinematics_equal_a_blocks_own_inside_each_initial_block(transformed):
    found, environment = loaded(transformed, S1)
    turning(found["arrays"])
    session = BlockEngine().session(found, environment, RULES)
    frames, rate_hz, kin = found["arrays"], found["session"]["rate_hz"], session["kinematics"]
    edge = new_kinematics.smooth_window(rate_hz, RULES) // 2
    for block in session["initial_blocks"]:
        at = slice(block["frame_start"] - 1, block["frame_end"])
        p = session["frame"][block["epoch"]]
        x, y = room.to_room(frames["mashup_x"][at], frames["mashup_y"][at], p["scale_px_per_m"], p["flip"], p["rotation_rad"], p["offset_m"])
        measured = room.heading_to_room(frames["head_dir"][at], new_heading.led_offset(frames, RULES)[0], p["rotation_rad"])
        speed, _, turn_rate = new_kinematics.kinematics(x, y, measured, np.zeros(len(x), bool), rate_hz, RULES)
        inner = slice(edge, -edge)
        np.testing.assert_allclose(kin["speed"][at][inner], speed[inner], rtol=0, atol=1e-9)
        np.testing.assert_allclose(kin["turn_rate"][at][inner], turn_rate[inner], rtol=0, atol=1e-9, equal_nan=True)
        assert np.isfinite(speed[inner]).all() and np.nanmax(np.abs(turn_rate[inner])) > 0.01 and np.isnan(turn_rate[inner]).any() == (block["epoch"] == "track")


def test_the_smoothed_position_of_a_straight_line_at_constant_speed_is_the_line_and_is_missing_where_the_position_or_a_stretch_is():
    t = np.arange(300) / 60
    x, y = 0.5 * t, 1.0 - 0.2 * t
    x[100:103] = np.nan
    breaks = np.zeros(300, bool)
    breaks[250] = True
    x_smooth, y_smooth = new_kinematics.smooth_position(x, y, breaks, 60, RULES)
    kept = np.isfinite(x_smooth)
    np.testing.assert_allclose(x_smooth[kept], x[kept], atol=1e-12)
    np.testing.assert_allclose(y_smooth[kept], y[kept], atol=1e-12)
    assert np.isnan(x_smooth[100:103]).all() and np.isnan(y_smooth[100:103]).all()
    # The three frames missing split the line into stretches that are each longer than the window, so only they are missing.
    assert kept[:100].all() and kept[103:].all()
    short = new_kinematics.smooth_position(x[:20], y[:20], np.zeros(20, bool), 60, RULES)[0]
    assert np.isfinite(short).all()
    assert np.isnan(new_kinematics.smooth_position(x[:8], y[:8], np.zeros(8, bool), 60, RULES)[0]).all()


def test_the_smoothed_position_of_a_noisy_circle_stays_near_the_registered_one_with_less_jitter(transformed):
    found, environment = loaded(transformed, S1)
    noise = np.random.default_rng(0)
    for name in ("mashup_x", "mashup_y"):
        found["arrays"][name] += noise.normal(0, NOISE_PX, len(found["arrays"][name]))
    session = BlockEngine().session(found, environment, RULES)
    kin, scale = session["kinematics"], session["frame"]["track"]["scale_px_per_m"]
    inside = slice(2200, 3500)
    for raw, smooth in (("x", "x_smooth"), ("y", "y_smooth")):
        assert np.abs(kin[smooth][inside] - kin[raw][inside]).max() < 5 * NOISE_PX / scale
        assert np.abs(np.diff(kin[smooth][inside], 2)).sum() < np.abs(np.diff(kin[raw][inside], 2)).sum() / 2
    assert np.isnan(kin["x_smooth"][np.isnan(kin["x"])]).all() and np.isnan(kin["x"]).any()
    assert np.isfinite(kin["x_smooth"][inside]).all()


def test_the_kinematics_do_not_differentiate_across_a_pause(transformed):
    found, environment = loaded(transformed, S6)
    handled_at_pause(found["arrays"])
    session = BlockEngine().session(found, environment, RULES)
    kin, near = session["kinematics"], slice(2690, 2712)
    assert [p["reason"] for p in session["cut_points"]] == ["epoch", "pause"]
    assert np.ptp(kin["speed"][near]) < 1e-2 and np.abs(kin["turn_rate"][near]).max() < 1e-6


def test_a_changed_rule_changes_the_output_so_no_rule_is_a_constant_of_a_module(transformed):
    found, environment = loaded(transformed, S1)
    engine = BlockEngine()
    base = engine.session(found, environment, RULES)
    assert base["rules"] == RULES and [b["frame_start"] for b in base["initial_blocks"]] == [301, 2101]
    longer = engine.session(found, environment, {**RULES, "min_block_s": 25.0})
    assert longer["initial_blocks"] == [] and longer["rules"]["min_block_s"] == 25.0
    untrimmed = engine.session(found, environment, {**RULES, "pause_margin_s": 0.0})
    assert [(b["frame_start"], b["frame_end"]) for b in untrimmed["initial_blocks"]] == [(1, 1800), (1801, 3600)] and untrimmed["margins"] == []
    assert engine.session(found, environment, {**RULES, "heading_fill_s": 1.0})["heading_spans"] == \
        {"lost": [{"first": 2800, "last": 2919, "seconds": 2.0, "reason": "over the fill limit of 1 s"}], "filled": [], "held": []}


def test_the_stops_find_the_still_stretch(transformed):
    found, environment = loaded(transformed, S1)
    lab_shaped(found["arrays"])
    session = BlockEngine().session(found, environment, RULES)
    (first, last), = session["stops"]
    assert 3000 <= first <= 3010 and 3390 <= last <= 3400
    assert BlockEngine().session(found, environment, {**RULES, "pause_min_s": 10.0})["stops"] == []


def test_the_session_carries_what_apply_reads_and_only_the_epochs_the_rules_select(transformed):
    found, environment = loaded(transformed, S6)
    session = BlockEngine().session(found, environment, RULES)
    assert set(session) == SESSION_KEYS and session["session_id"] == S6 and session["rate_hz"] == 60 and session["n_frames"] == 5400
    assert [e["epoch"] for e in session["epochs"]] == ["track"] and session["runs"] == found["runs"]
    assert session["rules"] == RULES and session["rules"] is not RULES
    assert set(session["kinematics"]) == {"t", "x", "y", "x_smooth", "y_smooth", "heading", "speed", "turn_rate", "motion", "n_lights"}
    assert {len(values) for values in session["kinematics"].values()} == {5400}


TRACK_SCALE_WARNING = f"{S1} track scale x and y differ by 26 percent, over 5: an outer corridor peak missed?"
ARENA_SEPARATION_WARNING = f"{S1} arena LED separation 6.3 cm outside 6.5 to 8"


@pytest.mark.parametrize("separation, warnings", [((0.04, 0.08), [TRACK_SCALE_WARNING]), ((0.065, 0.08), [TRACK_SCALE_WARNING, ARENA_SEPARATION_WARNING])])
def test_the_warnings_name_the_axes_and_a_led_separation_out_of_range(transformed, separation, warnings):
    found, environment = loaded(transformed, S1)
    assert BlockEngine().session(found, environment, {**RULES, "led_separation_m": separation})["warnings"] == warnings


def test_a_session_with_no_selected_track_epoch_is_refused_by_name(transformed):
    found, environment = loaded(transformed, S6)
    message = f"^session {S6} has no track epoch under condition rot45, registration needs one$"
    with pytest.raises(ValueError, match=message):
        BlockEngine().session(found, environment, {**RULES, "condition": "rot45"})


def test_a_heading_fill_across_the_wrap_takes_the_short_arc_through_pi():
    heading = np.concatenate([np.full(10, 3.0), np.full(5, np.nan), np.full(10, -3.0)])
    filled, found = new_heading.fill(heading, np.arange(len(heading)) / 60, np.zeros(len(heading), bool), 60, RULES)
    assert found == [(10, 15, new_heading.FILLED, ARC)]
    assert np.cos(filled[10:15]).max() < -0.98
    np.testing.assert_allclose(np.diff(np.unwrap(filled[9:16])), (2 * np.pi - 6.0) / 6)


def gap_after(before, gap, after):
    """
    A heading of measured frames with a run of lost ones between them.
    """
    return np.concatenate([np.full(before, 0.5), np.full(gap, np.nan), np.full(after, 0.5)])


@pytest.mark.parametrize("heading, pause_at, still, key, first, last, reason", [
    (gap_after(10, 250, 10), None, False, "lost", 11, 260, OVER_LIMIT),
    (gap_after(10, 250, 10), 100, True, "lost", 11, 260, "contains a pause"),
    (gap_after(10, 20, 10), 20, False, "lost", 11, 30, "contains a pause"),
    (gap_after(0, 20, 10), None, False, "lost", 1, 20, "touches the start of the recording"),
    (gap_after(10, 20, 0), None, False, "lost", 11, 30, "touches the end of the recording"),
    (gap_after(0, 30, 0), None, False, "lost", 1, 30, "no measured heading on either side"),
    (gap_after(10, 120, 10), None, False, "filled", 11, 130, ARC),
    (gap_after(10, 250, 10), None, True, "held", 11, 260, "the rat was still"),
])
def test_every_heading_span_carries_the_reason_the_fill_decided_it(heading, pause_at, still, key, first, last, reason):
    t = np.arange(len(heading)) / 60
    if pause_at is not None:
        t[pause_at:] += 5.0
    _, found = new_heading.fill(heading, t, np.full(len(heading), still), 60, RULES)
    spans = new_heading.fill_spans(np.arange(1, len(heading) + 1), found, 60)
    assert spans[key] == [{"first": first, "last": last, "seconds": pytest.approx((last - first + 1) / 60), "reason": reason}]
    assert [other for other in spans if other != key and spans[other]] == []


def test_the_fill_limit_in_the_reason_is_the_rules_own():
    heading = gap_after(10, 100, 10)
    _, found = new_heading.fill(heading, np.arange(len(heading)) / 60, np.zeros(len(heading), bool), 60, {**RULES, "heading_fill_s": 1.5})
    assert [span["reason"] for span in new_heading.fill_spans(np.arange(1, len(heading) + 1), found, 60)["lost"]] == ["over the fill limit of 1.5 s"]


@pytest.mark.parametrize("injected", [0.7, -2.5])
def test_an_injected_led_mounting_angle_is_recovered_from_running_frames(injected):
    n, angle = 1200, 2 * np.pi * np.arange(1200) / 600
    noise = np.random.default_rng(0).normal(0, 0.1, n)
    frames = {"t": np.arange(n) / 60, "mashup_x": 300 + 100 * np.cos(angle), "mashup_y": 200 + 100 * np.sin(angle),
              "head_dir": np.angle(np.exp(1j * (angle + np.pi / 2 + injected + noise)))}
    offset, concentration, running = new_heading.led_offset(frames, RULES)
    assert abs(np.angle(np.exp(1j * (offset - injected)))) < 0.02 and concentration > 0.98 and running > 0.99 * n
