"""
ReviewManager over the real engine and accesses on the synthetic folders, nothing faked but the data: the index, a session loaded and previewed, blocks saved and built, rebuilt, and a block that cannot be built.
"""

import getpass
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pytest
from fixtures import S1, S2, S3, S4, S5, S6, STAMP

import ratreplay_api.managers.review as review_module
from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.processed import METADATA_KEYS, ProcessedAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.trajectory import RULES, SETTINGS, VERSION, TrajectoryEngine
from ratreplay_api.managers.review import EXCLUDED, OTHER_RULES, SAVED_DIFFER, STILL_AUTO, ReviewManager
from ratreplay_api.utilities.errors import Invalid, NotFound

REAL = Path(__file__).resolve().parents[4] / "configs" / "environments"
FROZEN = "2026-10-18T10:00:00+00:00"
COMMIT = "abc1234"

# A window of 5 s so the 10 to 30 s blocks of the fixtures yield windows, the defaults of 40 s yield none.
SHORT = {**SETTINGS, "window_s": 5.0}

# S1 has an arena block over frames 301 to 1500 and a track block over 2101 to 3300. The edits confirm the arena block, split
# the track block at 2701 into two pieces of 10 s and drop the second. S6 has one track block, accepted whole.
SAVED = [{"op": "confirm", "frame": 1000}, {"op": "split", "frame": 2701}, {"op": "drop", "frame": 2701}]
SAVED_BLOCKS = [(f"{S1}_arena_01", "confirmed"), (f"{S1}_track_01", "edited"), (f"{S1}_track_02", "dropped")]
ACCEPT = [{"op": "accept"}]
HEADER_KEYS = {"session_id", "subject_id", "group", "protocol", "rate_hz", "max_gap", "date", "n_frames", "in_dataset", "reason", "annotated_exclude", "excluded",
               "epochs", "runs",
               "selected_epochs", "n_initial_blocks", "environments", "rules", "frame", "heading_spans", "cut_points", "margins", "stretches", "occupancy", "stops",
               "warnings", "review", "blocks", "refusals", "cuts", "flagged_runs"}
ARRAY_KEYS = ["t", "x", "y", "x_smooth", "y_smooth", "heading", "speed", "turn_rate", "motion", "n_lights"]


class MissingPosition(TransformedAccess):
    """
    The transformed folder with the position of three frames of S1's track block gone.
    """

    def session(self, sid):
        """
        The session with writable arrays, NaN in the position at lab frames 2500 to 2502.
        """
        found = super().session(sid)
        found["arrays"] = {name: values.copy() for name, values in found["arrays"].items()}
        found["arrays"]["mashup_x"][2499:2502] = np.nan
        return found


@pytest.fixture
def folders(tmp_path, transformed):
    """
    The transformed folder, a processed folder not made yet and a copy of the environment yaml files.
    """
    shutil.copytree(REAL, tmp_path / "environments")
    return transformed, tmp_path / "processed", tmp_path / "environments"


def manager_on(folders, transformed_access=TransformedAccess):
    """
    A ReviewManager on the folders, handed a fixed code version.
    """
    transformed, processed, environments = folders
    return ReviewManager(TrajectoryEngine(), transformed_access(transformed), ProcessedAccess(processed), EnvironmentAccess(environments), COMMIT)


@pytest.fixture
def manager(folders):
    """
    A ReviewManager over the synthetic folders.
    """
    return manager_on(folders)


def snapshot(root):
    """
    Every file under the root by relative path with its bytes.
    """
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_the_index_lists_six_sessions_the_dataset_first_with_the_reason_for_the_others_and_the_annotation_as_a_note(manager):
    rows = manager.index()
    assert [r["session_id"] for r in rows] == [S1, S6, S2, S3, S4, S5]
    assert [r["in_dataset"] for r in rows] == [True, True, False, False, False, False]
    assert [r["reason"] for r in rows] == [None, None, "no frames", "no frames", "no frames", "no arena or track epoch under condition baseline"]
    assert [(r["annotated_exclude"], r["excluded"]) for r in rows] == [(False, False)] * 2 + [(False, False), (True, False)] + [(False, False)] * 2
    first = rows[0]
    assert first["date"] == "2015-01-01" and (first["n_runs"], first["n_clean_runs"], first["built"], first["reviewed"]) == (4, 3, 0, False)
    assert [e["epoch"] for e in first["epochs"]] == ["arena", "track"] and set(first["epochs"][0]) == set(review_module.EPOCH_KEYS)
    assert first["confirmed_s"] == {"arena": 0, "track": 0} and first["notes"] == "" and first["reviewed_at"] is None
    json.dumps(rows)


def test_load_gives_the_header_with_the_initial_blocks_and_their_window_counts_and_arrays_gives_metres(manager):
    header, arrays = manager.load(S1, SHORT), manager.arrays(S1)
    assert set(header) == HEADER_KEYS and header["date"] == "2015-01-01" and header["review"] is None and header["n_initial_blocks"] == 2
    assert header["in_dataset"] is True and header["reason"] is None and header["selected_epochs"] == ["arena", "track"]
    assert [r["run"] for r in header["runs"]] == [1, 2, 3, 4] and len(header["epochs"]) == 2
    assert set(header["environments"]) == {e["environment"] for e in header["epochs"]} and all(g["room"] and "walls" in g for g in header["environments"].values())
    assert [(b["status"], b["problems"], set(b["windows"])) for b in header["blocks"]] == [("auto", [], {"count", "verdict"})] * 2
    assert all(b["windows"]["count"] > 0 and set(b["windows"]["verdict"]) == {"ok", "reasons"} for b in header["blocks"])
    assert list(arrays) == ARRAY_KEYS and all(len(values) == 5400 for values in arrays.values()) and arrays["n_lights"].dtype == np.int8
    assert 0 < np.nanmax(np.abs(arrays["x"])) < 3
    json.dumps(header)
    with pytest.raises(NotFound):
        manager.load(S2, SHORT)


def test_a_session_the_funnel_leaves_out_is_refused_a_save_and_its_review_is_skipped_by_a_rebuild(folders, manager, monkeypatch):
    manager.save_blocks(S1, SAVED, "", SHORT)
    monkeypatch.setattr(review_module, "RULES", {**RULES, "condition": "rot45"})
    reason = "no arena or track epoch under condition rot45"
    row = next(r for r in manager.index() if r["session_id"] == S1)
    assert (row["in_dataset"], row["reason"], row["excluded"]) == (False, reason, False)
    with pytest.raises(Invalid, match=re.escape(f"session {S1} is not in the dataset: {reason}")):
        manager.save_blocks(S1, SAVED, "", SHORT)
    done = manager.rebuild_all(SHORT)
    assert done["sessions"] == {} and done["skipped"] == {S1: reason} and done["excluded"] == {}
    assert done["totals"] == {"sessions": 0, "built": 0, "failed": 0, "errors": 0, "skipped": 1, "excluded": 0}


def test_a_preview_of_an_illegal_split_returns_the_refusal_and_writes_nothing(folders, manager):
    done = manager.preview(S1, [*ACCEPT, {"op": "split", "frame": 100}], SHORT)
    assert [(r["index"], r["op"]) for r in done["refusals"]] == [(1, "split")] and done["refusals"][0]["reason"]
    assert [b["status"] for b in done["blocks"]] == ["confirmed", "confirmed"] and done["cuts"] == [] and done["flagged_runs"] == []
    assert not folders[1].exists()


def test_save_writes_the_review_and_the_blocks_and_load_gives_them_back(folders, manager):
    saved = manager.save_blocks(S1, SAVED, "shaky", SHORT)
    assert set(saved) == {"review", "replaced", "file", "built", "failed", "build_error"}
    assert (saved["replaced"], saved["file"], saved["built"], saved["failed"], saved["build_error"]) == (False, f"review/{S1}.json", 2, [], None)
    review, access = saved["review"], ProcessedAccess(folders[1])
    assert review["reviewed_by"] == getpass.getuser() and review["converter_manifest_timestamp"] == STAMP and review["notes"] == "shaky"
    assert [(b["block_id"], b["status"]) for b in review["blocks"]] == SAVED_BLOCKS and review["edits"] == SAVED
    assert access.review(S1) == json.loads(json.dumps(review)) and [r["block_id"] for r in access.blocks()] == [b for b, _ in SAVED_BLOCKS[:2]]
    metadata = access.metadata(S1)
    assert set(metadata) >= set(METADATA_KEYS) and metadata["settings"] == SHORT and metadata["code_version"] == f"trajectory {VERSION} {COMMIT}"
    assert metadata["review_stamp"] == {"reviewed_at": review["reviewed_at"], "converter_manifest_timestamp": STAMP}
    assert list(metadata["windows"]) == [f"{S1}_arena_01", f"{S1}_track_01"] and metadata["failed"] == []
    assert all(set(w) == {"count", "verdict"} for w in metadata["windows"].values())
    header = manager.load(S1, SHORT)
    assert header["review"] == access.review(S1) and [(b["block_id"], b["status"]) for b in header["blocks"]] == SAVED_BLOCKS
    assert [b["windows"] is None for b in header["blocks"]] == [False, False, True] and header["warnings"] == metadata["warnings"]
    row = next(r for r in manager.index() if r["session_id"] == S1)
    assert (row["reviewed"], row["n_confirmed"], row["built"], row["notes"]) == (True, 2, 2, "shaky")
    assert row["confirmed_s"] == pytest.approx({"arena": 20.0, "track": 10.0}) and manager.save_blocks(S1, SAVED, "", SHORT)["replaced"] is True


def test_a_refused_edit_or_a_block_still_auto_refuses_the_whole_save_and_writes_nothing(folders, manager):
    with pytest.raises(Invalid, match=r"^edit 2 \(split at frame 100\): ."):
        manager.save_blocks(S1, [*ACCEPT, {"op": "split", "frame": 100}], "", SHORT)
    with pytest.raises(Invalid, match=STILL_AUTO):
        manager.save_blocks(S1, [{"op": "confirm", "frame": 1000}], "", SHORT)
    assert not folders[1].exists()


def test_rebuild_all_rebuilds_every_reviewed_session_with_the_same_bytes(folders, manager, monkeypatch):
    monkeypatch.setattr(review_module.clock, "iso_now", lambda: FROZEN)
    manager.save_blocks(S1, SAVED, "", SHORT)
    manager.save_blocks(S6, ACCEPT, "", SHORT)
    before = snapshot(folders[1])
    done = manager.rebuild_all(SHORT)
    assert done["sessions"] == {S1: {"built": 2, "failed": [], "build_error": None}, S6: {"built": 1, "failed": [], "build_error": None}}
    assert done["skipped"] == {} and done["excluded"] == {}
    assert done["totals"] == {"sessions": 2, "built": 3, "failed": 0, "errors": 0, "skipped": 0, "excluded": 0}
    assert snapshot(folders[1]) == before and len(before) == 8


def test_rebuild_all_skips_a_review_whose_session_has_no_frames_and_reports_one_the_folder_lacks_as_build_error(folders, manager):
    manager.save_blocks(S1, SAVED, "", SHORT)
    access, ghost = ProcessedAccess(folders[1]), "NS14_rec9_20150109_001"
    for sid in (S2, ghost):
        access.write_review(sid, {**access.review(S1), "session_id": sid})
    done = manager.rebuild_all(SHORT)
    assert done["skipped"] == {S2: "no frames"} and set(done["sessions"]) == {S1, ghost}
    assert done["sessions"][S1] == {"built": 2, "failed": [], "build_error": None}
    assert done["sessions"][ghost] == {"built": 0, "failed": [], "build_error": f"NotFound: no session {ghost}"}
    assert done["excluded"] == {} and done["totals"] == {"sessions": 2, "built": 2, "failed": 0, "errors": 1, "skipped": 1, "excluded": 0}
    assert S2 not in access.built()


def test_exclude_writes_a_review_of_the_initial_blocks_without_reviewing_the_session_and_builds_it_empty_at_once(folders, manager, monkeypatch):
    monkeypatch.setattr(review_module.clock, "iso_now", lambda: FROZEN)
    done = manager.exclude(S1, True, "camera moved", SHORT)
    review, access = done["review"], ProcessedAccess(folders[1])
    assert set(done) == {"review", "replaced", "file", "deleted", "built", "failed", "build_error"}
    assert (done["replaced"], done["file"], done["deleted"], done["built"], done["failed"], done["build_error"]) == (False, f"review/{S1}.json", False, 0, [], None)
    assert access.review(S1) == json.loads(json.dumps(review))
    assert (review["excluded"], review["notes"], review["excluded_at"], review["excluded_by"]) == (True, "camera moved", FROZEN, getpass.getuser())
    assert (review["reviewed_by"], review["reviewed_at"]) == (None, None) and review["converter_manifest_timestamp"] == STAMP
    assert (review["edits"], review["cuts"], review["flagged_runs"]) == ([], [], [])
    assert [(b["block_id"], b["status"]) for b in review["blocks"]] == [(f"{S1}_arena_01", "auto"), (f"{S1}_track_01", "auto")]
    metadata = access.metadata(S1)
    assert metadata["excluded"] is True and metadata["windows"] == {} and metadata["failed"] == [] and set(metadata) >= set(METADATA_KEYS)
    assert metadata["review_stamp"] == {"reviewed_at": None, "converter_manifest_timestamp": STAMP} and access.blocks() == [] and access.built() == [S1]
    row = next(r for r in manager.index() if r["session_id"] == S1)
    assert (row["excluded"], row["reviewed"], row["n_confirmed"], row["notes"], row["built"]) == (True, True, 0, "camera moved", 0)
    assert (row["reviewed_by"], row["reviewed_at"], row["excluded_by"], row["excluded_at"]) == (None, None, getpass.getuser(), FROZEN)
    header = manager.load(S1, SHORT)
    assert header["excluded"] is True and header["in_dataset"] is True and header["review"] == access.review(S1)
    with pytest.raises(Invalid, match=re.escape(EXCLUDED.format(sid=S1))):
        manager.save_blocks(S1, SAVED, "", SHORT)
    assert access.review(S1) == json.loads(json.dumps(review))
    with pytest.raises(NotFound):
        manager.exclude(S2, True, "no frames to cut", SHORT)


def test_including_a_session_that_was_only_excluded_removes_its_review_and_build_and_leaves_it_as_before(folders, manager):
    access = ProcessedAccess(folders[1])
    manager.save_blocks(S6, ACCEPT, "", SHORT)
    row_of = lambda sid: next(r for r in manager.index() if r["session_id"] == sid)
    before = (row_of(S1), access.built(), access.review(S1), access.blocks(), snapshot(folders[1]))
    manager.exclude(S1, True, "camera moved", SHORT)
    assert access.built() == [S1, S6] and row_of(S1)["excluded"] is True
    back = manager.exclude(S1, False, "after all", SHORT)
    assert (back["review"], back["replaced"], back["deleted"], back["file"], back["built"], back["build_error"]) == (None, False, True, f"review/{S1}.json", 0, None)
    assert (row_of(S1), access.built(), access.review(S1), access.blocks()) == before[:4]
    assert {name: data for name, data in snapshot(folders[1]).items() if "metadata" in name or "review" in name} == \
        {name: data for name, data in before[4].items() if "metadata" in name or "review" in name}
    assert manager.load(S1, SHORT)["excluded"] is False and manager.save_blocks(S1, SAVED, "", SHORT)["built"] == 2


def test_excluding_a_reviewed_session_keeps_its_review_stamp_and_clears_its_blocks_and_include_keeps_the_review(folders, manager, monkeypatch):
    monkeypatch.setattr(review_module.clock, "iso_now", lambda: FROZEN)
    manager.save_blocks(S1, SAVED, "shaky", SHORT)
    manager.save_blocks(S6, ACCEPT, "", SHORT)
    access = ProcessedAccess(folders[1])
    saved, built = access.review(S1), {name: data for name, data in snapshot(folders[1]).items() if not name.startswith("review")}
    done = manager.exclude(S1, True, "bad light", SHORT)
    assert done["replaced"] is True and done["deleted"] is False and done["review"]["notes"] == "shaky\nbad light" and (done["built"], done["build_error"]) == (0, None)
    assert {**done["review"], "excluded": False, "notes": "shaky", "excluded_by": None, "excluded_at": None} == saved
    assert (done["review"]["excluded_by"], done["review"]["excluded_at"]) == (getpass.getuser(), FROZEN)
    assert [r["session_id"] for r in access.blocks()] == [S6] and not list((folders[1] / "blocks").glob(f"{S1}_*"))
    assert access.metadata(S1)["excluded"] is True and access.metadata(S1)["review_stamp"] == {"reviewed_at": saved["reviewed_at"], "converter_manifest_timestamp": STAMP}
    assert manager.rebuild_all(SHORT)["excluded"] == {S1: "shaky\nbad light"}
    back = manager.exclude(S1, False, "", SHORT)
    assert (back["replaced"], back["deleted"], back["built"]) == (True, False, 0) and back["review"]["excluded"] is False
    assert (back["review"]["reviewed_by"], back["review"]["reviewed_at"]) == (saved["reviewed_by"], saved["reviewed_at"])
    assert (back["review"]["excluded_by"], back["review"]["excluded_at"]) == (getpass.getuser(), FROZEN) and [r["session_id"] for r in access.blocks()] == [S6]
    again = manager.rebuild_all(SHORT)
    assert again["totals"] == {"sessions": 2, "built": 3, "failed": 0, "errors": 0, "skipped": 0, "excluded": 0} and again["excluded"] == {}
    assert {name: data for name, data in snapshot(folders[1]).items() if not name.startswith("review")} == built


def test_an_excluded_session_the_funnel_also_leaves_out_is_still_written_empty(folders, manager, monkeypatch):
    access = ProcessedAccess(folders[1])
    manager.save_blocks(S1, SAVED, "", SHORT)
    access.write_review(S1, {**access.review(S1), "excluded": True})
    assert len(access.blocks()) == 2
    monkeypatch.setattr(review_module, "RULES", {**RULES, "condition": "rot45"})
    done = manager.rebuild_all(SHORT)
    assert done["excluded"] == {S1: ""} and done["skipped"] == {} and done["sessions"] == {S1: {"built": 0, "failed": [], "build_error": None}}
    assert access.blocks() == [] and access.metadata(S1)["excluded"] is True and access.metadata(S1)["windows"] == {}


def test_a_session_the_funnel_leaves_out_but_that_has_frames_can_be_excluded(folders, manager, monkeypatch):
    monkeypatch.setattr(review_module, "RULES", {**RULES, "condition": "rot45"})
    done = manager.exclude(S1, True, "", SHORT)
    assert done["review"]["blocks"] == [] and done["review"]["excluded"] is True and done["build_error"] is None
    row = next(r for r in manager.index() if r["session_id"] == S1)
    assert (row["in_dataset"], row["excluded"], row["built"]) == (False, True, 0) and ProcessedAccess(folders[1]).metadata(S1)["excluded"] is True


def test_a_review_file_without_the_excluded_keys_reads_as_not_excluded_and_builds(folders, manager):
    manager.save_blocks(S1, SAVED, "", SHORT)
    path = folders[1] / "review" / f"{S1}.json"
    path.write_text(json.dumps({key: value for key, value in json.loads(path.read_text()).items() if not key.startswith("excluded")}))
    assert not [key for key in json.loads(path.read_text()) if key.startswith("excluded")]
    assert manager.load(S1, SHORT)["excluded"] is False and next(r for r in manager.index() if r["session_id"] == S1)["excluded"] is False
    assert manager.rebuild_all(SHORT)["totals"] == {"sessions": 1, "built": 2, "failed": 0, "errors": 0, "skipped": 0, "excluded": 0}


def test_a_block_with_a_missing_position_lands_in_failed_and_is_not_written(folders):
    manager = manager_on(folders, MissingPosition)
    saved = manager.save_blocks(S1, ACCEPT, "", SHORT)
    problem = {"block_id": f"{S1}_track_01", "problems": ["position not finite on 3 frames"]}
    assert (saved["built"], saved["failed"], saved["build_error"]) == (1, [problem], None)
    access = ProcessedAccess(folders[1])
    assert [r["block_id"] for r in access.blocks()] == [f"{S1}_arena_01"] and access.metadata(S1)["failed"] == [problem]
    assert list(access.metadata(S1)["windows"]) == [f"{S1}_arena_01"] and access.review(S1) is not None
    assert [b["problems"] for b in manager.load(S1, SHORT)["blocks"]] == [[], problem["problems"]]


def test_the_header_warns_when_the_review_was_made_under_other_rules_or_its_blocks_are_not_the_ones_today_gives(folders, manager):
    manager.save_blocks(S1, SAVED, "", SHORT)
    access = ProcessedAccess(folders[1])
    base = manager.load(S1, SHORT)["warnings"]
    assert OTHER_RULES not in base and SAVED_DIFFER not in base and base == access.metadata(S1)["warnings"]
    saved = access.review(S1)
    access.write_review(S1, {**saved, "rules": {**RULES, "pause_margin_s": 1.0}})
    assert manager.rebuild_all(SHORT)["totals"]["built"] == 2
    assert access.metadata(S1)["warnings"] == base + [OTHER_RULES] and manager.load(S1, SHORT)["warnings"] == base + [OTHER_RULES]
    moved = [{**b, "frame_start": b["frame_start"] + 1} if b["block_id"].endswith("arena_01") else b for b in saved["blocks"]]
    access.write_review(S1, {**saved, "blocks": moved})
    header = manager.load(S1, SHORT)
    assert header["warnings"] == base + [SAVED_DIFFER] and header["refusals"] == []
    assert [(b["block_id"], b["status"], b["frame_start"]) for b in header["blocks"]][0] == (f"{S1}_arena_01", "confirmed", 301)


def test_only_a_file_or_validation_failure_of_the_build_comes_back_as_build_error(folders, manager, monkeypatch):
    def disk_full(self, sid, blocks, metadata):
        raise OSError("disk full")

    def bug(self, arrays, review, environment, rules):
        raise ValueError("bug")
    monkeypatch.setattr(ProcessedAccess, "write_blocks", disk_full)
    saved = manager.save_blocks(S1, SAVED, "", SHORT)
    assert (saved["built"], saved["failed"], saved["build_error"]) == (0, [], "OSError: disk full")
    access = ProcessedAccess(folders[1])
    assert access.review(S1) is not None and access.blocks() == []
    assert manager.rebuild_all(SHORT)["totals"] == {"sessions": 1, "built": 0, "failed": 0, "errors": 1, "skipped": 0, "excluded": 0}
    monkeypatch.setattr(TrajectoryEngine, "blocks", bug)
    with pytest.raises(ValueError, match="bug"):
        manager.rebuild_all(SHORT)
