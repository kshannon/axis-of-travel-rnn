"""
The block files: the engine's blocks fit the block and index schemas, two sessions written read back equal, and a session written again replaces only its own rows and files.
"""

import json

import numpy as np
import pyarrow as pa

from axis_of_travel_rnn.blocks import RULES, BlockEngine, io

from .fixtures import S1, S6, STAMP, loaded

TOLERANCE = 1e-12
META = dict.fromkeys(io.METADATA_KEYS)


def built(transformed, sid, review=None):
    """
    The blocks the engine makes of the session, without their problems.
    """
    found, environment = loaded(transformed, sid)
    return [{"row": b["row"], "arrays": b["arrays"]} for b in BlockEngine().blocks(found, review, environment, RULES)["blocks"]]


def same_block(mine, theirs):
    """
    The rows equal, a none in a text column read back as empty text as the csv reader gives it, and the columns equal one by one, floats to the tolerance with NaN where the other has NaN.
    """
    assert mine["row"] == {key: "" if value is None else value for key, value in theirs["row"].items()} and list(mine["arrays"]) == list(theirs["arrays"]) == io.BLOCK_SCHEMA.names
    for name, values in mine["arrays"].items():
        if values.dtype.kind == "f":
            np.testing.assert_allclose(values, theirs["arrays"][name], rtol=0, atol=TOLERANCE, equal_nan=True, err_msg=name)
        else:
            np.testing.assert_array_equal(values, theirs["arrays"][name], err_msg=name)


def test_the_engines_blocks_hold_the_block_schema_types_and_the_index_columns(transformed):
    for block in built(transformed, S1):
        assert [pa.array(block["arrays"][field.name]).type for field in io.BLOCK_SCHEMA] == [field.type for field in io.BLOCK_SCHEMA]
        assert list(block["row"]) == io.BLOCKS_CSV_SCHEMA.names


def test_two_sessions_written_read_back_equal_and_a_session_written_again_replaces_only_its_own(transformed, tmp_path):
    out = tmp_path / "built"
    made = {sid: built(transformed, sid) for sid in (S1, S6)}
    for sid, blocks in made.items():
        io.write_session(out, sid, blocks, {**META, "excluded": False, "warnings": [sid]})
    assert [row["block_id"] for row in io.blocks(out)] == [f"{S1}_arena_01", f"{S1}_track_01", f"{S6}_track_01"]
    for block in made[S1] + made[S6]:
        same_block(io.block(out, block["row"]["block_id"]), block)
    assert io.metadata(out, S6)["warnings"] == [S6] and io.metadata(out, "nobody") is None
    arena_only = {"session_id": S1, "reviewed_by": "kyle", "flagged_runs": [],
                  "blocks": [{"block_id": f"{S1}_arena_01", "epoch": "arena", "environment": "open_arena", "frame_start": 301,
                              "frame_end": 1500, "status": "confirmed", "note": None}]}
    io.write_session(out, S1, built(transformed, S1, arena_only), META)
    assert [(row["block_id"], row["reviewed_by"]) for row in io.blocks(out)] == [(f"{S1}_arena_01", "kyle"), (f"{S6}_track_01", "")]
    assert sorted(path.name for path in (out / io.BLOCKS_DIR).iterdir()) == [f"{S1}_arena_01.parquet", f"{S6}_track_01.parquet"]
    assert list(out.rglob(f"*{io.TEMP}")) == []
    same_block(io.block(out, f"{S6}_track_01"), made[S6][0])


def test_a_review_gets_the_defaults_an_older_file_lacks_and_the_reviews_are_listed_by_session(tmp_path):
    (tmp_path / f"{S1}.json").write_text(json.dumps({"session_id": S1, "reviewed_at": STAMP, "excluded": True}))
    (tmp_path / f"{S6}.json").write_text(json.dumps({"session_id": S6, "start_offset_m": 0.1}))
    assert io.reviews(tmp_path) == [S1, S6] and io.review(tmp_path, "nobody") is None
    assert io.review(tmp_path, S1) == {**io.REVIEW_DEFAULTS, "session_id": S1, "reviewed_at": STAMP, "excluded": True}
    assert io.review(tmp_path, S6)["start_offset_m"] == 0.1 and io.review(tmp_path, S6)["excluded"] is False


def test_the_transformed_reader_gives_the_stamp_and_refuses_a_session_without_frames(transformed):
    assert io.stamp(transformed) == STAMP and io.sessions(transformed)["frames"] == sorted([S1, S6])
    found = io.session(transformed, S1)
    assert found["stamp"] == STAMP and found["session"]["session_id"] == S1 and len(found["arrays"]["t"]) == 5400
    try:
        io.session(transformed, "nobody")
    except KeyError as error:
        assert "nobody" in str(error)
    else:
        raise AssertionError("a missing session was read")
