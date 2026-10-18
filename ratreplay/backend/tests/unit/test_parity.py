"""
Parity with the old tool (src/ratreplay/data.py) on the review file: its keys and the edit ops ProcessedAccess declares. This file imports the old tool on purpose, it is a parity oracle (test_apply_parity and test_trajectory_contract are the others) and nothing in ratreplay_api imports ratreplay, and it goes when the old tool does. The session and review routes were compared with the old tool here until ReviewManager replaced them, the engines carry that parity now (test_trajectory_*, test_apply_parity).
"""

from fixtures import S1, STAMP
from ratreplay import data as old_tool
from ratreplay_api.access.processed import EDIT_FIELDS, REVIEW_KEYS


def test_the_processed_access_names_the_review_keys_and_edit_ops_of_the_old_tool(transformed):
    session = old_tool.load_session(transformed, S1)
    # The old tool has no exclusion, the flag and its who and when are the keys the review gained.
    assert set(REVIEW_KEYS) - {"excluded", "excluded_by", "excluded_at"} == set(old_tool.review_of(session, [{"op": "accept"}], "", STAMP))
    assert set(EDIT_FIELDS) == set(old_tool.BLOCK_OPS) | {"flag"}
