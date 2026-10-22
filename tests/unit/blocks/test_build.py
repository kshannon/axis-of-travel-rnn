"""
The build: two fixture sessions with their reviews build into a temporary folder with a stable data id, a changed review changes it, a session without a review is skipped, an excluded one writes no blocks, main reads the reviews from PROCESSED_LAB_DATA/review by default, and exits 1 on an unexpected data id and 2 on an unknown blueprint key.
"""

import json

import pytest
import yaml

import axis_of_travel_rnn.blocks.__main__ as entry
from axis_of_travel_rnn.blocks import RULES, BlockEngine, io
from axis_of_travel_rnn.blocks.blueprint import read_blueprint

from .fixtures import S1, S2, S6, STAMP, loaded

BLUEPRINT = {"name": "fixture_v1", "format_version": 4, "transformed": "TRANSFORMED_LAB_DATA", "sessions": [S1, S2, S6],
             "rules": {}, "settings": {}, "start_offsets": "from_reviews", "expected_data_id": None}


def accepted_review(transformed, sid):
    """
    The review the review tool saves when the person accepts every initial block of the session.
    """
    session = BlockEngine().session(*loaded(transformed, sid), RULES)
    applied = BlockEngine().apply(session["initial_blocks"], [{"op": "accept"}], session)
    return {"session_id": sid, "reviewed_by": "kyle", "reviewed_at": STAMP, "converter_manifest_timestamp": STAMP,
            "rules": session["rules"], "blocks": applied["blocks"], "cuts": [], "flagged_runs": [], "notes": "",
            "edits": [{"op": "accept"}], "excluded": False, "excluded_by": None, "excluded_at": None, "start_offset_m": None}


@pytest.fixture
def reviews(tmp_path, transformed):
    """
    A reviews folder holding the accepted reviews of S1 and S6, none of S2.
    """
    root = tmp_path / "reviews"
    root.mkdir()
    for sid in (S1, S6):
        (root / f"{sid}.json").write_text(json.dumps(accepted_review(transformed, sid)))
    return root


def write_blueprint(tmp_path, reviews, **changes):
    """
    The fixture blueprint written as yaml with the changes and no reviews key when reviews is none, its path.
    """
    path = tmp_path / "fixture_v1.yaml"
    path.write_text(yaml.safe_dump({**BLUEPRINT, **({} if reviews is None else {"reviews": str(reviews)}), **changes}))
    return path


def built(tmp_path, transformed, reviews, folder):
    """
    The manifest of the fixture blueprint built into the folder under tmp_path.
    """
    path = write_blueprint(tmp_path, reviews)
    return entry.build(read_blueprint(path), entry.sha256_of(path), transformed, reviews, tmp_path / folder)


def test_two_builds_give_the_same_data_id_and_a_session_without_a_review_is_skipped(tmp_path, transformed, reviews):
    first, second = (built(tmp_path, transformed, reviews, folder) for folder in ("one", "two"))
    assert first["data_id"] == second["data_id"] and first["blueprint"] == second["blueprint"]
    assert first["skipped"] == {S2: entry.NO_REVIEW} and first["failed"] == {} and first["errors"] == {}
    assert first["counts"] == {"sessions_built": 2, "blocks_written": 3, "failed_blocks": 0, "skipped_sessions": 1,
                               "excluded_sessions": 0, "errors": 0}
    assert first["transformed_stamp"] == STAMP and first["engine_version"] == 2
    assert [row["block_id"] for row in io.blocks(tmp_path / "one")] == [f"{S1}_arena_01", f"{S1}_track_01", f"{S6}_track_01"]
    assert io.metadata(tmp_path / "one", S1)["review_stamp"] == {"reviewed_at": STAMP, "converter_manifest_timestamp": STAMP}


def test_a_changed_review_changes_the_data_id_and_an_excluded_session_writes_no_blocks(tmp_path, transformed, reviews):
    before = built(tmp_path, transformed, reviews, "before")
    review = json.loads((reviews / f"{S1}.json").read_text())
    review["blocks"][1]["status"] = "dropped"
    (reviews / f"{S1}.json").write_text(json.dumps(review))
    excluded = {**json.loads((reviews / f"{S6}.json").read_text()), "excluded": True}
    (reviews / f"{S6}.json").write_text(json.dumps(excluded))
    after = built(tmp_path, transformed, reviews, "after")
    assert after["data_id"] != before["data_id"] and after["excluded"] == [S6]
    assert [row["block_id"] for row in io.blocks(tmp_path / "after")] == [f"{S1}_arena_01"]
    assert io.metadata(tmp_path / "after", S6)["excluded"] is True


def test_main_exits_1_when_the_data_id_is_not_the_expected_one_and_0_when_it_is(tmp_path, transformed, reviews, capsys):
    config = {"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(tmp_path / "processed")}
    path = write_blueprint(tmp_path, reviews, expected_data_id="0" * 64)
    assert entry.main(["--blueprint", str(path)], config=config) == 1
    found = json.loads((tmp_path / "processed" / "fixture_v1" / entry.MANIFEST).read_text())["data_id"]
    with pytest.raises(SystemExit) as stop:
        entry.main(["--blueprint", str(path)], config=config)
    assert stop.value.code == 2 and "--replace" in capsys.readouterr().err
    path = write_blueprint(tmp_path, reviews, expected_data_id=found)
    assert entry.main(["--blueprint", str(path), "--replace"], config=config) == 0


def test_the_reviews_default_to_the_review_folder_beside_the_builds(tmp_path, transformed, reviews):
    config = {"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(tmp_path / "processed")}
    (tmp_path / "processed").mkdir()
    reviews.rename(tmp_path / "processed" / entry.REVIEW_DIR)
    assert entry.main(["--blueprint", str(write_blueprint(tmp_path, None))], config=config) == 0
    assert json.loads((tmp_path / "processed" / "fixture_v1" / entry.MANIFEST).read_text())["counts"]["sessions_built"] == 2


def test_an_unknown_blueprint_key_or_rule_exits_2(tmp_path, transformed, reviews):
    config = {"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(tmp_path / "processed")}
    for changes in ({"window": 40}, {"rules": {"jump_metres": 1.0}}):
        with pytest.raises(SystemExit) as stop:
            entry.main(["--blueprint", str(write_blueprint(tmp_path, reviews, **changes))], config=config)
        assert stop.value.code == 2
    assert not (tmp_path / "processed").exists()
