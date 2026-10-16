"""
The format contract checked on a folder: what the sources manager reports as a problem.
"""

import pyarrow.csv as pacsv

from ratreplay_api.managers import sources


def test_the_synthetic_folders_follow_the_format(transformed, processed):
    assert sources.transformed_problems(transformed) == []
    assert sources.processed_problems(processed) == []


def test_a_missing_table_is_named(transformed):
    (transformed / "epochs.csv").unlink()
    assert sources.transformed_problems(transformed) == ["missing epochs.csv"]


def test_a_missing_column_is_named(transformed):
    runs = pacsv.read_csv(transformed / "runs.csv")
    pacsv.write_csv(runs.drop_columns(["clean"]), transformed / "runs.csv")
    assert sources.transformed_problems(transformed) == ["runs.csv lacks clean"]


def test_a_missing_block_file_is_counted(processed):
    next((processed / "track" / "blocks").glob("*.parquet")).unlink()
    assert sources.processed_problems(processed)[0].startswith("1 block files missing")
