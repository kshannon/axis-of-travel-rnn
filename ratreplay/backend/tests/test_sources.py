"""
The format contract checked on a folder: what the sources manager reports as a problem.
"""

import pyarrow.csv as pacsv

from ratreplay_api.managers import sources
from ratreplay_api.stores.data_sources import DataSources


def test_the_synthetic_folders_follow_the_format(data_sources):
    assert sources.transformed_problems(data_sources) == []
    assert sources.processed_problems(data_sources) == []


def test_a_missing_table_is_named(data_sources, transformed):
    (transformed / "epochs.csv").unlink()
    assert sources.transformed_problems(data_sources) == ["missing epochs.csv"]


def test_a_missing_column_is_named(data_sources, transformed):
    runs = pacsv.read_csv(transformed / "runs.csv")
    pacsv.write_csv(runs.drop_columns(["clean"]), transformed / "runs.csv")
    assert sources.transformed_problems(data_sources) == ["runs.csv lacks clean"]


def test_a_missing_block_file_is_counted(data_sources, processed):
    next((processed / "track" / "blocks").glob("*.parquet")).unlink()
    assert sources.processed_problems(data_sources)[0].startswith("1 block files missing")


def test_a_folder_is_resolved_as_the_processor_resolves_it_and_a_missing_key_gives_none(tmp_path):
    (tmp_path / "local.yaml").write_text(f"TRANSFORMED_LAB_DATA: {tmp_path}/a/../b/\nPROCESSED_LAB_DATA: ''\n")
    data_sources = DataSources(tmp_path / "local.yaml")
    assert data_sources.root("transformed") == (tmp_path / "b").resolve()
    assert data_sources.root("processed") is None
