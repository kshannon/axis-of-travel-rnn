"""
TrajectoryEngine.blocks over the synthetic fixtures, in parity with the processor, which is imported here as the oracle and nowhere else, and the labels of a hand made run sequence.
"""

import json
from itertools import groupby
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest
from fixtures import S1, S6, STAMP, write_processed
from process_lab_data import output as old_output

import ratreplay_api.engines.trajectory.session as session_module
from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.processed import BLOCK_SCHEMA, BLOCKS_CSV_SCHEMA, METADATA_KEYS, ProcessedAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.trajectory import RULES, TrajectoryEngine, build, heading, labels

ENVIRONMENTS = Path(__file__).resolve().parents[4] / "configs" / "environments"
TOLERANCE = 1e-12
RATE_HZ = 20

# The one difference from the processor's rows: it wrote "automatic" as the status of a block no review kept, the engine
# keeps the initial block's own status, "auto". The processor's kind is the folder of its csv, the engine's a column.
STATUS_OF_THE_PROCESSOR = {"automatic": "auto"}

# S1's rat stands still for 91 frames inside its first run (frames 2200 to 2300), so the run holds a pause. The review keeps
# S1's arena block, edits its track block to start before the first run and end after the second, drops a second track
# block and flags the third run. S6 is not reviewed.
STILL = slice(2204, 2295)
REVIEWER = "kyle"
BLOCKS_OF_THE_REVIEW = [
    {"block_id": f"{S1}_arena_01", "epoch": "arena", "environment": "open_arena", "frame_start": 301, "frame_end": 1500, "status": "confirmed", "note": None},
    {"block_id": f"{S1}_track_01", "epoch": "track", "environment": "triple_t", "frame_start": 2151, "frame_end": 2750, "status": "edited", "note": None},
    {"block_id": f"{S1}_track_02", "epoch": "track", "environment": "triple_t", "frame_start": 2851, "frame_end": 3300, "status": "dropped", "note": None},
]
REVIEW = {"session_id": S1, "reviewed_by": REVIEWER, "reviewed_at": STAMP, "rules": {}, "blocks": BLOCKS_OF_THE_REVIEW, "flagged_runs": [3]}

# A block of 400 frames at 20 Hz: an outbound run on path 1, a dwell, a return on path 9, a dwell.
SEQUENCE_RUNS = [{"run": 1, "path_id": 1, "clean": True, "frame_start": 1, "frame_end": 100, "duplicate_of": None},
                 {"run": 2, "path_id": 9, "clean": False, "frame_start": 201, "frame_end": 300, "duplicate_of": None}]


@pytest.fixture
def paused(transformed):
    """
    The transformed folder with S1's rat still for 91 frames inside its first run, the path after it delayed by those frames so there is no jump.
    """
    path = transformed / "frames" / f"{S1}.parquet"
    table = pq.read_table(path)
    for name in ("mashup_x", "mashup_y"):
        before = table.column(name).to_numpy()
        values = before.copy()
        values[STILL] = before[STILL.start]
        values[STILL.stop:] = before[STILL.start:STILL.start + len(before) - STILL.stop]
        table = table.set_column(table.schema.get_field_index(name), name, pa.array(values))
    pq.write_table(table, path)
    return transformed


@pytest.fixture
def automatic(tmp_path, paused):
    """
    The processor's output over the paused folder with no review.
    """
    write_processed(paused, tmp_path / "automatic")
    return oracle(tmp_path / "automatic")


@pytest.fixture
def reviewed(tmp_path, paused):
    """
    The processor's output over the paused folder with S1's review.
    """
    (tmp_path / "reviewed" / "review").mkdir(parents=True)
    (tmp_path / "reviewed" / "review" / f"{S1}.json").write_text(json.dumps(REVIEW))
    write_processed(paused, tmp_path / "reviewed")
    return oracle(tmp_path / "reviewed")


def oracle(root):
    """
    Every block the processor wrote under the root by id, its csv row with the kind of its folder and its rate (its frames over its seconds, which the old csv did not hold) added and its parquet columns.
    """
    options = pacsv.ConvertOptions(column_types=old_output.BLOCKS_CSV_SCHEMA, strings_can_be_null=True)
    found = {}
    for kind in ("arena", "track"):
        for row in pacsv.read_csv(root / kind / "blocks.csv", convert_options=options).to_pylist():
            table = pq.read_table(root / kind / "blocks" / f"{row['block_id']}.parquet")
            found[row["block_id"]] = {"row": {**row, "kind": kind, "rate_hz": round(row["n_frames"] / row["duration_s"])}, "arrays": {name: table.column(name).to_numpy() for name in table.column_names}}
    return found


def loaded(transformed, sid):
    """
    The session as TransformedAccess gives it, with writable copies of its arrays, and the geometry of every environment by name.
    """
    found = TransformedAccess(transformed).session(sid)
    access = EnvironmentAccess(ENVIRONMENTS)
    return {**found, "arrays": {name: values.copy() for name, values in found["arrays"].items()}}, {n: access.environment(n) for n in access.environments()}


def same_arrays(mine, theirs):
    """
    The columns equal one by one, floats to the tolerance with NaN where the other has NaN, everything else exactly.
    """
    assert list(mine) == list(theirs) == BLOCK_SCHEMA.names
    for name in mine:
        if mine[name].dtype.kind == "f":
            np.testing.assert_allclose(mine[name], theirs[name], rtol=0, atol=TOLERANCE, equal_nan=True, err_msg=name)
        else:
            np.testing.assert_array_equal(mine[name], theirs[name], err_msg=name)


def same_row(mine, theirs):
    """
    The index rows equal field by field, floats to the tolerance, the processor's status mapped to the engine's.
    """
    assert set(mine) == set(theirs)
    for name, value in theirs.items():
        value = STATUS_OF_THE_PROCESSOR.get(value, value) if name == "status" else value
        assert mine[name] == (pytest.approx(value, rel=0, abs=TOLERANCE) if isinstance(value, float) else value), name


def same_blocks(made, theirs, sid):
    """
    The engine's blocks are exactly the processor's blocks of the session, each equal in its arrays and its row.
    """
    expected = {block_id: b for block_id, b in theirs.items() if b["row"]["session_id"] == sid}
    assert expected and sorted(b["row"]["block_id"] for b in made) == sorted(expected)
    for block in made:
        same_arrays(block["arrays"], expected[block["row"]["block_id"]]["arrays"])
        same_row(block["row"], expected[block["row"]["block_id"]]["row"])
        assert block["problems"] == []


def test_the_blocks_of_unreviewed_sessions_equal_the_processors_column_by_column_and_field_by_field(paused, automatic):
    for sid in (S1, S6):
        found, environment = loaded(paused, sid)
        same_blocks(TrajectoryEngine().blocks(found, None, environment, RULES)["blocks"], automatic, sid)
    assert len(automatic) == 3 and {p for b in automatic.values() for p in b["arrays"]["phase"]} == set(labels.PHASES)
    assert {b["row"]["status"] for b in automatic.values()} == {"automatic"} and automatic[f"{S1}_track_01"]["row"]["n_complete_trips"] == 1


def test_the_blocks_of_a_reviewed_session_equal_the_processors_and_a_session_without_review_still_builds_its_initial_block(paused, reviewed):
    found, environment = loaded(paused, S1)
    made = TrajectoryEngine().blocks(found, REVIEW, environment, RULES)["blocks"]
    same_blocks(made, reviewed, S1)
    found, environment = loaded(paused, S6)
    same_blocks(TrajectoryEngine().blocks(found, None, environment, RULES)["blocks"], reviewed, S6)
    assert sorted(reviewed) == [f"{S1}_arena_01", f"{S1}_track_01", f"{S6}_track_01"]
    edited = reviewed[f"{S1}_track_01"]
    assert edited["row"]["status"] == "edited" and edited["row"]["reviewed_by"] == REVIEWER and edited["row"]["n_complete_trips"] == 1
    assert set(edited["arrays"]["run"]) == {0, 1, 2}


def test_the_trips_and_phases_of_a_run_sequence_made_by_hand_follow_the_rules():
    frame, speed = np.arange(1, 401), np.full(400, 0.4)
    labelled = labels.label_frames(frame, speed, "track", SEQUENCE_RUNS, RATE_HZ, RULES)
    assert [phase for phase, _ in groupby(labelled["phase"])] == ["outbound", "dwell", "return", "dwell"]
    assert (labelled["trip"] == 1).all() and sorted(set(labelled["run"])) == [0, 1, 2] and sorted(set(labelled["path_id"])) == [0, 1, 9]
    assert not labelled["clean"][200:300].any() and labelled["clean"][:100].all()
    cut_short = [SEQUENCE_RUNS[0], {**SEQUENCE_RUNS[1], "frame_end": 450}]
    assert (labels.label_frames(frame, speed, "track", cut_short, RATE_HZ, RULES)["trip"] == -1).all()
    other_returns = labels.label_frames(frame, speed, "track", SEQUENCE_RUNS, RATE_HZ, {**RULES, "return_paths": (10,)})
    assert set(other_returns["phase"][200:300]) == {labels.DWELL} and (other_returns["trip"] == -1).all()
    foraging = labels.label_frames(frame, speed, "arena", [], RATE_HZ, RULES)
    assert set(foraging["phase"]) == {labels.FORAGE} and not foraging["trip"].any()


def test_a_dwell_before_the_first_outbound_run_is_a_partial_trip_and_the_next_trip_counts_on_from_it():
    frame, speed = np.arange(1, 401), np.full(400, 0.4)
    later = [{**r, "frame_start": r["frame_start"] + 50, "frame_end": r["frame_end"] + 50} for r in SEQUENCE_RUNS]
    labelled = labels.label_frames(frame, speed, "track", later, RATE_HZ, RULES)
    assert [phase for phase, _ in groupby(labelled["phase"])] == ["dwell", "outbound", "dwell", "return", "dwell"]
    assert (labelled["trip"][:50] == -1).all() and (labelled["trip"][50:] == 2).all()
    twice = [{**SEQUENCE_RUNS[0], "frame_start": 51, "frame_end": 100}, {**SEQUENCE_RUNS[0], "run": 2, "path_id": 2, "frame_start": 121, "frame_end": 170},
             {**SEQUENCE_RUNS[1], "run": 3, "frame_start": 251, "frame_end": 300}]
    trip = labels.label_frames(frame, speed, "track", twice, RATE_HZ, RULES)["trip"]
    assert (trip[:50] == -1).all() and (trip[50:120] == -2).all() and (trip[120:] == 3).all()


def test_a_slow_stretch_in_a_run_is_a_pause_only_when_it_is_longer_than_pause_min_s():
    frame, floor = np.arange(1, 401), RULES["running_floor_m_per_s"]
    assert RULES["pause_min_s"] * RATE_HZ == 20

    def phase_with(slow):
        speed = np.full(400, 0.4)
        speed[slow] = floor / 2
        return labels.label_frames(frame, speed, "track", SEQUENCE_RUNS, RATE_HZ, RULES)["phase"]
    assert (phase_with(slice(40, 70))[40:70] == labels.PAUSE).all()
    assert (phase_with(slice(75, 95))[75:95] == labels.OUTBOUND).all()
    assert (phase_with(slice(75, 96))[75:96] == labels.PAUSE).all()
    assert (phase_with(slice(150, 190))[150:190] == labels.DWELL).all()


def test_the_heading_fill_masks_of_a_block_equal_the_per_frame_fill_kind_for_spans_across_its_edges():
    frame, filled, held = np.arange(1, 101), np.zeros(100, bool), np.zeros(100, bool)
    filled[18:31], held[60:71] = True, True
    spans = heading.fill_spans(frame, [(18, 31, heading.FILLED, heading.ARC), (60, 71, heading.HELD, heading.STILL)], 60)
    assert [(s["first"], s["last"]) for s in spans["filled"]] == [(19, 31)] and [(s["first"], s["last"]) for s in spans["held"]] == [(61, 71)]
    for at in (slice(24, 66), slice(24, 80), slice(0, 100), slice(40, 55)):
        np.testing.assert_array_equal(build.in_spans(frame[at], spans["filled"]), filled[at])
        np.testing.assert_array_equal(build.in_spans(frame[at], spans["held"]), held[at])


def test_the_arrays_hold_the_block_schema_columns_and_no_motion_and_the_processed_access_takes_them(tmp_path, transformed):
    found, environment = loaded(transformed, S1)
    made = TrajectoryEngine().blocks(found, None, environment, RULES)
    assert not isinstance(found["session"]["date"], str) and set(made) == {"blocks", "frame", "warnings"}
    for block in made["blocks"]:
        assert list(block["arrays"]) == BLOCK_SCHEMA.names and "motion" not in block["arrays"]
        assert [pa.array(block["arrays"][field.name]).type for field in BLOCK_SCHEMA] == [field.type for field in BLOCK_SCHEMA]
        assert list(block["row"]) == BLOCKS_CSV_SCHEMA.names and isinstance(block["row"]["date"], str) and block["row"]["kind"] in labels.KINDS
    access = ProcessedAccess(tmp_path / "out")
    access.write_blocks(S1, made["blocks"], dict.fromkeys(METADATA_KEYS))
    assert [row["block_id"] for row in access.blocks()] == [b["row"]["block_id"] for b in made["blocks"]]
    for block in made["blocks"]:
        same_arrays(block["arrays"], access.block(block["row"]["block_id"])["arrays"])
    assert made["frame"]["track"]["scale_px_per_m"] > 0 and made["warnings"] == [w for w in made["warnings"] if w.startswith(S1)]


def test_a_blocks_position_is_the_registered_raw_position_never_the_smoothed_one(transformed):
    found, environment = loaded(transformed, S1)
    for name in ("mashup_x", "mashup_y"):
        found["arrays"][name] += np.random.default_rng(0).normal(0, 1.0, len(found["arrays"][name]))
    kin = TrajectoryEngine().session(found, environment, RULES)["kinematics"]
    for block in TrajectoryEngine().blocks(found, None, environment, RULES)["blocks"]:
        at = build.block_slice(found["arrays"]["frame"], block["row"])
        for raw, smooth in (("x", "x_smooth"), ("y", "y_smooth")):
            np.testing.assert_array_equal(block["arrays"][raw], kin[raw][at])
            assert np.nanmax(np.abs(block["arrays"][raw] - kin[smooth][at])) > 1e-3


def test_generated_style_arrays_build_the_same_blocks_under_their_own_session_id(transformed):
    found, environment = loaded(transformed, S1)
    generated = {**found, "session": {**found["session"], "session_id": "synthetic_0001"}}
    real, made = (TrajectoryEngine().blocks(arrays, None, environment, RULES) for arrays in (found, generated))
    assert [b["row"]["block_id"] for b in made["blocks"]] == ["synthetic_0001_arena_01", "synthetic_0001_track_01"]
    for new, old in zip(made["blocks"], real["blocks"]):
        same_arrays(new["arrays"], old["arrays"])
        assert new["row"] == {**old["row"], "block_id": new["row"]["block_id"], "session_id": "synthetic_0001"}
    assert made["frame"] == real["frame"] and made["warnings"] == [w.replace(S1, "synthetic_0001") for w in real["warnings"]]


def test_a_block_with_a_missing_position_or_an_irregular_step_in_t_names_the_problem_with_its_count_and_is_still_built(transformed):
    found, environment = loaded(transformed, S1)
    frames = found["arrays"]
    frames["mashup_x"][2499:2502] = np.nan
    frames["t"][2599:] += 0.01
    frames["t"][2799:] += 0.01
    arena, track = TrajectoryEngine().blocks(found, None, environment, RULES)["blocks"]
    assert arena["problems"] == []
    assert track["problems"] == ["position not finite on 3 frames", "t steps irregular, 2 frames off the rate"]
    assert np.isnan(track["arrays"]["x"]).sum() == 3 and len(track["arrays"]["t"]) == track["row"]["n_frames"] == 1200


def test_blocks_calls_session_once_and_every_rule_is_a_parameter(transformed, monkeypatch):
    found, environment = loaded(transformed, S1)
    calls, original = [], session_module.build

    def counted(*arguments):
        calls.append(arguments)
        return original(*arguments)
    monkeypatch.setattr(session_module, "build", counted)
    base = TrajectoryEngine().blocks(found, None, environment, RULES)
    assert len(calls) == 1 and [b["row"]["n_complete_trips"] for b in base["blocks"]] == [0, 1]
    other = TrajectoryEngine().blocks(found, None, environment, {**RULES, "outbound_paths": (2, 3, 4)})
    assert [b["row"]["n_complete_trips"] for b in other["blocks"]] == [0, 0] and other["blocks"][1]["row"]["n_runs"] == 3
    assert TrajectoryEngine().blocks(found, {**REVIEW, "blocks": []}, environment, RULES)["blocks"] == []
