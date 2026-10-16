"""
The funnel on the synthetic tables: the surviving epochs, the count after each step, --only, the block cuts and the heading fill.
"""

import numpy as np
import pytest

from process_lab_data import select

from .conftest import MAX_GAP, RATE_HZ, S1, S6

# A scripted session of 6000 frames with the epoch at 301 to 5700: a pause at 2401 and another at 5650, a jump of 60
# px at 3601, an unfilled stretch of exactly max_gap frames at 700 to 729 that stays inside its block, one light lost
# over 1000 to 1049 that stays under the both rule, and both lights lost over 4500 to 4549 that cuts. The margins,
# 300 frames, trim every edge at the epoch bounds, the pauses and the jump but not the edges at the gap: the stretch
# after the jump is left 599 frames, one under MIN_BLOCK_S, the one between the pause and the jump exactly 600, and
# the 51 frames after the second pause vanish.
SCRIPTED_EPOCH = {"frame_start": 301, "frame_end": 5700}
SCRIPTED_PAUSES, SCRIPTED_JUMP, SCRIPTED_GAP = (2401, 5650), 3601, (4500, 4549)
SCRIPTED_CUTS = [(601, 2100), (2701, 3300), (3901, 4499), (4550, 5349)]
SCRIPTED_MARGINS = [(301, 600), (2101, 2400), (2401, 2700), (3301, 3600), (3601, 3900), (5350, 5649), (5650, 5700)]


def scripted_frames():
    """
    The scripted session as the arrays cut_at reads.
    """
    frame = np.arange(1, 6001)
    t = (frame - 1) / RATE_HZ
    for pause, delay in zip(SCRIPTED_PAUSES, (120.0, 7.0)):
        t[frame >= pause] += delay
    unfilled_front, unfilled_back = np.zeros(6000, bool), np.zeros(6000, bool)
    unfilled_front[699:729] = unfilled_back[699:729] = True
    unfilled_front[999:1049] = True
    unfilled_front[4499:4549] = unfilled_back[4499:4549] = True
    lost = unfilled_front & unfilled_back
    x = np.where(lost, np.nan, 300.0 + 60.0 * (frame >= SCRIPTED_JUMP))
    y = np.where(lost, np.nan, 200.0)
    return {"frame": frame, "t": t, "unfilled_front": unfilled_front, "unfilled_back": unfilled_back,
            "mashup_x": x, "mashup_y": y}


def test_blocks_are_cut_at_pauses_jumps_long_both_lights_gaps_and_the_epoch_bounds_then_trimmed_and_short_ones_dropped():
    frames = scripted_frames()
    assert select.cut_at(frames, SCRIPTED_EPOCH, MAX_GAP, RATE_HZ) == SCRIPTED_CUTS
    assert select.cut_blocks(frames, SCRIPTED_EPOCH, MAX_GAP, RATE_HZ) == [SCRIPTED_CUTS[0], SCRIPTED_CUTS[1], SCRIPTED_CUTS[3]]


def test_a_pause_or_an_epoch_bound_inside_a_gap_still_trims_the_margins_on_both_sides_of_the_gap():
    frames = scripted_frames()
    frames["t"][frames["frame"] >= 4525] += 120.0  # a pause inside the gap at 4500 to 4549
    frames["unfilled_front"][:350] = frames["unfilled_back"][:350] = True  # the epoch starts inside a gap at 1 to 350
    frames["mashup_x"][:350] = frames["mashup_y"][:350] = np.nan
    cuts = select.cut_at(frames, SCRIPTED_EPOCH, MAX_GAP, RATE_HZ)
    assert cuts == [(651, 2100), (2701, 3300), (3901, 4199), (4850, 5349)]
    assert select.cut_points(frames, SCRIPTED_EPOCH, MAX_GAP, RATE_HZ)["margins"] == [
        (351, 650), (2101, 2400), (2401, 2700), (3301, 3600), (3601, 3900), (4200, 4499), (4550, 4849),
        (5350, 5649), (5650, 5700)]


def test_the_cut_points_name_every_pause_jump_gap_and_margin_of_the_epoch():
    points = select.cut_points(scripted_frames(), SCRIPTED_EPOCH, MAX_GAP, RATE_HZ)
    assert points == {"pauses": list(SCRIPTED_PAUSES), "jumps": [SCRIPTED_JUMP], "gaps": [SCRIPTED_GAP],
                      "margins": SCRIPTED_MARGINS}


def test_a_step_across_a_pause_or_a_lost_position_is_not_a_jump():
    frames = scripted_frames()
    frames["mashup_x"][frames["frame"] >= SCRIPTED_PAUSES[0]] += 500.0
    frames["mashup_x"][frames["frame"] > SCRIPTED_GAP[1]] += 500.0
    assert frames["frame"][select.jumps(frames)].tolist() == [SCRIPTED_JUMP]


def gappy_heading():
    """
    Heading over 1200 frames with t pausing at 900: a short gap through the wrap, a long gap, a short gap over the pause, a gap at the end.
    """
    t = np.arange(1200) / RATE_HZ
    t[900:] += 60.0
    heading = np.full(1200, 0.5)
    heading[100:104] = np.nan  # a short gap turning from 3.0 through pi to -2.9
    heading[:100], heading[104:300] = 3.0, -2.9
    heading[400:600] = np.nan  # 200 frames, over HEADING_FILL_SEC
    heading[898:902] = np.nan  # a short gap with the pause inside
    heading[1190:] = np.nan  # a gap at the end
    return heading, t


def test_short_heading_gaps_are_filled_along_the_shortest_arc_through_the_wrap_and_long_or_paused_ones_stay_nan_while_running():
    heading, t = gappy_heading()
    filled, kind = select.fill_heading(heading, t, np.zeros(1200, bool), RATE_HZ)
    arc = np.unwrap(np.concatenate(([3.0], filled[100:104], [-2.9])))
    assert np.diff(arc) == pytest.approx([(2 * np.pi - 5.9) / 5] * 5)
    assert (np.abs(filled[100:104]) <= np.pi).all() and (kind[100:104] == select.INTERPOLATED).all() and (kind > 0).sum() == 4
    assert np.isnan(filled[400:600]).all() and np.isnan(filled[898:902]).all() and np.isnan(filled[1190:]).all()
    assert np.array_equal(np.isnan(filled), np.isnan(heading) & (kind == select.UNTOUCHED)) and kind.dtype == np.int8


def test_a_long_heading_gap_is_held_at_the_last_heading_when_the_rat_is_still_throughout_and_stays_nan_otherwise():
    heading, t = gappy_heading()
    still = np.ones(1200, bool)
    filled, kind = select.fill_heading(heading, t, still, RATE_HZ)
    assert (filled[400:600] == 0.5).all() and (kind[400:600] == select.HELD).all()
    assert (kind[100:104] == select.INTERPOLATED).all() and (kind > 0).sum() == 204
    assert np.isnan(filled[898:902]).all() and np.isnan(filled[1190:]).all()
    still[500] = False
    filled, kind = select.fill_heading(heading, t, still, RATE_HZ)
    assert np.isnan(filled[400:600]).all() and not kind[400:600].any() and (kind > 0).sum() == 4


def test_blocks_of_reads_the_frames_and_counts_the_cuts_the_margins_and_the_length_rule(transformed):
    tables = select.read_tables(transformed)
    epochs, _ = select.funnel(tables, None)
    blocks, counts = select.blocks_of(transformed, epochs, tables["sessions"])
    assert [(b["block_id"], b["frame_start"], b["frame_end"], b["n_frames"], b["duration_s"]) for b in blocks] == [
        (f"{S1}_arena_01", 301, 1500, 1200, 20.0), (f"{S1}_track_01", 2101, 3300, 1200, 20.0), (f"{S6}_track_01", 3001, 4200, 1200, 20.0)]
    assert blocks[1]["environment"] == "triple_t"
    assert counts == [("blocks, cut at pauses, gaps and jumps", 4), ("blocks, after margins", 4), ("blocks, at least 10 s", 3),
                      ("blocks, kind arena", 1), ("blocks, kind track", 2),
                      ("jump frames, in the epochs", 0), ("seconds trimmed by margins", 40.0)]


def test_the_funnel_keeps_the_baseline_arena_and_track_epochs_of_standard_included_sessions(transformed):
    epochs, counts = select.funnel(select.read_tables(transformed), None)
    assert [(e["session_id"], e["epoch"]) for e in epochs] == [(S1, "arena"), (S1, "track"), (S6, "track")]
    assert [count for _, count in counts] == [6, 4, 3, 2, 2, 5, 4, 3, 4, 3]
    assert [step for step, _ in counts] == [
        "sessions, all sessions", "sessions, protocol standard", "sessions, group allowed",
        "sessions, not excluded by annotations", "sessions, --only",
        "epochs, of those sessions", "epochs, kind arena or track", "epochs, condition baseline",
        "runs, of surviving track epochs", "runs, clean",
    ]


def test_only_matches_the_whole_id_or_a_prefix_ending_at_an_underscore(transformed):
    tables = select.read_tables(transformed)
    for only, kept in (("NS16", [S6]), (S6, [S6]), ("NS14_rec1", [S1]), ("NS1", [])):
        epochs, counts = select.funnel(tables, only)
        assert sorted({e["session_id"] for e in epochs}) == kept
        assert dict(counts)["sessions, --only"] == len(kept)


def test_missing_annotations_and_verdicts_exclude_nothing(transformed):
    (transformed / select.ANNOTATIONS).unlink()
    tables = select.read_tables(transformed)
    assert tables["annotations"] == [] and tables["verdicts"] == []
    _, counts = select.funnel(tables, None)
    assert dict(counts)["sessions, not excluded by annotations"] == 3
