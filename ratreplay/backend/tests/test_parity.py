"""
Parity with the old tool (src/ratreplay/data.py) on the format contract: the review keys and the edit ops. This file imports the old tool on purpose, it is the parity oracle and nothing else in the backend imports ratreplay, and it goes when the old tool does. The session and review routes were compared with the old tool here until ReviewManager replaced them, the engines carry that parity now (test_trajectory_*, test_apply_parity).
"""

from fixtures import S1, STAMP
from ratreplay import data as old_tool
from ratreplay_api.contract import EDIT_FIELDS


def test_the_format_contract_names_the_review_keys_and_edit_ops_of_the_old_tool(client, transformed):
    contract = client.get("/api/format").json()
    session = old_tool.load_session(transformed, S1)
    assert set(contract["review"]["keys"]) == set(old_tool.review_of(session, [{"op": "accept"}], "", STAMP))
    assert set(EDIT_FIELDS) == set(old_tool.BLOCK_OPS) | {"flag"}
