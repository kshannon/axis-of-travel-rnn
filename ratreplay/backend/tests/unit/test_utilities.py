"""
The config utility answers a key's path and names the file when it cannot, and the folder time is the newest file's.
"""

import os
from datetime import datetime, timezone

import pytest
import yaml

from ratreplay_api.utilities import paths
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
