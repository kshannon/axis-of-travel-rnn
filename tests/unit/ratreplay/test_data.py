"""
Data access on the synthetic session: listing, loading, the processor's cut points and heading fill, the automatic blocks
against cut_at, the edits, the summary numbers, the review file.
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from process_lab_data import select
from ratreplay import data

from .conftest import (AUTO_BLOCKS, GAP, JUMP, LONG_HEADING_GAP, MARGINS, MAX_GAP, N_FRAMES, PAUSE, RATE_HZ, RUNS,
                       SESSION, SHORT_HEADING_GAP, STAMP, STRETCHES, frames_table, write_sessions)

ARRAYS = ("t", "x", "y", "heading", "speed", "n_lights")
LIGHT_COLUMNS = ("front_x", "front_y", "back_x", "back_y", "avg_x", "avg_y", "mashup_x", "mashup_y")
STILL_LEAD = 10
TRACK_RUNS = [{"epoch": "track", **run} for run in RUNS]
EPOCH_OF = ["arena", "track", "track", "track", "track"]
EDIT_STRETCHES = [{"epoch": epoch, "frame_start": start, "frame_end": end} for epoch, (start, end) in zip(EPOCH_OF, STRETCHES)]
EPOCHS = [{"epoch": "arena", "environment": "open_arena"}, {"epoch": "track", "environment": "triple_t"}]
EDIT_SESSION = {"session_id": SESSION, "runs": TRACK_RUNS, "rate_hz": RATE_HZ, "stretches": EDIT_STRETCHES, "epochs": EPOCHS}
TRACK_S = sum(end - start + 1 for start, end in AUTO_BLOCKS[1:]) / RATE_HZ


def auto_blocks():
    """
    The automatic blocks as apply_edits receives them.
    """
    return [{"block_id": f"{SESSION}_{epoch}_{i:02d}", "session_id": SESSION, "epoch": epoch, "environment": env,
             "frame_start": start, "frame_end": end}
            for (start, end), (epoch, env, i) in zip(AUTO_BLOCKS, [("arena", "open_arena", 1), ("track", "triple_t", 1),
                                                                    ("track", "triple_t", 2), ("track", "triple_t", 3)])]


def ranges(blocks):
    """
    The (frame_start, frame_end, status) of each block.
    """
    return [(b["frame_start"], b["frame_end"], b["status"]) for b in blocks]


def still_frames(span):
    """
    The synthetic frames with every light standing where it was from STILL_LEAD frames before the (first, last) span to as many after.
    """
    columns = frames_table().to_pydict()
    at = slice(span[0] - 1 - STILL_LEAD, span[1] + STILL_LEAD)
    for name in LIGHT_COLUMNS:
        values = np.array(columns[name])
        values[at] = values[at.start]
        columns[name] = values
    return pa.table(columns)


def test_sessions_are_listed_unreviewed_first_then_oldest_review_first_with_the_review_facts(transformed, processed):
    sessions = data.list_sessions(transformed, processed)
    assert [(s["session_id"], s["reviewed"], s["n_automatic"], [e["epoch"] for e in s["epochs"]]) for s in sessions] == [
        (SESSION, False, 4, ["arena", "track"])]
    assert sessions[0]["date"] == "2015-01-01" and sessions[0]["reviewed_at"] is None and sessions[0]["n_confirmed"] == 0
    write_sessions(transformed, [SESSION, "old", "new"])
    session = data.load_session(transformed, SESSION)
    old = data.review_of(session, [{"op": "drop", "frame": 1000}, {"op": "accept"}], "shaky camera", STAMP)
    new = data.review_of(session, [{"op": "accept"}], "", STAMP)
    data.write_review(processed, {**old, "session_id": "old", "reviewed_at": "2026-10-13T08:00:00+00:00"})
    data.write_review(processed, {**new, "session_id": "new", "reviewed_at": "2026-10-13T09:00:00+00:00"})
    sessions = data.list_sessions(transformed, processed)
    assert [s["session_id"] for s in sessions] == [SESSION, "old", "new"]
    assert (sessions[1]["n_confirmed"], sessions[1]["notes"], sessions[1]["reviewed_by"]) == (3, "shaky camera", old["reviewed_by"])
    assert sessions[1]["confirmed_s"] == {"arena": 0.0, "track": TRACK_S}
    assert sessions[2]["confirmed_s"] == {"arena": 30.0, "track": TRACK_S}


def test_the_automatic_count_is_read_once_per_session_and_again_once_forgotten(transformed, processed, monkeypatch):
    write_sessions(transformed, [SESSION, "other"])
    reads = []
    blocks_of = select.blocks_of
    monkeypatch.setattr(select, "blocks_of", lambda source, epochs, sessions: reads.append(sessions[0]["session_id"]) or blocks_of(source, epochs, sessions))
    assert [s["n_automatic"] for s in data.list_sessions(transformed, processed)] == [4, 4]
    assert sorted(reads) == [SESSION, "other"] and data.AUTOMATIC_COUNTS == {SESSION: 4, "other": 4}
    data.list_sessions(transformed, processed)
    assert len(reads) == 2
    data.AUTOMATIC_COUNTS.pop(SESSION)
    data.list_sessions(transformed, processed)
    assert reads[2:] == [SESSION]
    data.AUTOMATIC_COUNTS.clear()
    data.load_session(transformed, "other")
    assert data.AUTOMATIC_COUNTS == {"other": 4} and reads[3:] == ["other"]


def test_the_time_since_a_save_names_the_largest_unit_that_fits():
    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    stamps = [(now - timedelta(seconds=s)).isoformat(timespec="seconds") for s in (30, 90, 3 * 3600 + 100, 2 * 86400)]
    assert [data.time_since(stamp, now) for stamp in stamps] == [data.JUST_NOW, "1 min ago", "3 h ago", "2 d ago"]


def test_a_session_loads_with_the_processors_cut_points_and_heading_fill_and_its_automatic_blocks_equal_to_cut_at(transformed):
    session = data.load_session(transformed, SESSION)
    assert all(len(session[name]) == N_FRAMES for name in ARRAYS)
    assert session["x"][GAP[0] - 1] is None and session["n_lights"][GAP[0] - 1] == 0 and session["n_lights"][0] == 2
    assert session["cuts"] == {"pauses": [PAUSE], "jumps": [JUMP], "gaps": [GAP], "margins": MARGINS}
    assert session["heading_filled"] == [GAP, SHORT_HEADING_GAP] and session["heading_lost"] == [LONG_HEADING_GAP]
    assert session["heading_held"] == []
    assert session["heading"][SHORT_HEADING_GAP[0] - 1] is not None and session["heading"][LONG_HEADING_GAP[0] - 1] is None
    assert session["n_lights"][SHORT_HEADING_GAP[0] - 1] == 1
    grids = session["occupancy"]
    assert list(grids) == ["arena", "track"] and all(np.shape(g["z"]) == (data.OCCUPANCY_BINS,) * 2 for g in grids.values())
    assert grids["arena"]["x"] == grids["track"]["x"]
    assert np.expm1(grids["arena"]["z"]).sum() == pytest.approx(2400) and np.expm1(grids["track"]["z"]).sum() == pytest.approx(6550)
    assert [(r["run"], r["path_id"], r["clean"]) for r in session["runs"]] == [(1, 3, True), (2, 7, False), (3, 3, True)]
    assert [(b["block_id"], b["frame_start"], b["frame_end"]) for b in session["blocks"]] == [
        (f"{SESSION}_arena_01", 301, 2100), (f"{SESSION}_track_01", 2701, 3999), (f"{SESSION}_track_02", 4050, 5700),
        (f"{SESSION}_track_03", 6301, 7700)]
    frames = select.read_frames(transformed, SESSION)
    for epoch in session["epochs"]:
        cut = select.cut_at(frames, epoch, MAX_GAP, RATE_HZ)
        assert [(s["frame_start"], s["frame_end"]) for s in session["stretches"] if s["epoch"] == epoch["epoch"]] == cut
        kept = [b for b in cut if select.long_enough(b, RATE_HZ)]
        assert [(b["frame_start"], b["frame_end"]) for b in session["blocks"] if b["epoch"] == epoch["epoch"]] == kept
    assert session["heading"][0] == pytest.approx(data.wrapped(frames["head_dir"][0] - session["led_offset"]["rad"]),
                                                  abs=10 ** -data.DECIMALS)
    json.dumps(session)


def test_a_long_heading_gap_over_a_still_rat_is_held_at_the_heading_before_it_and_drawn_as_the_held_band(transformed):
    write_sessions(transformed, [SESSION, "still"])
    pq.write_table(still_frames(LONG_HEADING_GAP), transformed / "frames" / "still.parquet")
    session = data.load_session(transformed, "still")
    assert session["heading_held"] == [LONG_HEADING_GAP] and session["heading_lost"] == []
    assert session["heading_filled"] == [GAP, SHORT_HEADING_GAP]
    before, held = session["heading"][LONG_HEADING_GAP[0] - 2], session["heading"][LONG_HEADING_GAP[0] - 1:LONG_HEADING_GAP[1]]
    assert before is not None and held == [before] * (LONG_HEADING_GAP[1] - LONG_HEADING_GAP[0] + 1)
    assert session["speed"][LONG_HEADING_GAP[0] - 1] == 0.0 and session["speed"][LONG_HEADING_GAP[0] - 2 - STILL_LEAD] > 0.0


def test_the_led_offset_recovers_a_known_mounting_angle():
    n, radius, mounting = 1200, 150.0, np.deg2rad(105)
    t = np.arange(n) / RATE_HZ
    x, y = radius * np.cos(t), radius * np.sin(t)
    heading = np.arctan2(np.gradient(y), np.gradient(x)) + mounting + np.random.default_rng(0).normal(0, 0.1, n)
    offset = data.led_offset(heading, data.motion_direction(t, x, y), data.speed_from_positions(t, x, y))
    assert abs(np.rad2deg(offset["rad"]) - 105) < 3 and offset["r"] > 0.9
    assert data.led_offset(heading, data.motion_direction(t, x, y), np.zeros(n)) == {"rad": 0.0, "r": 0.0}


def test_accept_confirms_the_automatic_blocks_as_drawn():
    blocks = data.apply_edits(auto_blocks(), [{"op": "accept"}], EDIT_SESSION)
    assert ranges(blocks) == [(s, e, "confirmed") for s, e in AUTO_BLOCKS]
    assert [b["block_id"] for b in blocks] == [b["block_id"] for b in auto_blocks()]
    assert all(b["note"] == "" for b in blocks)


def test_a_moved_edge_snaps_to_the_nearest_run_edge_and_stays_inside_its_stretch():
    edits = [{"op": "move", "frame": 2790, "edge": "start", "at": 2701}, {"op": "move", "frame": 4610, "edge": "end", "at": 4050}]
    blocks = data.apply_edits(auto_blocks(), edits, EDIT_SESSION)
    assert ranges(blocks)[1:3] == [(2800, 3999, "edited"), (4050, 4620, "edited")]
    blocks = data.apply_edits(auto_blocks(), [{"op": "move", "frame": 4040, "edge": "end", "at": 2701}], EDIT_SESSION)
    assert ranges(blocks)[1] == (2701, 3999, "edited")
    runs = TRACK_RUNS + [{"epoch": "track", "run": 4, "path_id": 1, "clean": True, "frame_start": 3980, "frame_end": 4120}]
    edits = [{"op": "move", "frame": 4020, "edge": "start", "at": 4050}]
    blocks = data.apply_edits(auto_blocks(), edits, {**EDIT_SESSION, "runs": runs})
    assert ranges(blocks)[1:3] == [(2701, 3999, "auto"), (4050, 5700, "edited")]
    blocks = data.apply_edits(auto_blocks(), [{"op": "move", "frame": 1500, "edge": "end", "at": 301}], EDIT_SESSION)
    assert ranges(blocks)[0] == (301, 1500, "edited")
    blocks = data.apply_edits(auto_blocks(), [{"op": "move", "frame": 6500, "edge": "end", "at": 4050}], EDIT_SESSION)
    assert ranges(blocks)[2:] == [(4050, 5700, "edited"), (6301, 7700, "auto")]


def test_confirm_toggles_an_auto_block_and_leaves_a_dropped_one():
    edits = [{"op": "drop", "frame": 7000}, {"op": "confirm", "frame": 7000}, {"op": "confirm", "frame": 2800},
             {"op": "confirm", "frame": 1000}, {"op": "confirm", "frame": 1000}]
    blocks = data.apply_edits(auto_blocks(), edits, EDIT_SESSION)
    assert [b["status"] for b in blocks] == ["auto", "confirmed", "auto", "dropped"]


def test_a_new_block_is_refused_over_a_cut_a_kept_block_or_under_ten_seconds_and_added_otherwise():
    blocks = data.apply_edits(auto_blocks(), [{"op": "drop", "frame": 5000}], EDIT_SESSION)
    refused = {"frame_start": 3990, "frame_end": 4100}, {"frame_start": 7600, "frame_end": 7800}, \
        {"frame_start": 2000, "frame_end": 2800}, {"frame_start": 4100, "frame_end": 4698}, {"frame_start": 2800, "frame_end": 3999}
    assert [data.refusal(blocks, edit, EDIT_SESSION) for edit in refused] == [
        data.CROSSES_MESSAGE, data.CROSSES_MESSAGE, data.CROSSES_MESSAGE, data.SHORT_MESSAGE, data.OVERLAPS_MESSAGE]
    edit = {"op": "new", "frame_start": 4100, "frame_end": 5000}
    assert data.refusal(blocks, edit, EDIT_SESSION) is None
    blocks = data.apply_edits(auto_blocks(), [{"op": "drop", "frame": 5000}, edit], EDIT_SESSION)
    assert ranges(blocks)[2:4] == [(4050, 5700, "dropped"), (4100, 5000, "edited")]
    assert (blocks[3]["block_id"], blocks[3]["epoch"], blocks[3]["environment"]) == (f"{SESSION}_track_03", "track", "triple_t")


def test_a_split_gives_two_blocks_renumbered_in_order():
    blocks = data.apply_edits(auto_blocks(), [{"op": "split", "frame": 3000}], EDIT_SESSION)
    assert ranges(blocks) == [(301, 2100, "auto"), (2701, 2999, "edited"), (3000, 3999, "edited"), (4050, 5700, "auto"),
                              (6301, 7700, "auto")]
    assert [b["block_id"].rsplit("_", 2)[-2:] for b in blocks] == [
        ["arena", "01"], ["track", "01"], ["track", "02"], ["track", "03"], ["track", "04"]]
    assert data.apply_edits(auto_blocks(), [{"op": "split", "frame": 2701}], EDIT_SESSION) == \
        data.apply_edits(auto_blocks(), [], EDIT_SESSION)


def test_a_drop_marks_one_block_and_dropping_again_takes_it_back():
    blocks = data.apply_edits(auto_blocks(), [{"op": "drop", "frame": 7000}], EDIT_SESSION)
    assert ranges(blocks)[3] == (6301, 7700, "dropped") and ranges(blocks)[2] == (4050, 5700, "auto")
    blocks = data.apply_edits(auto_blocks(), [{"op": "drop", "frame": 7000}, {"op": "drop", "frame": 7000}], EDIT_SESSION)
    assert ranges(blocks)[3] == (6301, 7700, "edited")


def test_a_cut_splits_the_block_and_drops_a_piece_under_ten_seconds():
    edits = [{"op": "cut", "frame_start": 4600, "frame_end": 5000}]
    blocks = data.apply_edits(auto_blocks(), edits, EDIT_SESSION)
    assert ranges(blocks)[2:4] == [(4050, 4599, "dropped"), (5001, 5700, "edited")]
    assert blocks[2]["note"] == data.SHORT_NOTE and blocks[3]["note"] == ""
    blocks = data.apply_edits(auto_blocks(), [{"op": "cut", "frame_start": 6000, "frame_end": 8000}], EDIT_SESSION)
    assert ranges(blocks)[2:] == [(4050, 5700, "auto"), (6301, 7700, "dropped")]
    assert blocks[3]["note"] == data.INSIDE_NOTE
    assert data.cuts_of(edits) == [{"frame_start": 4600, "frame_end": 5000, "reason": data.CUT_REASON}]


def test_an_edit_whose_block_or_room_is_gone_is_skipped_and_counted():
    stale = [{"op": "move", "frame": 2790, "edge": "start", "at": 2500}, {"op": "drop", "frame": 2500},
             {"op": "split", "frame": 2500}, {"op": "confirm", "frame": 2500},
             {"op": "new", "frame_start": 2800, "frame_end": 3999}]
    blocks, skipped = data.replayed(auto_blocks(), stale + [{"op": "flag", "run": 1}, {"op": "accept"}], EDIT_SESSION)
    assert skipped == stale and ranges(blocks) == [(s, e, "confirmed") for s, e in AUTO_BLOCKS]
    assert data.apply_edits(auto_blocks(), stale, EDIT_SESSION) == data.apply_edits(auto_blocks(), [], EDIT_SESSION)


def test_flagging_a_run_twice_takes_the_flag_back():
    edits = [{"op": "flag", "run": 2}, {"op": "flag", "run": 1}, {"op": "flag", "run": 2}]
    assert data.flagged_runs(edits) == [1]


def test_windows_are_counted_by_length_and_stride_and_a_short_block_yields_none():
    assert [data.windows_in(seconds, 40, 10) for seconds in (39.9, 40, 49.9, 50, 100)] == [0, 1, 1, 2, 7]
    assert data.windows_in(17.5, 10, 5) == 2


def test_the_summary_counts_statuses_block_time_windows_cuts_and_heading_seconds(transformed):
    session = data.load_session(transformed, SESSION)
    blocks = data.apply_edits(session["blocks"], [{"op": "confirm", "frame": 1000}, {"op": "drop", "frame": 7000}], session)
    summary = data.summary(session, blocks, 10, 5)
    assert summary["statuses"] == {"auto": 2, "confirmed": 1, "edited": 0, "dropped": 1}
    assert summary["kept_s"] == pytest.approx((1800 + 1299 + 1651) / RATE_HZ) and summary["epoch_s"] == 9000 / RATE_HZ
    assert summary["windows"] == 5 + 3 + 4 and summary["cuts"] == {"pauses": 1, "jumps": 1, "gaps": 1, "margins": 8}
    assert (summary["heading_lost_s"], summary["heading_filled_s"]) == (5.0, pytest.approx(110 / RATE_HZ))
    assert data.heading_in(session, 6301, 7700) == {"heading_lost_s": 5.0, "heading_filled_s": 0.0}
    assert data.heading_in(session, 4050, 5700) == {"heading_lost_s": 0.0, "heading_filled_s": 1.0}


def test_the_review_file_round_trips_and_is_overwritten(transformed, processed):
    session = data.load_session(transformed, SESSION)
    edits = [{"op": "split", "frame": 3000}, {"op": "flag", "run": 2}, {"op": "accept"}]
    review = data.review_of(session, edits, "camera shook", STAMP)
    assert review["session_id"] == SESSION and review["converter_manifest_timestamp"] == STAMP
    assert review["rules"] == {"GAP_LIGHTS": "both", "JUMP_PX": 40.0, "PAUSE_MARGIN_SEC": 5.0, "MIN_BLOCK_S": 10.0,
                               "HEADING_FILL_SEC": 3.0, "RUNNING_FLOOR_M_PER_S": 0.03}
    assert review["flagged_runs"] == [2] and review["cuts"] == [] and review["notes"] == "camera shook"
    assert [tuple(b) for b in review["blocks"]] == [data.BLOCK_KEYS] * 5
    assert [b["status"] for b in review["blocks"]] == ["confirmed", "edited", "edited", "confirmed", "confirmed"]
    path = data.write_review(processed, review)
    assert path == processed / "review" / f"{SESSION}.json" and data.read_review(processed, SESSION) == review
    data.write_review(processed, {**review, "notes": "second look"})
    assert data.read_review(processed, SESSION)["notes"] == "second look"
    assert data.read_review(processed, "other") is None
