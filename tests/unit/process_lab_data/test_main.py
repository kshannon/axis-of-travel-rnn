"""
The runner: setup guards, the dry run and the real run stub.
"""

from pathlib import Path

import pytest

import process_lab_data.__main__ as entry

from .conftest import S1, S6

# the transformed folder and the output folder under tmp_path, the tables in "transformed", None leaving that key out
GUARDS = [
    pytest.param("transformed", None, "PROCESSED_LAB_DATA", id="a missing key"),
    pytest.param(None, None, "TRANSFORMED_LAB_DATA", id="an empty config"),
    pytest.param("nowhere", "out", "not a folder holding", id="the transformed folder missing"),
    pytest.param("empty", "out", "not a folder holding", id="the transformed folder without the tables"),
    pytest.param("transformed", "transformed", "is the transformed lab data", id="output equals the input"),
    pytest.param("transformed", "transformed/out", "is the transformed lab data", id="output inside the input"),
    pytest.param("transformed", ".", "contains the transformed lab data", id="output contains the input"),
    pytest.param("transformed", "repo", "is the repository", id="output equals the repository"),
    pytest.param("transformed", "repo/out", "is the repository", id="output inside the repository"),
]


@pytest.mark.parametrize("source, out, problem", GUARDS)
def test_a_bad_setup_exits_2_naming_the_problem(tmp_path, transformed, monkeypatch, capsys, source, out, problem):
    (tmp_path / "empty").mkdir()
    monkeypatch.setattr(entry, "repo_root", lambda: tmp_path / "repo")
    pairs = zip(("TRANSFORMED_LAB_DATA", "PROCESSED_LAB_DATA"), (source, out))
    with pytest.raises(SystemExit) as stop:
        entry.main(["--dry-run"], config={key: str(tmp_path / value) for key, value in pairs if value is not None})
    assert stop.value.code == 2
    assert problem in capsys.readouterr().err


def test_a_dry_run_prints_the_funnel_and_the_blocks_and_writes_nothing(config, transformed, capsys):
    before = sorted(transformed.rglob("*"))
    assert entry.main(["--dry-run", "--list"], config=config) == 0
    out = capsys.readouterr().out
    assert "sessions, all sessions: 6" in out and "epochs, condition baseline: 3" in out
    assert "blocks, cut at pauses and gaps: 4" in out and "blocks, at least 10 s: 2" in out
    assert "  arena: 1 blocks, 10 s, durations 10, 10, 10, 10" in out
    assert f"  {S1}_track_01  600 frames  10.0 s" in out and S6 not in out
    assert "track/blocks.csv" in out and "manifest.json" in out
    assert not Path(config["PROCESSED_LAB_DATA"]).exists()
    assert sorted(transformed.rglob("*")) == before


def test_the_real_run_stub_exits_3_and_writes_nothing(config):
    assert entry.main([], config=config) == 3
    assert not Path(config["PROCESSED_LAB_DATA"]).exists()
