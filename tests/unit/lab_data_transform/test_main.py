"""
The runner: setup guards, the dry run, a failed session and a rerun.
"""

import json
import os
from pathlib import Path

import pytest

import lab_data_transform.__main__ as entry
from lab_data_transform.transform_helpers import convert

from .synthetic_mat import example_session, session_names, write_session

# the two sessions of the lab_root fixture in recording order: v7.3 with no tag, then classic with bilatmusc
A = "JL1_rec23_20140715_001"
B = "NS14_rec27_20150219_001"

# the lab folder and the output folder under tmp_path, the lab data in "lab", None leaving that key out
GUARDS = [
    pytest.param("lab", None, id="a missing key"),
    pytest.param(None, None, id="an empty config"),
    pytest.param("nowhere", "out", id="the lab folder missing"),
    pytest.param("lab", "lab", id="output equals the lab data"),
    pytest.param("lab", "lab/out", id="output inside the lab data"),
    pytest.param("lab", ".", id="output contains the lab data"),
    pytest.param("lab", "repo", id="output equals the repository"),
    pytest.param("lab", "repo/out", id="output inside the repository"),
]


@pytest.mark.parametrize("lab, out", GUARDS)
def test_a_bad_setup_exits_2(tmp_path, monkeypatch, lab, out):
    (tmp_path / "lab").mkdir()
    monkeypatch.setattr(entry, "repo_root", lambda: tmp_path / "repo")
    pairs = zip(("LAB_DATA", "TRANSFORMED_LAB_DATA"), (lab, out))
    with pytest.raises(SystemExit) as stop:
        entry.main(["--dry-run"], config={key: str(tmp_path / value) for key, value in pairs if value is not None})
    assert stop.value.code == 2


def test_a_dry_run_opens_no_mat_file_and_writes_nothing(config, lab_root):
    if os.geteuid() == 0:
        pytest.skip("root reads a file whatever its mode")
    mats = sorted(lab_root.rglob("*.mat"))
    before = sorted(lab_root.rglob("*"))
    for mat in mats:
        mat.chmod(0)
    try:
        assert entry.main(["--dry-run"], config=config) == 0
    finally:
        for mat in mats:
            mat.chmod(0o644)
    assert not Path(config["TRANSFORMED_LAB_DATA"]).exists()
    assert sorted(lab_root.rglob("*")) == before


def shorten_heading(config, monkeypatch):
    """
    Rewrite A's files with a heading one sample short, so the tracking arrays differ in length.
    """
    variables = example_session()
    variables["HDRadians"] = variables["HDRadians"][:-1]
    write_session(Path(config["LAB_DATA"]) / "JL1HPCData", variables, session_names("JL1", 23, "071514", "001"), "v7.3")


def raise_in_convert(config, monkeypatch):
    """
    Make convert.convert raise for A and behave as before for every other session.
    """
    real = convert.convert

    def broken(record):
        if record.session.session_id == A:
            raise RuntimeError("synthetic failure")
        return real(record)

    monkeypatch.setattr(convert, "convert", broken)


@pytest.mark.parametrize("breaker, check", [(shorten_heading, "tracking_lengths"), (raise_in_convert, "exception")])
def test_a_failed_first_session_does_not_stop_the_later_one_and_exits_1(config, monkeypatch, breaker, check):
    breaker(config, monkeypatch)
    assert entry.main([], config=config) == 1
    run = json.loads((Path(config["TRANSFORMED_LAB_DATA"]) / "manifest.json").read_text())["run"]
    assert run["written"] == [B]
    assert {sid: list(found) for sid, found in run["failed"].items()} == {A: [check]}


def test_a_rerun_gives_identical_files(config):
    root = Path(config["TRANSFORMED_LAB_DATA"])

    def files():
        # the manifest holds the run's timestamps
        return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
                and p.name != "manifest.json"}

    assert entry.main([], config=config) == 0
    first = files()
    assert entry.main([], config=config) == 0
    assert files() == first
    assert len(first) == 4 + 1 + 2  # the CSV tables, checks.json and a frames file per session
