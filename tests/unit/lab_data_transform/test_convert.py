"""
The processing rules: both MATLAB formats, NaN by the flags, epochs by the tag, pairing, and the integrity checks.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from lab_data_transform.transform_helpers import checks
from lab_data_transform.transform_helpers.convert import build_runs, pair_events
from lab_data_transform.transform_helpers.convert import convert as convert_record
from lab_data_transform.transform_helpers.orchestrator import Record
from lab_data_transform.transform_helpers.readers import (
    ANALYSIS_PROVENANCE, ANALYSIS_VARIABLES, DVT_COLUMNS, FLAGS, TRACKING_PROVENANCE, TRACKING_REQUIRED, Session, read,
)

from .synthetic_mat import example_session, session_names, write_session

SID = "NS14_rec27_20150219_001"
N = 900


def session_for(tag_raw, folder=Path()):
    """
    A Session for the synthetic recording with this variant tag as written, its two files in folder.
    """
    dvt_name, rmaps_name = session_names("NS14", 27, "021915", "001", tag_raw)
    return Session(session_id=SID, subject_id="NS14", group="NS14Data", session="001", rec=27,
                   date=date(2015, 2, 19), tag=tag_raw.lower() if tag_raw else None, tag_raw=tag_raw,
                   dvt_path=folder / dvt_name, rmaps_path=folder / rmaps_name)


def written(folder, variables, fmt):
    """
    The Session of the variables written to folder in this MATLAB format.
    """
    session = session_for(None, folder)
    write_session(folder, variables, (session.dvt_path.name, session.rmaps_path.name), fmt)
    return session


def convert(variables, tag=None):
    """
    The variables checked, converted and checked as the runner does, without a file, stopping at a fail.
    """
    trk = {k: variables[k] for k in TRACKING_REQUIRED + TRACKING_PROVENANCE if k in variables}
    ana = {k: variables[k] for k in ANALYSIS_VARIABLES + ANALYSIS_PROVENANCE if k in variables}
    trk.update({name: trk[name] != 0 for name in FLAGS})
    for value in [*trk.values(), *ana.values()]:
        if isinstance(value, np.ndarray):
            value.setflags(write=False)  # a stage that writes into its input fails
    record = Record(session_for(tag), trk, ana)
    for stage in (checks.check_inputs, convert_record, checks.check_converted):
        record = stage(record)
        if record.failed:
            break
    return record


@pytest.mark.parametrize("fmt", ["classic", "v7.3"])
def test_both_formats_read_to_the_values_written(tmp_path, fmt):
    variables = example_session()
    record = read(Record(written(tmp_path, variables, fmt)))
    got = {**record.trk, **record.ana}
    assert set(got) == set(variables)
    for name, value in variables.items():
        np.testing.assert_equal(got[name], value, err_msg=name)


def test_positions_are_nan_by_the_flags_never_the_pixels():
    variables = example_session()
    dvt = variables["processedDVT"]
    dvt[:, 2:] = 200.0      # no sentinel where a light is flagged unfilled
    dvt[399, 2:] = 1.0      # frame 400: a real (1, 1) everywhere, nothing flagged
    unfilled = variables["samplesUnfilled"] == 1
    gone = {"front": unfilled[:, 0], "back": unfilled[:, 1], "avg": unfilled.any(axis=1),
            "mashup": unfilled.all(axis=1)}

    frames = convert(variables).frames
    for name in ("front_x", "front_y", "back_x", "back_y", "avg_x", "avg_y", "mashup_x", "mashup_y"):
        want = dvt[:, DVT_COLUMNS[name]].copy()
        want[gone[name.split("_")[0]]] = np.nan
        np.testing.assert_array_equal(frames.column(name).to_numpy(), want, err_msg=name)


# tag as written, the arena and track condition, the variant epoch's (environment, condition) and the protocol
TAG_ROWS = [
    (None, "baseline", None, "standard"),
    ("plus45", "baseline", ("triple_t_rot45", "rot45"), "rotation"),
    ("bilatmusc", "musc_bilateral", ("triple_t", "musc_bilateral"), "infusion"),
    ("dark", "dark", ("triple_t", "dark"), "dark"),
    ("NewDrug", "baseline", ("triple_t", "NewDrug"), "other"),
    ("LeftMusc", "musc_left", ("triple_t", "musc_left"), "infusion"),
]


@pytest.mark.parametrize("tag, condition, variant, protocol", TAG_ROWS, ids=[str(row[0]) for row in TAG_ROWS])
def test_epochs_and_protocol_follow_the_tag(tag, condition, variant, protocol):
    variables = example_session()
    variables["timeStamps"] = np.array([101, 400, 451, 700, 721, 880][:6 if variant else 4], dtype=float)
    t = variables["processedDVT"][:, 1]
    want = [("arena", "open_arena", condition, 101, 400), ("track", "triple_t", condition, 451, 700)]
    if variant:
        want.append(("variant", *variant, 721, 880))

    record = convert(variables, tag)
    epochs = record.rows["epochs"]
    assert [(e["epoch"], e["environment"], e["condition"], e["frame_start"], e["frame_end"]) for e in epochs] == want
    assert [(e["t_start"], e["t_end"], e["duration_s"]) for e in epochs] == [
        (t[first - 1], t[last - 1], (last - first + 1) / 60) for *_, first, last in want]
    epoch_of = [next((w[0] for w in want if w[3] <= frame <= w[4]), None) for frame in range(1, N + 1)]
    assert record.frames.column("epoch").to_pylist() == epoch_of
    assert record.rows["sessions"][0]["protocol"] == protocol
    assert record.results["tag_known"]["status"] == ("warn" if tag == "NewDrug" else "pass")


@pytest.mark.parametrize("stamps, status", [
    pytest.param(None, "absent", id="absent"),
    pytest.param([21, 150, 161], "count", id="count"),
    pytest.param([21, 150, 150, 700], "order", id="order"),
    pytest.param([21, 150, 161, 901], "range", id="outside the tracking"),
    pytest.param([21.5, 150, 161, 700], "range", id="non-whole"),
])
def test_unusable_stamps_give_no_epochs(stamps, status):
    variables = example_session()
    if stamps is None:
        del variables["timeStamps"]
    else:
        variables["timeStamps"] = np.array(stamps, dtype=float)

    record = convert(variables)
    assert record.facts["stamps"] == status
    assert record.rows["epochs"] == []
    assert set(record.frames.column("epoch").to_pylist()) == {None}
    assert record.results["stamps_usable"]["status"] == "warn"


# (frame, label) in click order, with pauses at frames 230 and 300; runs are numbered by start frame, then click order
RULE_CLICKS = [
    (205, 1), (214, 101),               # run 2 shares all its 10 frames with run 1: a duplicate
    (200, 1), (230, 101),               # run 1, clicked after run 2 but starting first, ends on a pause frame
    (205, -1), (228, -101),             # run 3, dirty, clicked after run 2 so numbered after it; its sign: no duplicate
    (240, -2), (250, 102),              # signs differ: no pair
    (260, 2), (262, 4), (270, 104),     # a start pairs only with the next start or end row: 2 has no pair
    (300, 2), (319, 102),               # run 5 starts on a pause frame, which it does not span
    (310, 2), (329, 102),               # run 6 shares exactly half (10 of 20 frames) with run 5: a duplicate
    (400, 3), (418, 103),               # run 7 has 19 frames
    (410, 3), (429, 103),               # run 8 shares 9 of 19 with run 7: under half, no duplicate
    (500, 5), (530, 105),               # run 9
    (502, 5), (532, 105),               # run 10 duplicates run 9
    (505, 5), (525, 105),               # run 11 matches runs 9 and 10, and the earliest is its original
]
# per run: first frame, last frame, path, clean, duplicate_of, overlap_frames, spans_pause
RULE_RUNS = [
    (200, 230, 1, True, None, 0, True),
    (205, 214, 1, True, 1, 26, False),
    (205, 228, 1, False, None, 10, False),
    (262, 270, 4, True, None, 0, False),
    (300, 319, 2, True, None, 0, False),
    (310, 329, 2, True, 5, 10, False),
    (400, 418, 3, True, None, 0, False),
    (410, 429, 3, True, None, 9, False),
    (500, 530, 5, True, None, 0, False),
    (502, 532, 5, True, 9, 29, False),
    (505, 525, 5, True, 9, 28, False),
]


def test_runs_pair_by_the_rules_and_the_lab_counts_agree():
    events = np.array([[frame, 0, label] for frame, label in RULE_CLICKS], dtype=float)
    pairs = pair_events(events)
    assert pairs == [(0, 1), (2, 3), (4, 5), (9, 10), *[(i, i + 1) for i in range(11, len(RULE_CLICKS), 2)]]

    rows, run_by_event = build_runs(SID, pairs, events, np.arange(1, N + 1) / 60, N, [], [(230, 1.0), (300, 1.0)], 60)
    assert [r["run"] for r in rows] == list(range(1, len(RULE_RUNS) + 1))
    assert [(r["frame_start"], r["frame_end"], r["path_id"], r["clean"], r["duplicate_of"], r["overlap_frames"],
             r["spans_pause"]) for r in rows] == RULE_RUNS
    assert [r["duration_s"] for r in rows] == [(end - start + 1) / 60 for start, end, *_ in RULE_RUNS]
    assert run_by_event == {i: k + 1 for k, pair in enumerate([pairs[1], pairs[0], *pairs[2:]]) for i in pair}

    # the lab's nRuns and run markers per path (pathList 1, 2) agree with the clean pairs, and a change warns
    assert convert(example_session()).results["lab_counts_match"]["status"] == "pass"
    variables = example_session()
    variables["nRuns"] = np.array([1, 2], dtype=float)
    variables["runPosMarkers"][0][1] = np.array([231.0])
    detail = convert(variables).results["lab_counts_match"]
    assert detail == {"status": "warn", "detail": {"nruns_differ": [2], "markers_differ": [1]}}


def test_integrity_rules_stop_bad_data(tmp_path):
    # a file with no frames fails
    empty = example_session()
    empty.update(processedDVT=np.empty((0, 10)), HDRadians=np.empty(0), samplesFilled=np.empty((0, 2)),
                 samplesUnfilled=np.empty((0, 2)))
    assert checks.failed(convert(empty).results) == ["tracking_lengths"]

    # an event frame that is no whole number is not stored as the file holds it, so the event rows are not the file's
    changed = example_session()
    changed["spiral_events"][3, 0] += 0.5
    assert checks.failed(convert(changed).results) == ["rows_conserved"]

    # a repeated run row fails keys_unique
    repeated = convert(example_session())
    repeated.rows["runs"].append(repeated.rows["runs"][0])
    assert checks.failed(checks.check_converted(repeated).results) == ["keys_unique"]

    # a pixelDvt of the wrong width is not aligned, so no frame has a painted label
    narrow = example_session()
    narrow["pixelDvt"] = narrow["pixelDvt"][:, :10]
    assert convert(narrow).frames.column("painted_label").null_count == N

    # a run ending beyond the tracking has its start time and no end time
    beyond = example_session()
    beyond["spiral_events"][-1, 0] = N + 5
    run = convert(beyond).rows["runs"][-1]
    assert (run["frame_end"], run["t_start"], run["t_end"]) == (N + 5, beyond["processedDVT"][439, 1], None)

    # an empty manifest-only number reads as absent in both formats
    variables = example_session()
    variables["nRealLights"] = np.array([])
    for fmt in ("classic", "v7.3"):
        assert read(Record(written(tmp_path / fmt, variables, fmt))).trk["nRealLights"] is None
