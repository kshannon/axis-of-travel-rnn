"""
The edit rules on a scripted session: each op, the refusals, the review file's content. Ported from the old tool's tests of src/ratreplay/data.py.
"""

from fixtures import S1, STAMP
from ratreplay_api.engines import edits as engine

RATE_HZ = 60

# An arena block of 1800 frames, then track blocks over three stretches, a fourth stretch too short to keep and the processor's
# cuts between them. The track holds three runs.
STRETCHES = [("arena", 301, 2100), ("track", 2701, 3999), ("track", 4050, 5700), ("track", 6301, 7700), ("track", 8301, 8700)]
ENVIRONMENTS = {"arena": "open_arena", "track": "triple_t"}
RUNS = [{"epoch": "track", "run": 1, "path_id": 3, "clean": True, "frame_start": 2800, "frame_end": 2920},
        {"epoch": "track", "run": 2, "path_id": 7, "clean": False, "frame_start": 3100, "frame_end": 3200},
        {"epoch": "track", "run": 3, "path_id": 3, "clean": True, "frame_start": 4500, "frame_end": 4620}]
BLOCKS = [{"block_id": f"{S1}_{epoch}_{i:02d}", "session_id": S1, "epoch": epoch, "environment": ENVIRONMENTS[epoch],
           "frame_start": start, "frame_end": end}
          for (epoch, start, end), i in zip(STRETCHES[:4], [1, 1, 2, 3])]
SESSION = {"session_id": S1, "runs": RUNS, "rate_hz": RATE_HZ, "blocks": BLOCKS,
           "stretches": [{"epoch": epoch, "frame_start": start, "frame_end": end} for epoch, start, end in STRETCHES],
           "epochs": [{"epoch": epoch, "environment": environment} for epoch, environment in ENVIRONMENTS.items()]}
AUTO = [(start, end) for _, start, end in STRETCHES[:4]]


def made(edits, session=SESSION):
    """
    The blocks the edits make of the automatic blocks.
    """
    return engine.apply_edits(session["blocks"], edits, session)[0]


def ranges(blocks):
    """
    The (frame_start, frame_end, status) of each block.
    """
    return [(b["frame_start"], b["frame_end"], b["status"]) for b in blocks]


def test_accept_confirms_the_automatic_blocks_as_drawn():
    blocks = made([{"op": "accept"}])
    assert ranges(blocks) == [(s, e, "confirmed") for s, e in AUTO]
    assert [b["block_id"] for b in blocks] == [b["block_id"] for b in BLOCKS]
    assert all(b["note"] == "" for b in blocks)


def test_a_moved_edge_snaps_to_the_nearest_run_edge_and_stays_inside_its_stretch():
    edits = [{"op": "move", "frame": 2790, "edge": "start", "at": 2701}, {"op": "move", "frame": 4700, "edge": "end", "at": 4050}]
    assert ranges(made(edits))[1:3] == [(2800, 3999, "edited"), (4050, 4700, "edited")]
    assert ranges(made([{"op": "move", "frame": 4040, "edge": "end", "at": 2701}]))[1] == (2701, 3999, "edited")
    runs = RUNS + [{"epoch": "track", "run": 4, "path_id": 1, "clean": True, "frame_start": 3980, "frame_end": 4120}]
    blocks = made([{"op": "move", "frame": 4020, "edge": "start", "at": 4050}], {**SESSION, "runs": runs})
    assert ranges(blocks)[1:3] == [(2701, 3999, "auto"), (4050, 5700, "edited")]
    assert ranges(made([{"op": "move", "frame": 1500, "edge": "end", "at": 301}]))[0] == (301, 1500, "edited")
    assert ranges(made([{"op": "move", "frame": 6500, "edge": "end", "at": 4050}]))[2:] == [(4050, 5700, "edited"), (6301, 7700, "auto")]


def test_confirm_toggles_an_auto_block_and_leaves_a_dropped_one():
    edits = [{"op": "drop", "frame": 7000}, {"op": "confirm", "frame": 7000}, {"op": "confirm", "frame": 2800},
             {"op": "confirm", "frame": 1000}, {"op": "confirm", "frame": 1000}]
    assert [b["status"] for b in made(edits)] == ["auto", "confirmed", "auto", "dropped"]


def test_a_new_block_is_refused_over_a_cut_a_kept_block_or_under_ten_seconds_and_added_otherwise():
    dropped = made([{"op": "drop", "frame": 5000}])
    refused = [(3990, 4100), (7600, 7800), (2000, 2800), (4100, 4698), (2800, 3999)]
    edits = [{"op": "new", "frame_start": first, "frame_end": last} for first, last in refused]
    assert [engine.refusal(dropped, edit, SESSION) for edit in edits] == [
        engine.CROSSES_MESSAGE, engine.CROSSES_MESSAGE, engine.CROSSES_MESSAGE, engine.SHORT_MESSAGE, engine.OVERLAPS_MESSAGE]
    new = {"op": "new", "frame_start": 4100, "frame_end": 5000}
    assert engine.refusal(dropped, new, SESSION) is None
    blocks = made([{"op": "drop", "frame": 5000}, new])
    assert ranges(blocks)[2:4] == [(4050, 5700, "dropped"), (4100, 5000, "edited")]
    assert (blocks[3]["block_id"], blocks[3]["epoch"], blocks[3]["environment"]) == (f"{S1}_track_03", "track", "triple_t")


def test_a_split_gives_two_blocks_renumbered_in_order():
    blocks = made([{"op": "split", "frame": 3301}])
    assert ranges(blocks) == [(301, 2100, "auto"), (2701, 3300, "edited"), (3301, 3999, "edited"), (4050, 5700, "auto"), (6301, 7700, "auto")]
    assert [b["block_id"].rsplit("_", 2)[-2:] for b in blocks] == [["arena", "01"], ["track", "01"], ["track", "02"], ["track", "03"], ["track", "04"]]
    assert engine.apply_edits(BLOCKS, [{"op": "split", "frame": 2701}], SESSION) == engine.apply_edits(BLOCKS, [], SESSION)


def test_a_drop_marks_one_block_and_dropping_again_takes_it_back():
    blocks = made([{"op": "drop", "frame": 7000}])
    assert ranges(blocks)[3] == (6301, 7700, "dropped") and ranges(blocks)[2] == (4050, 5700, "auto")
    assert ranges(made([{"op": "drop", "frame": 7000}, {"op": "drop", "frame": 7000}]))[3] == (6301, 7700, "edited")


def test_a_removed_block_cannot_come_back_over_a_kept_block_by_a_drop_a_move_a_split_or_a_cut():
    standing = [{"op": "drop", "frame": 5000}, {"op": "new", "frame_start": 4100, "frame_end": 5000}]
    restores = [{"op": "drop", "frame": 4060}, {"op": "move", "frame": 4070, "edge": "start", "at": 4060},
                {"op": "split", "frame": 4070}, {"op": "cut", "frame_start": 5100, "frame_end": 5200}]
    for restore in restores:
        blocks, skipped = engine.apply_edits(BLOCKS, [*standing, restore], SESSION)
        assert ranges(blocks)[2:4] == [(4050, 5700, "dropped"), (4100, 5000, "edited")], restore
        assert skipped == [{**restore, "reason": engine.RESTORES_MESSAGE}]
    # Once the kept block is removed too, the block comes back.
    assert ranges(made([*standing, {"op": "drop", "frame": 4500}, restores[0]]))[2:4] == [(4050, 5700, "edited"), (4100, 5000, "dropped")]


def test_a_cut_splits_the_block_and_drops_a_piece_under_ten_seconds():
    edits = [{"op": "cut", "frame_start": 4600, "frame_end": 5000}]
    blocks = made(edits)
    assert ranges(blocks)[2:4] == [(4050, 4599, "dropped"), (5001, 5700, "edited")]
    assert blocks[2]["note"] == engine.SHORT_NOTE and blocks[3]["note"] == ""
    blocks = made([{"op": "cut", "frame_start": 6000, "frame_end": 8000}])
    assert ranges(blocks)[2:] == [(4050, 5700, "auto"), (6301, 7700, "dropped")]
    assert blocks[3]["note"] == engine.INSIDE_NOTE
    assert engine.cuts_of(edits) == [{"frame_start": 4600, "frame_end": 5000, "reason": engine.CUT_REASON}]


def test_an_edit_whose_block_or_room_is_gone_is_skipped_with_its_reason():
    stale = [{"op": "move", "frame": 2790, "edge": "start", "at": 2500}, {"op": "drop", "frame": 2500},
             {"op": "split", "frame": 2500}, {"op": "confirm", "frame": 2500},
             {"op": "new", "frame_start": 2800, "frame_end": 3999}]
    blocks, skipped = engine.apply_edits(BLOCKS, [*stale, {"op": "flag", "run": 1}, {"op": "accept"}], SESSION)
    gone = engine.NO_BLOCK.format(2500)
    assert [(e["op"], e["reason"]) for e in skipped] == [("move", gone), ("drop", gone), ("split", gone), ("confirm", gone),
                                                         ("new", engine.OVERLAPS_MESSAGE)]
    assert ranges(blocks) == [(s, e, "confirmed") for s, e in AUTO]
    assert engine.apply_edits(BLOCKS, stale, SESSION)[0] == engine.apply_edits(BLOCKS, [], SESSION)[0]


def test_flagging_a_run_twice_takes_the_flag_back():
    edits = [{"op": "flag", "run": 2}, {"op": "flag", "run": 1}, {"op": "flag", "run": 2}]
    assert engine.flagged_runs(edits) == [1]


def test_a_review_holds_the_blocks_cuts_flags_notes_and_rules_with_who_and_when_it_was_given():
    edits = [{"op": "split", "frame": 3301}, {"op": "flag", "run": 2}, {"op": "accept"}]
    review = engine.review_of(SESSION, edits, "camera shook", STAMP, "kyle", "2026-10-16T09:00:00+00:00")
    assert review == engine.review_of(SESSION, edits, "camera shook", STAMP, "kyle", "2026-10-16T09:00:00+00:00")
    assert (review["session_id"], review["reviewed_by"], review["reviewed_at"]) == (S1, "kyle", "2026-10-16T09:00:00+00:00")
    assert review["converter_manifest_timestamp"] == STAMP and review["edits"] == edits
    assert review["rules"] == {"GAP_LIGHTS": "both", "JUMP_PX": 40.0, "PAUSE_MARGIN_SEC": 5.0, "MIN_BLOCK_S": 10.0,
                               "HEADING_FILL_SEC": 3.0, "RUNNING_FLOOR_M_PER_S": 0.03}
    assert review["flagged_runs"] == [2] and review["cuts"] == [] and review["notes"] == "camera shook"
    assert [tuple(b) for b in review["blocks"]] == [engine.BLOCK_KEYS] * 5
    assert [b["status"] for b in review["blocks"]] == ["confirmed", "edited", "edited", "confirmed", "confirmed"]


def test_a_split_or_a_move_that_would_leave_a_kept_block_under_the_minimum_length_is_refused():
    short = [{"op": "split", "frame": 7695}, {"op": "move", "frame": 7690, "edge": "start", "at": 6301}]
    for edit in short:
        blocks, skipped = engine.apply_edits(BLOCKS, [edit], SESSION)
        assert ranges(blocks)[3] == (6301, 7700, "auto"), edit
        assert skipped == [{**edit, "reason": engine.TOO_SHORT_MESSAGE}]
    blocks, skipped = engine.apply_edits(BLOCKS, [{"op": "split", "frame": 7000}], SESSION)
    assert skipped == [] and ranges(blocks)[3:5] == [(6301, 6999, "edited"), (7000, 7700, "edited")]
