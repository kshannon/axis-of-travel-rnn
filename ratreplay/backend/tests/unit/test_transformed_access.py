"""
TransformedAccess over the synthetic transformed folder: its health names what is wrong and a session comes with its frames.
"""

import pyarrow.csv as pacsv
import pytest
from fixtures import EPOCHS, N_FRAMES, RUNS, S1, S2, S6, STAMP

from ratreplay_api.access.transformed import FRAMES, TransformedAccess
from ratreplay_api.utilities.errors import NotFound


def test_health_of_the_synthetic_folder_has_no_problem_and_the_fixtures_counts(transformed):
    health = TransformedAccess(transformed).health()
    assert health["root"] == str(transformed) and health["exists"] and health["problems"] == []
    assert health["counts"] == {"sessions": 6, "epochs": len(EPOCHS["epoch"]), "runs": len(RUNS["run"]), "frames": 2}
    assert health["manifest"]["timestamp"] == STAMP and health["manifest"]["modified"]


def test_a_missing_table_is_named_and_the_counts_are_withheld(transformed):
    (transformed / "epochs.csv").unlink()
    health = TransformedAccess(transformed).health()
    assert health["problems"] == ["missing epochs.csv"]
    assert health["counts"] == {} and health["manifest"] is None


def test_a_missing_required_column_is_named(transformed):
    runs = pacsv.read_csv(transformed / "runs.csv")
    pacsv.write_csv(runs.drop_columns(["clean"]), transformed / "runs.csv")
    assert TransformedAccess(transformed).health()["problems"] == ["runs.csv lacks clean"]


def test_a_root_that_does_not_exist_is_reported(tmp_path):
    health = TransformedAccess(tmp_path / "nope").health()
    assert health == {"root": str(tmp_path / "nope"), "exists": False, "problems": [f"{tmp_path / 'nope'} does not exist"],
                      "counts": {}, "manifest": None}


def test_the_verbs_of_a_root_that_does_not_exist_are_not_found_by_name(tmp_path):
    access = TransformedAccess(tmp_path / "nope")
    for verb, arguments in ((access.sessions, ()), (access.session, (S1,))):
        with pytest.raises(NotFound, match=f"{tmp_path / 'nope'} does not exist"):
            verb(*arguments)


def test_a_session_with_frames_comes_with_its_epochs_runs_and_arrays(transformed):
    found = TransformedAccess(transformed).session(S1)
    assert found["session"]["session_id"] == S1
    assert {e["epoch"] for e in found["epochs"]} == {"arena", "track"} and len(found["runs"]) == 4
    assert set(found["arrays"]) == set(FRAMES) and len(found["arrays"]["front_x"]) == N_FRAMES
    assert found["stamp"] == STAMP


def test_a_session_without_frames_or_without_a_row_is_not_found_by_name(transformed):
    access = TransformedAccess(transformed)
    with pytest.raises(NotFound, match=f"session {S2} has no frames file"):
        access.session(S2)
    with pytest.raises(NotFound, match="no session nope"):
        access.session("nope")


def test_the_annotations_are_empty_when_the_file_is_absent(transformed):
    access = TransformedAccess(transformed)
    found = access.sessions()
    assert set(found) == {"sessions", "epochs", "runs", "annotations", "frames"}
    assert len(found["annotations"]) == 2 and found["frames"] == sorted([S1, S6])
    (transformed / "annotations.csv").unlink()
    assert access.sessions()["annotations"] == [] and access.health()["problems"] == []

