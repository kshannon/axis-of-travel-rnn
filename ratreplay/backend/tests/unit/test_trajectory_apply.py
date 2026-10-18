"""
TrajectoryEngine.apply on a scripted session: each op, the refusals and their reasons, the rules the session carries. Ported from the old tests of the edit rules.
"""

from copy import deepcopy
from pathlib import Path

from fixtures import S1

from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.trajectory import RULES, TrajectoryEngine
from ratreplay_api.engines.trajectory import edits as rules_of

ENVIRONMENTS = Path(__file__).resolve().parents[4] / "configs" / "environments"
RATE_HZ = 60

# An arena block of 1800 frames, then track blocks over three stretches, a fourth stretch too short to keep and the
# cuts between them. The track holds three runs.
STRETCHES = [("arena", 301, 2100), ("track", 2701, 3999), ("track", 4050, 5700), ("track", 6301, 7700), ("track", 8301, 8700)]
ENVIRONMENT_OF = {"arena": "open_arena", "track": "triple_t"}
RUNS = [{"epoch": "track", "run": 1, "path_id": 3, "clean": True, "frame_start": 2800, "frame_end": 2920},
        {"epoch": "track", "run": 2, "path_id": 7, "clean": False, "frame_start": 3100, "frame_end": 3200},
        {"epoch": "track", "run": 3, "path_id": 3, "clean": True, "frame_start": 4500, "frame_end": 4620}]
BLOCKS = [{"block_id": f"{S1}_{epoch}_{i:02d}", "epoch": epoch, "environment": ENVIRONMENT_OF[epoch], "frame_start": start,
           "frame_end": end, "status": "auto", "note": None}
          for (epoch, start, end), i in zip(STRETCHES[:4], [1, 1, 2, 3])]
SESSION = {"rules": RULES, "session_id": S1, "rate_hz": RATE_HZ, "runs": RUNS,
           "stretches": [{"epoch": epoch, "frame_start": start, "frame_end": end} for epoch, start, end in STRETCHES],
           "epochs": [{"epoch": epoch, "environment": environment} for epoch, environment in ENVIRONMENT_OF.items()]}
AUTO = [(start, end) for _, start, end in STRETCHES[:4]]
TOO_SHORT = rules_of.TOO_SHORT_MESSAGE.format(10.0)


def apply(edits, blocks=BLOCKS, session=SESSION):
    """
    The engine's apply on the scripted blocks.
    """
    return TrajectoryEngine().apply(blocks, edits, session)


def made(edits, session=SESSION):
    """
    The blocks the edits make of the automatic blocks.
    """
    return apply(edits, session=session)["blocks"]


def ranges(blocks):
    """
    The (frame_start, frame_end, status) of each block.
    """
    return [(b["frame_start"], b["frame_end"], b["status"]) for b in blocks]


def refused(edits, blocks=BLOCKS, session=SESSION):
    """
    The (index, op, reason) of each edit the engine refuses.
    """
    return [(r["index"], r["op"], r["reason"]) for r in apply(edits, blocks, session)["refusals"]]


def test_accept_confirms_the_automatic_blocks_as_drawn():
    blocks = made([{"op": "accept"}])
    assert ranges(blocks) == [(s, e, "confirmed") for s, e in AUTO]
    assert [b["block_id"] for b in blocks] == [b["block_id"] for b in BLOCKS]
    assert all(b["note"] is None for b in blocks)


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
    ranges_refused = [(3990, 4100), (7600, 7800), (2000, 2800), (4100, 4698), (2800, 3999)]
    edits = [{"op": "new", "frame_start": first, "frame_end": last} for first, last in ranges_refused]
    assert [reason for _, _, reason in refused(edits, dropped)] == [
        rules_of.CROSSES_MESSAGE, rules_of.CROSSES_MESSAGE, rules_of.CROSSES_MESSAGE, rules_of.SHORT_MESSAGE.format(10.0), rules_of.OVERLAPS_MESSAGE]
    blocks = made([{"op": "drop", "frame": 5000}, {"op": "new", "frame_start": 4100, "frame_end": 5000}])
    assert ranges(blocks)[2:4] == [(4050, 5700, "dropped"), (4100, 5000, "edited")]
    assert (blocks[3]["block_id"], blocks[3]["epoch"], blocks[3]["environment"], blocks[3]["note"]) == (f"{S1}_track_03", "track", "triple_t", None)


def test_a_split_gives_two_blocks_renumbered_in_order():
    blocks = made([{"op": "split", "frame": 3301}])
    assert ranges(blocks) == [(301, 2100, "auto"), (2701, 3300, "edited"), (3301, 3999, "edited"), (4050, 5700, "auto"), (6301, 7700, "auto")]
    assert [b["block_id"].rsplit("_", 2)[-2:] for b in blocks] == [["arena", "01"], ["track", "01"], ["track", "02"], ["track", "03"], ["track", "04"]]
    assert apply([{"op": "split", "frame": 2701}]) == apply([])


def test_a_drop_marks_one_block_and_dropping_again_takes_it_back():
    blocks = made([{"op": "drop", "frame": 7000}])
    assert ranges(blocks)[3] == (6301, 7700, "dropped") and ranges(blocks)[2] == (4050, 5700, "auto")
    assert ranges(made([{"op": "drop", "frame": 7000}, {"op": "drop", "frame": 7000}]))[3] == (6301, 7700, "edited")


def test_a_removed_block_cannot_come_back_over_a_kept_block_by_a_drop_a_move_a_split_or_a_cut():
    standing = [{"op": "drop", "frame": 5000}, {"op": "new", "frame_start": 4100, "frame_end": 5000}]
    restores = [{"op": "drop", "frame": 4060}, {"op": "move", "frame": 4070, "edge": "start", "at": 4060},
                {"op": "split", "frame": 4070}, {"op": "cut", "frame_start": 5100, "frame_end": 5200}]
    for restore in restores:
        result = apply([*standing, restore])
        assert ranges(result["blocks"])[2:4] == [(4050, 5700, "dropped"), (4100, 5000, "edited")], restore
        assert result["refusals"] == [{"index": 2, "op": restore["op"], "reason": rules_of.RESTORES_MESSAGE}]
    # Once the kept block is removed too, the block comes back.
    assert ranges(made([*standing, {"op": "drop", "frame": 4500}, restores[0]]))[2:4] == [(4050, 5700, "edited"), (4100, 5000, "dropped")]


def test_a_cut_splits_the_block_and_drops_a_piece_under_ten_seconds():
    edits = [{"op": "cut", "frame_start": 4600, "frame_end": 5000}]
    result = apply(edits)
    blocks = result["blocks"]
    assert ranges(blocks)[2:4] == [(4050, 4599, "dropped"), (5001, 5700, "edited")]
    assert blocks[2]["note"] == rules_of.SHORT_NOTE.format(10.0) and blocks[3]["note"] is None
    blocks = made([{"op": "cut", "frame_start": 6000, "frame_end": 8000}])
    assert ranges(blocks)[2:] == [(4050, 5700, "auto"), (6301, 7700, "dropped")]
    assert blocks[3]["note"] == rules_of.INSIDE_NOTE
    assert result["cuts"] == [{"frame_start": 4600, "frame_end": 5000, "reason": rules_of.CUT_REASON}]


def test_an_edit_whose_block_or_room_is_gone_is_skipped_with_its_index_and_reason():
    stale = [{"op": "move", "frame": 2790, "edge": "start", "at": 2500}, {"op": "drop", "frame": 2500},
             {"op": "split", "frame": 2500}, {"op": "confirm", "frame": 2500},
             {"op": "new", "frame_start": 2800, "frame_end": 3999}]
    result = apply([*stale, {"op": "flag", "run": 1}, {"op": "accept"}])
    gone = rules_of.NO_BLOCK.format(2500)
    assert [(r["index"], r["op"], r["reason"]) for r in result["refusals"]] == [
        (0, "move", gone), (1, "drop", gone), (2, "split", gone), (3, "confirm", gone), (4, "new", rules_of.OVERLAPS_MESSAGE)]
    assert ranges(result["blocks"]) == [(s, e, "confirmed") for s, e in AUTO]
    assert apply(stale)["blocks"] == apply([])["blocks"]


def test_an_unknown_op_is_refused_with_a_reason_and_the_other_edits_still_apply():
    result = apply([{"op": "rotate", "frame": 3301}, {"op": "split", "frame": 3301}])
    assert result["refusals"] == [{"index": 0, "op": "rotate", "reason": "rotate is not an edit op"}]
    assert ranges(result["blocks"])[1:3] == [(2701, 3300, "edited"), (3301, 3999, "edited")]


def test_flagging_a_run_twice_takes_the_flag_back_and_a_flag_is_never_refused():
    result = apply([{"op": "flag", "run": 2}, {"op": "flag", "run": 1}, {"op": "flag", "run": 2}])
    assert result["flagged_runs"] == [1] and result["refusals"] == [] and result["blocks"] == apply([])["blocks"]


def test_a_split_or_a_move_that_would_leave_a_kept_block_under_the_minimum_length_is_refused():
    short = [{"op": "split", "frame": 7695}, {"op": "move", "frame": 7690, "edge": "start", "at": 6301}]
    for edit in short:
        result = apply([edit])
        assert ranges(result["blocks"])[3] == (6301, 7700, "auto"), edit
        assert [(r["op"], r["reason"]) for r in result["refusals"]] == [(edit["op"], TOO_SHORT)]
    result = apply([{"op": "split", "frame": 7000}])
    assert result["refusals"] == [] and ranges(result["blocks"])[3:5] == [(6301, 6999, "edited"), (7000, 7700, "edited")]


def test_the_snap_and_the_minimum_length_are_the_rules_the_session_carries():
    snap = {"op": "move", "frame": 2790, "edge": "start", "at": 2701}
    assert ranges(made([snap]))[1] == (2800, 3999, "edited")
    assert ranges(made([snap], {**SESSION, "rules": {**RULES, "snap_s": 0.0}}))[1] == (2790, 3999, "edited")
    split = {"op": "split", "frame": 7200}
    assert refused([split]) == [(0, "split", TOO_SHORT)]
    assert refused([split], session={**SESSION, "rules": {**RULES, "min_block_s": 5.0}}) == []
    longer = {**SESSION, "rules": {**RULES, "min_block_s": 20.0}}
    assert refused([{"op": "split", "frame": 7000}], session=longer) == [(0, "split", "a kept block must last 20 s or more, remove it instead")]


def test_a_session_from_the_engine_feeds_apply_and_the_input_is_left_unchanged(transformed):
    access = EnvironmentAccess(ENVIRONMENTS)
    environments = {name: access.environment(name) for name in access.environments()}
    found = TransformedAccess(transformed).session(S1)
    session = TrajectoryEngine().session(found, environments, RULES)
    initial, before = session["initial_blocks"], deepcopy(session)
    edits = [{"op": "split", "frame": 2701}, {"op": "move", "frame": 2230, "edge": "start", "at": 2101}, {"op": "drop", "frame": 301},
             {"op": "new", "frame_start": 400, "frame_end": 1200}, {"op": "flag", "run": 3}]
    result = TrajectoryEngine().apply(initial, edits, session)
    assert set(result) == {"blocks", "refusals", "cuts", "flagged_runs"} and result["flagged_runs"] == [3] and result["cuts"] == []
    assert result["refusals"] == [{"index": 1, "op": "move", "reason": TOO_SHORT}]
    assert ranges(result["blocks"]) == [(301, 1500, "dropped"), (400, 1200, "edited"), (2101, 2700, "edited"), (2701, 3300, "edited")]
    assert [b["block_id"] for b in result["blocks"]] == [f"{S1}_arena_01", f"{S1}_arena_02", f"{S1}_track_01", f"{S1}_track_02"]
    assert [b["environment"] for b in result["blocks"]] == ["open_arena", "open_arena", "triple_t", "triple_t"]
    assert all(tuple(b) == rules_of.BLOCK_KEYS and b["note"] is None for b in result["blocks"])
    assert session["initial_blocks"] == before["initial_blocks"] and session["stretches"] == before["stretches"]
