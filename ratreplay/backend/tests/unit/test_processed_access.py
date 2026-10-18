"""
ProcessedAccess over small hand made blocks: a build is replaced whole and idempotent, a session never touches another, a failed write leaves the previous build, and health names what is wrong.
"""

import json

import numpy as np
import pyarrow as pa
import pytest
from fixtures import S1, S6

from ratreplay_api import contract
from ratreplay_api.access.processed import BLOCK_SCHEMA, BLOCKS_CSV_SCHEMA, ProcessedAccess
from ratreplay_api.utilities import tables
from ratreplay_api.utilities.errors import Invalid, NotFound

FRAMES = 300
FLOATS = ("t", "x", "y", "heading", "speed", "turn_rate")
BOOLS = ("heading_filled", "heading_held", "filled_front", "filled_back", "clean")
INTS = {"n_lights": np.int8, "trip": np.int32, "run": np.int32, "path_id": np.int16}
CELLS = {pa.string(): "text", pa.int64(): 1, pa.float64(): 0.5}
METADATA = {"rules": {"MIN_BLOCK_S": 10}, "settings": {"window_s": 40.0}, "review_stamp": "2026-10-17T10:00:00+00:00",
            "code_version": "abc1234", "built_at": "2026-10-17T10:05:00+00:00", "windows": {"S1_track_100": {"count": 3, "verdict": "ok"}}}
WINDOWS = {"settings": {"window_s": 40.0}, "totals": {"blocks": 5}, "selected_at": "2026-10-17T11:00:00+00:00", "selected_by": "kyle"}


def make_block(sid, first):
    """
    A hand made block of the session starting at the lab frame: its index row and its arrays in the block schema's dtypes.
    """
    rng = np.random.default_rng(first)
    arrays = {"frame": np.arange(first, first + FRAMES, dtype=np.int32), "phase": np.array(["outbound", "dwell"] * (FRAMES // 2))}
    arrays.update({name: rng.random(FRAMES) for name in FLOATS})
    arrays.update({name: rng.random(FRAMES) > 0.5 for name in BOOLS})
    arrays.update({name: rng.integers(0, 3, FRAMES).astype(kind) for name, kind in INTS.items()})
    row = {field.name: CELLS[field.type] for field in BLOCKS_CSV_SCHEMA}
    row.update(block_id=f"{sid}_track_{first}", session_id=sid, subject_id="0123", date="2015-01-01", kind="track",
               frame_start=first, frame_end=first + FRAMES - 1, n_frames=FRAMES)
    return {"row": row, "arrays": arrays}


def make_session(sid, firsts):
    """
    The blocks of a session, one per first frame.
    """
    return [make_block(sid, first) for first in firsts]


def snapshot(root):
    """
    Every file under the folder with its bytes.
    """
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def review_of(sid, status="confirmed"):
    """
    A review of the session with one block of the given status.
    """
    block = {"block_id": f"{sid}_track_100", "epoch": "track", "environment": "triple_t", "frame_start": 100, "frame_end": 399,
             "status": status, "note": ""}
    return {"session_id": sid, "reviewed_by": "kyle", "reviewed_at": "2026-10-17T09:00:00+00:00", "converter_manifest_timestamp": "t",
            "rules": {}, "blocks": [block], "cuts": [], "flagged_runs": [], "notes": "", "edits": []}


@pytest.fixture
def access(tmp_path):
    """
    A ProcessedAccess over a folder that does not exist yet.
    """
    return ProcessedAccess(tmp_path / "processed")


@pytest.fixture
def built(access):
    """
    The access after the build of two sessions, three blocks and two.
    """
    access.write_blocks(S1, make_session(S1, (100, 1000, 2000)), METADATA)
    access.write_blocks(S6, make_session(S6, (100, 1000)), METADATA)
    return access


def test_writing_a_session_twice_gives_identical_files(access):
    blocks = make_session(S1, (100, 1000, 2000))
    assert access.write_blocks(S1, blocks, METADATA) == {"blocks": 3, "replaced": False}
    first = snapshot(access.root)
    assert access.write_blocks(S1, blocks, METADATA) == {"blocks": 3, "replaced": True}
    assert snapshot(access.root) == first
    assert sorted(first) == sorted(["blocks.csv", f"metadata/{S1}.json", *(f"blocks/{b['row']['block_id']}.parquet" for b in blocks)])


def test_a_second_session_leaves_the_first_untouched_whatever_the_order(access, tmp_path):
    access.write_blocks(S1, make_session(S1, (100, 1000, 2000)), METADATA)
    files, rows = snapshot(access.root), access.blocks()
    access.write_blocks(S6, make_session(S6, (100, 1000)), METADATA)
    after = snapshot(access.root)
    assert all(after[name] == data for name, data in files.items() if name != "blocks.csv")
    assert access.blocks()[:3] == rows and [row["session_id"] for row in access.blocks()] == [S1] * 3 + [S6] * 2
    reverse = ProcessedAccess(tmp_path / "reverse")
    reverse.write_blocks(S6, make_session(S6, (100, 1000)), METADATA)
    reverse.write_blocks(S1, make_session(S1, (100, 1000, 2000)), METADATA)
    assert snapshot(reverse.root) == after


def test_rewriting_a_session_removes_its_earlier_blocks(built):
    before = snapshot(built.root)
    built.write_blocks(S1, make_session(S1, (100, 5000)), METADATA)
    after = snapshot(built.root)
    assert [row["block_id"] for row in built.blocks() if row["session_id"] == S1] == [f"{S1}_track_100", f"{S1}_track_5000"]
    assert f"blocks/{S1}_track_1000.parquet" not in after and f"blocks/{S1}_track_5000.parquet" in after
    assert all(after[name] == data for name, data in before.items() if S6 in name)


def test_an_interrupted_write_leaves_the_previous_build_and_no_temporary_file(built, monkeypatch):
    before, real, calls = snapshot(built.root), tables.write_parquet, []

    def second_fails(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(tables, "write_parquet", second_fails)
    with pytest.raises(OSError, match="disk full"):
        built.write_blocks(S1, make_session(S1, (300, 400, 500)), METADATA)
    assert len(calls) == 2 and snapshot(built.root) == before


def test_a_block_comes_back_with_its_row_and_arrays_and_an_unknown_one_is_not_found(access):
    block = make_block(S1, 100)
    access.write_blocks(S1, [block], METADATA)
    found = access.block(block["row"]["block_id"])
    assert found["row"] == block["row"]
    assert set(found["arrays"]) == set(BLOCK_SCHEMA.names)
    assert all(list(found["arrays"][name]) == list(block["arrays"][name]) for name in BLOCK_SCHEMA.names)
    with pytest.raises(NotFound, match="no block nope"):
        access.block("nope")


def test_a_build_that_breaks_the_format_is_refused_and_writes_nothing(access):
    good = make_block(S1, 100)
    other = make_block(S6, 100)
    escaping = make_block(S1, 200)
    escaping["row"]["block_id"] = "../outside"
    for blocks, metadata, message in [([other], METADATA, f"is of session {S6}, not {S1}"), ([escaping], METADATA, "not a safe file name"),
                                      ([good], {"rules": {}}, "metadata lacks settings"), ([{"row": {"block_id": "a"}, "arrays": {}}], METADATA, "block row lacks session_id")]:
        with pytest.raises(Invalid, match=message):
            access.write_blocks(S1, blocks, metadata)
    assert not access.root.exists()


def test_the_built_sessions_are_listed_by_their_metadata_whether_or_not_they_hold_blocks(built):
    assert built.built() == [S1, S6]
    built.write_blocks(S1, [], METADATA)
    assert built.built() == [S1, S6] and [row["session_id"] for row in built.blocks()] == [S6, S6]
    assert ProcessedAccess(built.root / "nowhere").built() == []


def test_a_review_round_trips_and_the_reviewed_sessions_are_listed(access):
    assert access.review(S1) is None and access.reviews() == []
    assert access.write_review(S6, review_of(S6)) == {"replaced": False}
    assert access.write_review(S1, review_of(S1)) == {"replaced": False}
    assert access.write_review(S1, review_of(S1, "edited")) == {"replaced": True}
    assert access.review(S1) == review_of(S1, "edited")
    assert access.reviews() == [S1, S6]


def test_a_review_with_a_bad_status_or_a_missing_key_is_refused_by_name(access):
    with pytest.raises(Invalid, match=f"block {S1}_track_100 has status maybe"):
        access.write_review(S1, review_of(S1, "maybe"))
    with pytest.raises(Invalid, match="review lacks notes"):
        access.write_review(S1, {key: value for key, value in review_of(S1).items() if key != "notes"})
    with pytest.raises(Invalid, match=f"review is of session {S6}, not {S1}"):
        access.write_review(S1, review_of(S6))
    assert not access.root.exists()


def test_window_settings_round_trip_with_the_replaced_flag(access):
    assert access.window_settings() is None
    assert access.write_window_settings(WINDOWS) == {"replaced": False, "file": "windows.json"}
    assert access.write_window_settings({**WINDOWS, "selected_by": "yuki"}) == {"replaced": True, "file": "windows.json"}
    assert access.window_settings()["selected_by"] == "yuki"
    with pytest.raises(Invalid, match="window settings lacks totals"):
        access.write_window_settings({key: value for key, value in WINDOWS.items() if key != "totals"})


def test_health_is_clean_and_zero_on_an_empty_or_absent_folder(tmp_path):
    empty = {"problems": [], "counts": {"reviews": 0, "blocks": 0, "sessions": 0}, "manifest": None}
    (tmp_path / "empty").mkdir()
    for name, exists in (("empty", True), ("absent", False)):
        health = ProcessedAccess(tmp_path / name).health()
        assert {key: health[key] for key in empty} == empty and health["exists"] is exists and health["root"] == str(tmp_path / name)


def test_health_counts_a_build(built):
    built.write_review(S1, review_of(S1))
    health = built.health()
    assert health["problems"] == [] and health["counts"] == {"reviews": 1, "blocks": 5, "sessions": 2}
    assert health["manifest"]["modified"]


def test_health_names_a_missing_block_file_a_bad_json_file_and_a_csv_lacking_a_column(built):
    (built.root / "blocks" / f"{S1}_track_100.parquet").unlink()
    (built.root / "blocks" / f"{S6}_track_100.parquet").unlink()
    (built.root / "review").mkdir()
    (built.root / "review" / f"{S1}.json").write_text("{not json")
    health = built.health()
    assert health["problems"] == [f"2 block files missing, the first is {S1}_track_100", f"review/{S1}.json is not valid json"]
    assert health["counts"] == {} and health["manifest"] is None
    (built.root / "review" / f"{S1}.json").unlink()
    (built.root / "blocks" / "orphan.parquet").write_bytes(b"")
    (built.root / "blocks" / "half.parquet.tmp").write_bytes(b"")
    assert built.health()["problems"][1:] == ["1 block files with no row in blocks.csv, the first is orphan",
                                               "1 temporary files left by an interrupted write, the first is blocks/half.parquet.tmp"]
    index = built.root / "blocks.csv"
    tables.write_csv(built.blocks(), index, pa.schema([field for field in BLOCKS_CSV_SCHEMA if field.name != "kind"]))
    assert built.health()["problems"][0] == "blocks.csv lacks kind"


def test_the_schema_is_the_contracts_processed_part_in_the_new_layout():
    # Goes with contract.py when task L deletes it.
    files = {file["path"]: file for file in ProcessedAccess("unused").schema()["files"]}
    old = contract.build()
    assert list(files) == ["blocks.csv", "blocks/<block_id>.parquet", "review/<session_id>.json", "metadata/<session_id>.json", "windows.json"]
    assert files["blocks/<block_id>.parquet"]["columns"] == old["processed"]["files"][1]["columns"]
    assert [column for column in files["blocks.csv"]["columns"] if column["name"] != "kind"] == old["processed"]["files"][0]["columns"]
    assert {key: value for key, value in files["review/<session_id>.json"].items() if key != "optional"} == old["review"]
    json.dumps(files)
