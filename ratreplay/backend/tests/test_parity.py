"""
Parity with the old tool: the same synthetic session through the new API and through src/ratreplay/data.py gives the same review files, session facts and arrays, except for the documented differences. This file imports the old tool on purpose, it is the parity oracle and nothing else in the backend imports ratreplay. It goes when the old tool does.
"""

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest

from fixtures import S1, S6, STAMP
from ratreplay import data as old_tool
from ratreplay_api.contract import EDIT_FIELDS

ARRAY_COLUMNS = ("t", "x", "y", "heading", "speed")
ROUNDING = 1e-4  # the old tool sends its arrays rounded to 4 decimals
SESSION_KEYS = ("n_frames", "epochs", "runs", "cuts", "blocks", "heading_lost", "heading_filled", "heading_held")

# S1 has an arena block over frames 301 to 1500 and a track block over 2101 to 3300, the track's runs lie in 2200 to 2700.
# Each list comes with the blocks it must leave, so that a list that did nothing in both tools cannot pass.
ACCEPT_ALL = ([{"op": "accept"}], [(301, 1500, "confirmed"), (2101, 3300, "confirmed")])
NEW_OVER_REMOVED_AT_ITS_START = ([{"op": "accept"}, {"op": "drop", "frame": 301}, {"op": "new", "frame_start": 301, "frame_end": 1299}],
                                 [(301, 1500, "dropped"), (301, 1299, "edited"), (2101, 3300, "confirmed")])
SPLIT_DROP_FLAG = ([{"op": "drop", "frame": 1000}, {"op": "split", "frame": 2701}, {"op": "accept"}, {"op": "flag", "run": 2}],
                   [(301, 1500, "dropped"), (2101, 2700, "edited"), (2701, 3300, "edited")])
NEW_OVER_REMOVED_AND_MOVE = ([{"op": "accept"}, {"op": "drop", "frame": 301}, {"op": "new", "frame_start": 399, "frame_end": 1299},
                              {"op": "move", "frame": 2230, "edge": "start", "at": 2101}],
                             [(301, 1500, "dropped"), (399, 1299, "edited"), (2200, 3300, "edited")])


def triples(blocks):
    """
    The frame range and status of each block.
    """
    return [(b["frame_start"], b["frame_end"], b["status"]) for b in blocks]


def old_review(transformed, tmp_path, edits, notes):
    """
    The review file the old tool writes for S1, read back.
    """
    review = old_tool.review_of(old_tool.load_session(transformed, S1), edits, notes, STAMP)
    return json.loads(old_tool.write_review(tmp_path / "old", review).read_text())


@pytest.mark.parametrize("edits, blocks", [ACCEPT_ALL, SPLIT_DROP_FLAG, NEW_OVER_REMOVED_AND_MOVE, NEW_OVER_REMOVED_AT_ITS_START],
                         ids=["accept all", "split drop flag", "new over removed and move", "new over removed at its start"])
def test_a_review_saved_through_the_api_is_the_file_the_old_tool_writes(client, attached, transformed, tmp_path, edits, blocks):
    saved = client.put(f"/api/sources/{attached[0]}/sessions/{S1}/review", json={"edits": edits, "notes": "shaky"}).json()
    written = json.loads(Path(saved["path"]).read_text())
    expected = old_review(transformed, tmp_path, edits, "shaky")
    assert {**written, "reviewed_at": None} == {**expected, "reviewed_at": None}
    assert triples(written["blocks"]) == blocks


def test_difference_an_edit_anchored_where_a_new_block_lies_over_a_removed_one_reaches_the_new_block(client, attached, transformed, tmp_path):
    edits = [{"op": "accept"}, {"op": "drop", "frame": 301}, {"op": "new", "frame_start": 399, "frame_end": 1299},
             {"op": "move", "frame": 449, "edge": "start", "at": 399}]
    saved = client.put(f"/api/sources/{attached[0]}/sessions/{S1}/review", json={"edits": edits}).json()["review"]
    assert triples(saved["blocks"]) == [(301, 1500, "dropped"), (449, 1299, "edited"), (2101, 3300, "confirmed")]  # the new block moves
    old = old_review(transformed, tmp_path, edits, "")
    assert triples(old["blocks"]) == [(399, 1299, "edited"), (449, 1500, "edited"), (2101, 3300, "confirmed")]  # the removed block, first in the list, moves


def test_difference_a_removed_block_does_not_come_back_over_a_kept_one(client, attached, transformed, tmp_path):
    edits = [{"op": "accept"}, {"op": "drop", "frame": 301}, {"op": "new", "frame_start": 399, "frame_end": 1299}, {"op": "drop", "frame": 301}]
    saved = client.put(f"/api/sources/{attached[0]}/sessions/{S1}/review", json={"edits": edits}).json()["review"]
    assert triples(saved["blocks"]) == [(301, 1500, "dropped"), (399, 1299, "edited"), (2101, 3300, "confirmed")]  # the drop is refused
    old = old_review(transformed, tmp_path, edits, "")
    assert triples(old["blocks"]) == [(301, 1500, "edited"), (399, 1299, "edited"), (2101, 3300, "confirmed")]  # two kept blocks overlap, the processor fails both


def test_difference_an_epoch_under_another_condition_has_no_block_and_no_cuts(client, attached, transformed):
    header = client.get(f"/api/sources/{attached[0]}/sessions/{S6}").json()  # S6's arena is under the rot45 condition
    old = old_tool.load_session(transformed, S6)
    assert [b["epoch"] for b in header["blocks"]] == ["track"]  # the processor builds no arena block for it
    assert [b["epoch"] for b in old["blocks"]] == ["arena", "track"]  # a confirmed one makes the processor raise
    assert all(first >= 1801 for first, _ in header["cuts"]["margins"]) and old["cuts"]["margins"][0][0] < 1801


@pytest.mark.parametrize("session_id, differing", [(S1, ()), (S6, ("cuts", "blocks"))])
def test_a_session_equals_what_the_old_tool_loads(client, attached, transformed, session_id, differing):
    old = old_tool.load_session(transformed, session_id)
    header = client.get(f"/api/sources/{attached[0]}/sessions/{session_id}").json()
    for key in (key for key in SESSION_KEYS if key not in differing):
        assert header[key] == json.loads(json.dumps(old[key])), key
    assert header["led_offset"] == pytest.approx(old["led_offset"])
    table = pa.ipc.open_stream(client.get(f"/api/sources/{attached[0]}/sessions/{session_id}/arrays").content).read_all()
    for key in ARRAY_COLUMNS:
        expected = np.array([np.nan if value is None else value for value in old[key]])
        np.testing.assert_allclose(table[key].to_numpy(), expected, atol=ROUNDING, equal_nan=True, err_msg=key)
    assert table["n_lights"].to_pylist() == old["n_lights"]


def test_the_format_contract_names_the_review_keys_and_edit_ops_of_the_old_tool(client, transformed):
    contract = client.get("/api/format").json()
    session = old_tool.load_session(transformed, S1)
    assert set(contract["review"]["keys"]) == set(old_tool.review_of(session, [{"op": "accept"}], "", STAMP))
    assert set(EDIT_FIELDS) == set(old_tool.BLOCK_OPS) | {"flag"}
