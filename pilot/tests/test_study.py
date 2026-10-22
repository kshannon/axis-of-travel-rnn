"""
Notebook section 3 as functions: the gate, one row per run and one inputs row per input set, the tables.
"""

import pytest

from pilot import analysis, study, train
from pilot.config import SMOKE, THRESHOLDS_SHA256
from pilot.worlds import WORLDS, load_sessions, make_layouts

CFG = SMOKE
SESSIONS = load_sessions(CFG, make_layouts(CFG))  # the cached SMOKE sessions
THR = analysis.load_thresholds()
UNTRAINED = train.ArmSpec("place_only", WORLDS, "untrained")


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(train, "RUNS_DIR", tmp_path)  # runs never go into datasets/pilot


def test_the_gate_needs_a_complete_sweep_an_unchanged_file_and_passed_or_overridden_checks():
    checks = [("fine", True, ""), ("broken", False, "")]
    assert study.blockers_of(checks[:1], {1: 1, 2: 2}, [1, 2], THRESHOLDS_SHA256) == ([], [])
    failed, blockers = study.blockers_of(checks, {1: 1}, [1, 2], "changed")
    assert failed == ["broken"] and len(blockers) == 2
    with pytest.raises(RuntimeError, match="does not cover"):
        study.check_gate([], blockers, override=True)  # the override covers failed checks and nothing else
    with pytest.raises(RuntimeError, match="section 2 checks failed: broken"):
        study.check_gate(failed, [], override=False)
    study.check_gate(failed, [], override=True)
    study.check_gate([], [], override=False)


def test_analysis_jobs_leave_out_the_memoryless_nets():
    jobs = study.analysis_jobs(CFG, ("place_only",))
    assert {arm.kind for arm, _ in jobs} == {"trained", "untrained"} and len(jobs) == 3


def test_each_run_gets_a_row_and_each_input_set_one_inputs_row_and_a_rerun_gives_the_same_rows():
    jobs = [(UNTRAINED, 0), (UNTRAINED, 1)]
    for arm, seed in jobs:
        train.run_arm(arm, seed, CFG, SESSIONS)
    rows, kept = study.analyse_runs(CFG, SESSIONS, THR, jobs)
    first, inputs, second = rows  # the inputs row comes after the first run of the input set only
    assert (first["arm"], first["kind"], first["diet"], first["seed"], first["n_units"]) == (
        "untrained_both", "untrained", "both", 0, 128)
    assert second["seed"] == 1 and second["kind"] == "untrained"
    assert (inputs["arm"], inputs["kind"], inputs["seed"], inputs["n_units"]) == ("inputs", "inputs", "-", 100)
    assert set(kept) == {"untrained", "inputs"} and kept["untrained"]["units"]["loop"][0].shape[1] == 128
    assert study.analyse_runs(CFG, SESSIONS, THR, jobs)[0] == rows  # the nulls are seeded
    lines = study.tables_text(rows, ("place_only",))
    assert lines[0] == "== place_only: every run" and any(line.startswith("inputs") for line in lines)


def test_the_raw_place_channel_check_fails_on_any_direction_or_axis_unit():
    def raw(n_direction, n_axis):
        return [{"input_set": "place_only", "kind": "inputs", "n_direction": n_direction, "n_axis": n_axis,
                 "n_units": 100}]

    assert study.raw_place_check(raw(0, 0)).startswith("[pass]")
    assert study.raw_place_check(raw(1, 0)).startswith("[FAIL]")
    assert study.raw_place_check(raw(0, 2)).startswith("[FAIL]")
