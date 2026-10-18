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
from ratreplay_api.managers.review import OTHER_RULES, SAVED_DIFFER, STILL_AUTO, ReviewManager
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
HEADER_KEYS = {"session_id", "subject_id", "group", "protocol", "rate_hz", "max_gap", "date", "n_frames", "in_dataset", "reason", "epochs", "runs",
               "selected_epochs", "n_initial_blocks", "frame", "heading_spans", "cut_points", "margins", "stretches", "occupancy", "stops",
               "warnings", "review", "blocks", "refusals", "cuts", "flagged_runs"}
ARRAY_KEYS = ["t", "x", "y", "heading", "speed", "turn_rate", "motion", "n_lights"]


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


def test_the_index_lists_six_sessions_the_dataset_first_with_the_reason_for_the_others(manager):
    rows = manager.index()
    assert [r["session_id"] for r in rows] == [S1, S6, S2, S3, S4, S5]
    assert [r["in_dataset"] for r in rows] == [True, True, False, False, False, False]
    assert [bool(r["reason"]) for r in rows] == [False, False, True, True, True, True]
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
    assert [(b["status"], b["problems"], set(b["windows"])) for b in header["blocks"]] == [("auto", [], {"count", "verdict"})] * 2
    assert all(b["windows"]["count"] > 0 and set(b["windows"]["verdict"]) == {"ok", "reasons"} for b in header["blocks"])
    assert list(arrays) == ARRAY_KEYS and all(len(values) == 5400 for values in arrays.values()) and arrays["n_lights"].dtype == np.int8
    assert 0 < np.nanmax(np.abs(arrays["x"])) < 3
    json.dumps(header)
    with pytest.raises(NotFound):
        manager.load(S2, SHORT)


def test_a_session_the_rules_leave_out_can_be_viewed_and_previewed_but_not_saved_or_rebuilt(folders, manager, monkeypatch):
    manager.save_blocks(S1, SAVED, "", SHORT)
    monkeypatch.setattr(review_module, "RULES", {**RULES, "protocol": "rotation"})
    header = manager.load(S1, SHORT)
    assert header["in_dataset"] is False and header["reason"] and len(manager.arrays(S1)["t"]) == 5400
    assert manager.preview(S1, ACCEPT, SHORT)["refusals"] == []
    with pytest.raises(Invalid, match=re.escape(f"session {S1} is not in the dataset: {header['reason']}")):
        manager.save_blocks(S1, SAVED, "", SHORT)
    done = manager.rebuild_all(SHORT)
    assert done["totals"]["errors"] == 1 and done["sessions"][S1]["build_error"].startswith("Invalid: ")


def test_a_preview_of_an_illegal_split_returns_the_refusal_and_writes_nothing(folders, manager):
    done = manager.preview(S1, [*ACCEPT, {"op": "split", "frame": 100}], SHORT)
    assert [(r["index"], r["op"]) for r in done["refusals"]] == [(1, "split")] and done["refusals"][0]["reason"]
    assert [b["status"] for b in done["blocks"]] == ["confirmed", "confirmed"] and done["cuts"] == [] and done["flagged_runs"] == []
    assert not folders[1].exists()


def test_save_writes_the_review_and_the_blocks_and_load_gives_them_back(folders, manager):
    saved = manager.save_blocks(S1, SAVED, "shaky", SHORT)
    assert set(saved) == {"review", "replaced", "built", "failed", "build_error"}
    assert (saved["replaced"], saved["built"], saved["failed"], saved["build_error"]) == (False, 2, [], None)
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
    assert done["totals"] == {"sessions": 2, "built": 3, "failed": 0, "errors": 0}
    assert snapshot(folders[1]) == before and len(before) == 8


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
    assert manager.rebuild_all(SHORT)["totals"] == {"sessions": 1, "built": 0, "failed": 0, "errors": 1}
    monkeypatch.setattr(TrajectoryEngine, "blocks", bug)
    with pytest.raises(ValueError, match="bug"):
        manager.rebuild_all(SHORT)
