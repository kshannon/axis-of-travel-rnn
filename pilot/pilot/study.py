"""
Notebook section 3: every run through the trace path and the section 8 measures, as one plain row per run.
"""

import numpy as np
import torch
from proj_helpers.paths import repo_root
from tqdm import tqdm

from . import analysis, train, viz
from .config import ANALYSIS_SEED, NUM_THREADS, THRESHOLDS_SHA256, WORLDS
from .dataset import fit_scaler, make_feature_layout, select_sessions

THRESHOLDS_PATH = str(analysis.THRESHOLDS.relative_to(repo_root()))


# ---------------------------------------------------------------------------
# the gate and the file it reads
# ---------------------------------------------------------------------------

def thresholds_source():
    """
    Where the thresholds file stands in git: its last commit, or uncommitted.
    """
    commit = train.git("log", "-1", "--format=%h", "--", THRESHOLDS_PATH)
    changed = train.git("status", "--short", "--", THRESHOLDS_PATH)
    return "uncommitted" if not commit else f"commit {commit}" + (" with uncommitted changes" if changed else "")


def blockers_of(checks, results, jobs, sha):
    """
    The failed section 2 checks, and the other reasons section 3 may not run (an unfinished sweep, a changed file).
    """
    failed = [name for name, passed, _ in checks if not passed]
    blockers = []
    if len(results) < len(jobs):
        blockers.append(f"the sweep is not finished ({len(results)} of {len(jobs)} runs)")
    if sha != THRESHOLDS_SHA256:
        blockers.append("thresholds.yaml does not match THRESHOLDS_SHA256")
    return failed, blockers


def check_gate(failed, blockers, override):
    """
    Raise unless section 3 may run: the override covers failed checks, never the other blockers.
    """
    if blockers:
        raise RuntimeError("Section 3 refuses to run: " + "; ".join(blockers) + ". The override does not cover these.")
    if failed and not override:
        raise RuntimeError("Section 3 refuses to run, the section 2 checks failed: " + "; ".join(failed)
                           + ". Fix the task first (brief section 9, last row), or set OVERRIDE_FAILED_CHECKS = True "
                           "to analyse the runs anyway.")


# ---------------------------------------------------------------------------
# one row per run
# ---------------------------------------------------------------------------

def world_test_sessions(cfg, sessions):
    """
    The test sessions of each world, as {world: [sessions]}.
    """
    return {world: select_sessions(sessions, cfg, "test", (world,)) for world in WORLDS}


def traces_of(arm, seed, cfg, sessions, test):
    """
    The trace path of one run over every test session of both worlds, with the input noise of the section 2 decoders.
    """
    model = train.load_model(train.run_dir(arm, seed, cfg), cfg)
    layout = make_feature_layout(arm.input_set, cfg)
    scaler = fit_scaler(select_sessions(sessions, cfg, "train", arm.diet))
    return {world: [viz.session_trace(model, s, layout, scaler, cfg, train.NOISE_SEEDS["test"]) for s in test[world]]
            for world in WORLDS}


def measure(traces, key, test, thr):
    """
    Sections 8.1 to 8.4 with the block `key` of the traces ("hidden", or the input "x") as the units.
    """
    return analysis.analyse_units(test["loop"], [t[key] for t in traces["loop"]],
                                  test["open_field"], [t[key] for t in traces["open_field"]],
                                  thr, np.random.default_rng(ANALYSIS_SEED))


def record(arm_label, input_set, kind, diet, seed, result):
    """
    One row of the analysis table: unit counts of the three tests and the population ratios.
    """
    axis = result["axis"].any(axis=1)
    return {"input_set": input_set, "arm": arm_label, "kind": kind, "diet": diet, "seed": seed,
            "n_units": len(axis), "n_direction": int(result["direction"].any(axis=1).sum()), "n_axis": int(axis.sum()),
            "n_persist": int(result["persists"].sum()), "released": result["fractions"]["released"],
            **{key: result["distances"][key] for key in ("opposite_over_cross", "parallel_over_cross")}}


def kept_units(traces, key, result):
    """
    The units of a run per world and session, with its analysis result, for the figures.
    """
    return {"units": {world: [t[key] for t in traces[world]] for world in WORLDS}, "result": result}


def analysis_jobs(cfg, input_sets):
    """
    The runs of the sweep that are analysed: all but the memoryless nets, which have no trace path.
    """
    return [(arm, seed) for arm, seed in train.sweep_jobs(cfg, input_sets) if arm.kind != "memoryless"]


def analyse_runs(cfg, sessions, thr, jobs):
    """
    Rows for the (arm, seed) jobs and an inputs row for the first job of each input set; kept has the figure material.
    """
    torch.set_num_threads(NUM_THREADS)
    test = world_test_sessions(cfg, sessions)
    rows, kept, seen = [], {}, set()  # kept: the place_only runs of seed 0 on both worlds, and the place_only inputs
    for arm, seed in tqdm(jobs, desc="analysis"):
        traces = traces_of(arm, seed, cfg, sessions, test)
        diet = "both" if arm.diet == WORLDS else arm.diet[0]
        result = measure(traces, "hidden", test, thr)
        rows.append(record(train.label(arm), arm.input_set, arm.kind, diet, seed, result))
        if arm.input_set == "place_only" and seed == 0 and diet == "both":
            kept[arm.kind] = kept_units(traces, "hidden", result)
        if arm.input_set not in seen:  # the input channels, once per input set: the input does not depend on the net
            seen.add(arm.input_set)
            result = measure(traces, "x", test, thr)
            rows.append(record("inputs", arm.input_set, "inputs", "both", "-", result))
            if arm.input_set == "place_only":
                kept["inputs"] = kept_units(traces, "x", result)
    return rows, kept


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------

def share(n, total):
    """
    A count with its percentage of the total.
    """
    return f"{n} ({100 * n / total:.1f}%)"


def run_table(rows, input_set):
    """
    Lines of the analysis rows of one input set.
    """
    lines = [("arm", "seed", "direction units", "axis units", "released of axis", "released / all",
              "opposite / cross", "parallel / cross")]
    for r in rows:
        if r["input_set"] == input_set:
            lines.append((r["arm"], r["seed"], share(r["n_direction"], r["n_units"]), share(r["n_axis"], r["n_units"]),
                          f"{r['n_axis'] - r['n_persist']} of {r['n_axis']}", f"{100 * r['released']:.1f}%",
                          f"{r['opposite_over_cross']:.3f}", f"{r['parallel_over_cross']:.3f}"))
    return train.format_rows(lines)


def mean_range(group, key):
    """
    Mean (and range) of one key over the rows of a group.
    """
    values = [r[key] for r in group]
    if len(values) == 1:
        return f"{values[0]:.3f}"
    return f"{np.mean(values):.3f} ({min(values):.3f} to {max(values):.3f})"


def population_table(rows, input_set):
    """
    Lines of the population measure, mean (range) over the seeds of each arm of one input set.
    """
    lines = [("arm", "runs", "opposite / cross", "parallel / cross")]
    for label in dict.fromkeys(r["arm"] for r in rows if r["input_set"] == input_set):
        group = [r for r in rows if r["input_set"] == input_set and r["arm"] == label]
        lines.append((label, len(group), mean_range(group, "opposite_over_cross"),
                      mean_range(group, "parallel_over_cross")))
    return train.format_rows(lines)


def tables_text(rows, input_sets):
    """
    Per input set the table of every run, then the population measure by arm, as lines.
    """
    lines = []
    for input_set in input_sets:
        lines += [f"== {input_set}: every run", *run_table(rows, input_set), "",
                  "population measure, mean (range) over the seeds of each arm", *population_table(rows, input_set), ""]
    return lines


def raw_place_check(rows):
    """
    The section 1 check that waited for the analysis: the raw place channels have no direction and no axis units.
    """
    raw = next(r for r in rows if r["input_set"] == "place_only" and r["kind"] == "inputs")
    status = "pass" if raw["n_direction"] == raw["n_axis"] == 0 else "FAIL"
    return (f"[{status}] raw place channels: {raw['n_direction']} direction units and {raw['n_axis']} axis units of "
            f"{raw['n_units']} channels (the test sessions, noisy input)")
