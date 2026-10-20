"""
The config utility answers a key's path and names the file when it cannot, the folder time is the newest file's, tables read back what they wrote and the version names the commit.
"""

import os
import subprocess
from datetime import datetime, timezone

import numpy as np
import pyarrow as pa
import pytest
import yaml

from ratreplay_api.utilities import paths, tables, version
from ratreplay_api.utilities.config import Config
from ratreplay_api.utilities.errors import Invalid

NEWEST = 2_000_000_000


def test_config_gives_the_resolved_path_of_a_key_whatever_the_key_is_called(tmp_path):
    (tmp_path / "local.yaml").write_text(yaml.safe_dump({"ANY_NAME": str(tmp_path / "sub" / ".." / "there")}))
    assert Config(tmp_path / "local.yaml").value("ANY_NAME") == tmp_path.resolve() / "there"


@pytest.mark.parametrize("content", ["other: 1\n", "KEY:\n"])
def test_config_refuses_a_missing_or_empty_key_naming_the_key_and_the_file(tmp_path, content):
    (tmp_path / "local.yaml").write_text(content)
    config = Config(tmp_path / "local.yaml")
    with pytest.raises(Invalid, match=f"KEY is not set in {config.path}"):
        config.value("KEY")


def test_config_reload_picks_up_a_change(tmp_path):
    file = tmp_path / "local.yaml"
    file.write_text(f"KEY: {tmp_path / 'first'}\n")
    config = Config(file)
    file.write_text(f"KEY: {tmp_path / 'second'}\n")
    assert config.value("KEY") == tmp_path.resolve() / "first"
    config.reload()
    assert config.value("KEY") == tmp_path.resolve() / "second"


def test_newest_mtime_is_none_for_an_empty_folder_and_the_newest_file_otherwise(tmp_path):
    assert paths.newest_mtime(tmp_path) is None
    (tmp_path / "sub").mkdir()
    for name, seconds in (("older.txt", NEWEST - 100), ("sub/newest.txt", NEWEST)):
        (tmp_path / name).write_text("x")
        os.utime(tmp_path / name, (seconds, seconds))
    assert paths.newest_mtime(tmp_path) == datetime.fromtimestamp(NEWEST, timezone.utc).isoformat(timespec="seconds")


def test_tables_read_back_what_they_wrote_with_their_columns(tmp_path):
    schema = pa.schema([("name", pa.string()), ("n", pa.int64()), ("x", pa.float64())])
    rows = [{"name": "a", "n": 1, "x": 0.5}, {"name": "", "n": None, "x": 2.5}]
    tables.write_csv(rows, tmp_path / "sub" / "rows.csv", schema)
    assert tables.read_csv(tmp_path / "sub" / "rows.csv") == rows
    assert tables.csv_columns(tmp_path / "sub" / "rows.csv") == ["name", "n", "x"]
    arrays = {"name": np.array(["a", "b"], object), "n": np.array([1, 2]), "x": np.array([0.5, np.nan])}
    tables.write_parquet(arrays, tmp_path / "sub" / "cols.parquet", schema)
    read = tables.read_parquet(tmp_path / "sub" / "cols.parquet")
    assert tables.parquet_columns(tmp_path / "sub" / "cols.parquet") == ["name", "n", "x"]
    assert read["name"].tolist() == ["a", "b"] and read["n"].tolist() == [1, 2] and np.isnan(read["x"][1])


def test_the_version_is_the_short_commit_dirty_when_a_tracked_file_changed_and_unknown_without_git(tmp_path):
    def git(*arguments):
        return subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *arguments], check=True, capture_output=True, text=True).stdout.strip()
    assert version.git_commit(tmp_path) == "unknown"
    git("init", "-q")
    (tmp_path / "a.txt").write_text("one\n")
    git("add", "a.txt")
    git("commit", "-q", "-m", "one")
    commit = git("rev-parse", "--short", "HEAD")
    (tmp_path / "untracked.txt").write_text("x\n")
    assert version.git_commit(tmp_path) == commit
    (tmp_path / "a.txt").write_text("two\n")
    assert version.git_commit(tmp_path) == f"{commit}+dirty"
