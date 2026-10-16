"""
The synthetic folders every later backend test builds on: the transformed tables and the blocks the processor builds from them.
"""

from fixtures import S1, S6


def test_transformed_folder_holds_the_tables_and_frames(transformed):
    names = {path.name for path in transformed.iterdir()}
    assert {"sessions.csv", "epochs.csv", "runs.csv", "annotations.csv", "manifest.json", "frames"} <= names
    assert {path.stem for path in (transformed / "frames").iterdir()} == {S1, S6}


def test_processed_folder_holds_track_and_arena_blocks(processed):
    assert (processed / "manifest.json").exists()
    for kind in ("track", "arena"):
        assert list((processed / kind / "blocks").glob("*.parquet"))
