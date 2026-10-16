"""
The runner: setup guards, the dry run, and the real run on the synthetic sessions, with a review file, the fault each check catches and --only.
"""

import json
import re
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest

import process_lab_data.__main__ as entry
from axis_of_travel_rnn import trajectory
from process_lab_data import frame, select

from .conftest import CIRCLE_FRAMES, CIRCLE_PX, FRAMES, RATE_HZ, S1, S6, STAMP, frames_table

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

# The fixture's blocks: S1's arena and track blocks and S6's track block, the files a full run writes, and the csv's
# columns. S1's track block holds the back light loss of 2 s over BACK_LOST and the runs over RUN_SPANS.
S1_ARENA, S1_TRACK, S6_TRACK = f"{S1}_arena_01", f"{S1}_track_01", f"{S6}_track_01"
FILES = {f"arena/blocks/{S1_ARENA}.parquet", f"track/blocks/{S1_TRACK}.parquet", f"track/blocks/{S6_TRACK}.parquet",
         "arena/blocks.csv", "track/blocks.csv", "manifest.json"}
CSV_COLUMNS = ["block_id", "session_id", "subject_id", "date", "protocol", "environment", "epoch", "frame_start", "frame_end",
               "n_frames", "duration_s", "n_runs", "n_clean_runs", "n_trips", "n_complete_trips", "heading_lost_s",
               "heading_filled_s", "heading_held_s", "status", "reviewed_by", "scale_px_per_m", "rotation_rad", "led_offset_rad",
               "kinematics_version"]
BACK_LOST = FRAMES[S1]["back_lost"][0]
RUN_SPANS = {1: (2200, 2300), 2: (2400, 2500), 3: (2600, 2700)}

# A review of S1 saved under a JUMP_PX that is not today's: the arena block dropped, the track block cut down to
# EDITED_RANGE and the return run flagged.
EDITED_RANGE = (2200, 3000)
REVIEW = {
    "session_id": S1, "reviewed_by": "kyle", "reviewed_at": "2026-10-15T09:00:00+00:00", "converter_manifest_timestamp": STAMP,
    "rules": {"GAP_LIGHTS": "both", "JUMP_PX": 30.0, "PAUSE_MARGIN_SEC": 5.0, "MIN_BLOCK_S": 10.0, "HEADING_FILL_SEC": 3.0,
              "RUNNING_FLOOR_M_PER_S": 0.03},
    "blocks": [{"block_id": S1_ARENA, "epoch": "arena", "environment": "open_arena", "frame_start": 301, "frame_end": 1500,
                "status": "dropped", "note": "a pot, not the arena"},
               {"block_id": S1_TRACK, "epoch": "track", "environment": "triple_t", "frame_start": EDITED_RANGE[0],
                "frame_end": EDITED_RANGE[1], "status": "edited", "note": ""}],
    "cuts": [], "flagged_runs": [2], "notes": "", "edits": [],
}

# A review of S6 whose four blocks each plant one fault for the checks: 02 spans the pause at 2701 (t_steps), 03 starts
# before the track epoch's first frame 1801 (inside_epoch), 01 and 04 share frames 3601 to 4200 (one_block).
FAULTY = {f"{S6}_track_01": (3001, 4200, "one_block"), f"{S6}_track_02": (2401, 3000, "t_steps"),
          f"{S6}_track_03": (1501, 2100, "inside_epoch"), f"{S6}_track_04": (3601, 4500, "one_block")}

# A session for block_columns alone: a circle whose rat holds still over STILL (0-based frames) with the back light
# lost over HELD inside it, longer than HEADING_FILL_SEC, so the heading is held there although the mashup steps from
# the midpoint to the front LED at the loss and back at its end, as the converter's mashup does (tables.md 2.4).
N_STILL, STILL, HELD = 1200, (600, 900), (610, 890)
PARAMETERS = {"led_offset_rad": 0.0, "track": {"scale_px_per_m": 400.0, "flip": True, "rotation_rad": 0.0, "offset_m": [0.0, 0.0]}}


def read_csv(root, kind):
    """
    The kind's blocks csv as a list of row dicts.
    """
    return pacsv.read_csv(root / kind / "blocks.csv").to_pylist()


def read_block(root, kind, block_id):
    """
    A block parquet as the table and a dict of numpy arrays.
    """
    table = pq.read_table(root / kind / "blocks" / f"{block_id}.parquet")
    return table, {name: table.column(name).to_numpy() for name in table.column_names}


def manifest(root):
    """
    The manifest as a dict.
    """
    return json.loads((root / "manifest.json").read_text())


def written_bytes(root):
    """
    Every parquet and csv file under the root by relative path with its bytes.
    """
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.suffix in (".parquet", ".csv")}


def still_frames():
    """
    The still session as the frames dict block_columns reads, with its epoch list: the heading along the tangent, lost over HELD, the position still over STILL, the mashup on the front LED while the back is lost.
    """
    moving = np.ones(N_STILL, bool)
    moving[STILL[0]:STILL[1]] = False
    angle = 2 * np.pi * np.cumsum(moving) / CIRCLE_FRAMES
    x, y = 300.0 + CIRCLE_PX * np.cos(angle), 200.0 + CIRCLE_PX * np.sin(angle)
    head_dir = frame.wrapped(angle + np.pi / 2)
    head_dir[HELD[0]:HELD[1]] = np.nan
    lost, none = np.isnan(head_dir), np.zeros(N_STILL, bool)
    frames = {"frame": np.arange(1, N_STILL + 1), "t": np.arange(N_STILL) / RATE_HZ, "front_x": x + 5, "front_y": y,
              "back_x": np.where(lost, np.nan, x - 5), "back_y": np.where(lost, np.nan, y), "head_dir": head_dir,
              "filled_front": none, "filled_back": none, "unfilled_front": none, "unfilled_back": lost,
              "mashup_x": np.where(lost, x + 5, x), "mashup_y": y, "epoch": np.full(N_STILL, "track", object)}
    return frames, [{"epoch": "track", "frame_start": 1, "frame_end": N_STILL}]


@pytest.mark.parametrize("source, out, problem", GUARDS)
def test_a_bad_setup_exits_2_naming_the_problem(tmp_path, transformed, monkeypatch, capsys, source, out, problem):
    (tmp_path / "empty").mkdir()
    monkeypatch.setattr(entry, "repo_root", lambda: tmp_path / "repo")
    pairs = zip(("TRANSFORMED_LAB_DATA", "PROCESSED_LAB_DATA"), (source, out))
    with pytest.raises(SystemExit) as stop:
        entry.main(["--dry-run"], config={key: str(tmp_path / value) for key, value in pairs if value is not None})
    assert stop.value.code == 2
    assert problem in capsys.readouterr().err


def test_a_dry_run_prints_the_funnel_the_blocks_and_the_review_count_and_writes_nothing(config, transformed, capsys):
    before = sorted(transformed.rglob("*"))
    assert entry.main(["--dry-run", "--list"], config=config) == 0
    out = capsys.readouterr().out
    assert "sessions, all sessions: 6" in out and "epochs, condition baseline: 3" in out
    assert "blocks, cut at pauses, gaps and jumps: 4" in out and "blocks, after margins: 4" in out
    assert "blocks, at least 10 s: 3" in out and "jump frames, in the epochs: 0" in out
    assert "seconds trimmed by margins: 40.0" in out
    assert "  arena: 1 blocks, 20 s, durations 20, 20, 20, 20" in out
    assert f"  {S1_TRACK}  1200 frames  20.0 s" in out and f"  {S6_TRACK}  1200 frames  20.0 s" in out
    assert "sessions with a review file: 0 of 2" in out
    assert "track/blocks.csv" in out and "manifest.json" in out
    assert not Path(config["PROCESSED_LAB_DATA"]).exists()
    assert sorted(transformed.rglob("*")) == before


def test_a_dry_run_with_frames_prints_the_frame_parameters_per_session_and_the_medians_per_rat_and_writes_nothing(config, transformed, capsys):
    before = sorted(transformed.rglob("*"))
    assert entry.main(["--dry-run", "--frames"], config=config) == 0
    lines = capsys.readouterr().out.splitlines()
    s1, s6 = (next(line for line in lines if line.startswith(f"  {s}  ")) for s in (S1, S6))
    assert re.search(r"NS14  arena \d+ px/m \(extent \d+\.\d\d, LEDs \d+\.\d cm\)  track \d+ px/m \(x \d+, y \d+, LEDs \d+\.\d cm\)", s1)
    assert re.search(r"NS16  track \d+ px/m \(x \d+, y \d+, LEDs \d+\.\d cm\)  rotation ", s6) and "arena" not in s6
    assert all("rotation " in line and "offset " in line and "n " in line for line in (s1, s6))
    warned = [line.split()[1] for line in lines if "track scale x and y differ by" in line and "an outer corridor peak missed?" in line]
    assert warned == [S1, S6]
    medians = lines[lines.index("median LED offset and LED separation per rat:") + 1:]
    assert [line.split()[0] for line in medians] == ["NS14", "NS16"] and all(re.search(r" deg  \d+\.\d cm$", line) for line in medians)
    assert not Path(config["PROCESSED_LAB_DATA"]).exists() and sorted(transformed.rglob("*")) == before


def test_a_full_run_writes_the_layout_the_csv_rows_and_the_manifest_and_a_rerun_is_identical(config, capsys):
    root = Path(config["PROCESSED_LAB_DATA"])
    assert entry.main([], config=config) == 0
    out = capsys.readouterr().out
    assert f"{S1}  2 blocks written, 0 failed, unreviewed, 1 warnings" in out and f"{S6}  1 blocks written, 0 failed, unreviewed" in out
    assert "3 blocks written, 0 failed, 0 of 2 sessions reviewed" in out and "blocks, written: 3" in out
    assert {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} == FILES
    track, arena = read_csv(root, "track"), read_csv(root, "arena")
    assert list(track[0]) == CSV_COLUMNS and [row["block_id"] for row in track] == [S1_TRACK, S6_TRACK] and [row["block_id"] for row in arena] == [S1_ARENA]
    s1 = track[0]
    assert (s1["subject_id"], str(s1["date"]), s1["protocol"], s1["environment"], s1["epoch"]) == ("NS14", "2015-01-01", "standard", "triple_t", "track")
    assert (s1["frame_start"], s1["frame_end"], s1["n_frames"], s1["duration_s"]) == (2101, 3300, 1200, 20.0)
    assert (s1["n_runs"], s1["n_clean_runs"], s1["n_trips"], s1["n_complete_trips"]) == (3, 2, 3, 1)
    assert (s1["heading_lost_s"], s1["heading_filled_s"], s1["heading_held_s"]) == (0.0, 2.0, 0.0)
    assert (s1["status"], s1["reviewed_by"], s1["kinematics_version"]) == ("automatic", None, trajectory.KINEMATICS_VERSION)
    assert (arena[0]["n_runs"], arena[0]["n_trips"], arena[0]["environment"]) == (0, 0, "open_arena")
    assert arena[0]["scale_px_per_m"] == pytest.approx(s1["scale_px_per_m"] * frame.PARALLAX_RATIO)
    m = manifest(root)
    assert set(m["run"]) == {"timestamp", "converter_manifest_timestamp", "rules", "funnel", "only", "confirmed_only", "written", "failed", "warnings"}
    assert m["run"]["converter_manifest_timestamp"] == STAMP and m["run"]["only"] is None and m["run"]["failed"] == {}
    assert m["run"]["written"] == [S1_ARENA, S1_TRACK, S6_TRACK] and m["run"]["funnel"]["blocks, written"] == 3
    assert set(m["run"]["rules"]) == {"select", "frame", "labels", "trajectory", "checks"}
    assert m["run"]["rules"]["select"]["JUMP_PX"] == select.JUMP_PX and m["run"]["rules"]["trajectory"]["KINEMATICS_VERSION"] == 1
    assert len(m["run"]["warnings"]) == 2 and all("track scale x and y differ" in w for w in m["run"]["warnings"])
    assert list(m["sessions"]) == [S1, S6]
    s1_entry = m["sessions"][S1]
    assert set(s1_entry) == {"frame_parameters", "checks", "reviewed", "reviewed_by", "reviewed_at", "review_rules", "rules_differ",
                             "blocks_written", "blocks_failed", "blocks_dropped_by_review"}
    assert s1_entry["reviewed"] is False and s1_entry["blocks_written"] == [S1_ARENA, S1_TRACK] and s1_entry["blocks_dropped_by_review"] == []
    assert s1_entry["checks"]["scale_axes"]["status"] == "warn" and s1_entry["checks"]["led_separation"]["status"] == "pass"
    assert s1_entry["frame_parameters"]["track"]["scale_px_per_m"] == s1["scale_px_per_m"]
    before = written_bytes(root)
    assert entry.main([], config=config) == 0
    assert written_bytes(root) == before
    again = manifest(root)
    del again["run"]["timestamp"], m["run"]["timestamp"]
    assert again == m


def test_a_block_parquet_holds_the_lab_frame_then_exactly_the_schema_with_t_from_zero_and_no_turn_rate_on_filled_frames(config):
    root = Path(config["PROCESSED_LAB_DATA"])
    assert entry.main([], config=config) == 0
    table, d = read_block(root, "track", S1_TRACK)
    assert table.column_names == ["frame"] + list(trajectory.COLUMNS)
    assert table.schema.field("frame").type == pa.int32()
    assert [str(table.schema.field(name).type) for name in trajectory.COLUMNS] == [
        {"U8": "string", "float64": "double"}.get(dtype, dtype) for dtype in trajectory.COLUMNS.values()]
    assert d["frame"][0] == 2101 and d["frame"][-1] == 3300 and d["t"][0] == 0.0
    assert np.allclose(np.diff(d["t"]), 1 / RATE_HZ, atol=1e-6) and np.isfinite(d["x"]).all() and np.isfinite(d["y"]).all()
    lost = (d["frame"] >= BACK_LOST[0]) & (d["frame"] <= BACK_LOST[1])
    assert np.array_equal(d["heading_filled"], lost) and not d["heading_held"].any() and np.isfinite(d["heading"]).all()
    assert np.array_equal(np.isnan(d["turn_rate"]), lost) and np.array_equal(d["n_lights"], np.where(lost, 1, 2))
    assert np.isfinite(d["speed"]).all() and (d["speed"] > 0).all()
    for number, (first, last) in RUN_SPANS.items():
        assert np.array_equal(d["run"] == number, (d["frame"] >= first) & (d["frame"] <= last))
    assert set(np.unique(d["phase"][d["run"] == 2])) == {"return"} and set(np.unique(d["phase"][d["run"] == 0])) == {"dwell"}
    assert np.array_equal(np.unique(d["trip"][d["frame"] < 2200]), [-1]) and np.array_equal(np.unique(d["trip"][(d["frame"] >= 2200) & (d["frame"] < 2600)]), [2])
    assert np.array_equal(np.unique(d["trip"][d["frame"] >= 2600]), [-3]) and d["clean"][d["run"] == 2].sum() == 0 and d["clean"][d["run"] == 1].all()
    _, arena = read_block(root, "arena", S1_ARENA)
    assert set(np.unique(arena["phase"])) == {"forage"} and not arena["trip"].any()


def test_a_held_heading_gives_no_turn_rate_while_the_measured_heading_around_it_does():
    frames, epochs = still_frames()
    filled, kind = select.fill_heading(frames["head_dir"], frames["t"], frame.still(frames, epochs), RATE_HZ)
    columns = entry.block_columns(frames, slice(0, N_STILL), PARAMETERS, "track", filled, kind, [], RATE_HZ)
    held = np.zeros(N_STILL, bool)
    held[HELD[0]:HELD[1]] = True
    assert np.array_equal(columns["heading_held"], held) and not columns["heading_filled"].any()
    assert np.isnan(columns["turn_rate"][held]).all() and np.isfinite(columns["turn_rate"][~held]).all()
    assert (columns["heading"][held] == columns["heading"][HELD[0] - 1]).all() and np.isfinite(columns["heading"]).all()
    assert np.abs(columns["speed"][HELD[0] + 5:HELD[1] - 5]).max() < 1e-9 and columns["speed"][:STILL[0] - 5].min() > 0.1
    assert np.array_equal(columns["n_lights"], np.where(held, 1, 2)) and columns["t"][0] == 0.0


def test_a_review_file_drops_a_block_builds_an_edited_range_clears_a_flagged_run_and_is_recorded(config, capsys):
    root = Path(config["PROCESSED_LAB_DATA"])
    assert entry.main([], config=config) == 0 and (root / "arena" / "blocks" / f"{S1_ARENA}.parquet").is_file()
    (root / "review").mkdir()
    (root / "review" / f"{S1}.json").write_text(json.dumps(REVIEW))
    assert entry.main([], config=config) == 0
    out = capsys.readouterr().out
    assert f"{S1}  1 blocks written, 0 failed, reviewed by kyle 2026-10-15T09:00:00+00:00, 2 warnings" in out
    assert "1 of 2 sessions reviewed" in out
    assert not (root / "arena" / "blocks").exists() and read_csv(root, "arena") == [] and (root / "review" / f"{S1}.json").is_file()
    track = read_csv(root, "track")
    assert [(row["block_id"], row["frame_start"], row["frame_end"], row["status"], row["reviewed_by"] or None) for row in track] == [
        (S1_TRACK, EDITED_RANGE[0], EDITED_RANGE[1], "edited", "kyle"), (S6_TRACK, 3001, 4200, "automatic", None)]
    assert (track[0]["n_runs"], track[0]["n_clean_runs"], track[0]["n_trips"], track[0]["n_complete_trips"]) == (2, 2, 2, 0)
    _, d = read_block(root, "track", S1_TRACK)
    assert d["frame"][0] == EDITED_RANGE[0] and d["frame"][-1] == EDITED_RANGE[1] and d["t"][0] == 0.0
    flagged = (d["frame"] >= RUN_SPANS[2][0]) & (d["frame"] <= RUN_SPANS[2][1])
    assert not d["run"][flagged].any() and not d["path_id"][flagged].any() and not d["clean"][flagged].any()
    assert set(np.unique(d["phase"][flagged])) == {"dwell"} and set(np.unique(d["run"])) == {0, 1, 3}
    assert np.array_equal(np.unique(d["trip"]), [-2, -1])
    m = manifest(root)
    s1, s6 = m["sessions"][S1], m["sessions"][S6]
    assert (s1["reviewed"], s1["reviewed_by"], s1["reviewed_at"]) == (True, "kyle", "2026-10-15T09:00:00+00:00")
    assert s1["review_rules"] == REVIEW["rules"] and s1["rules_differ"] is True
    assert s1["blocks_written"] == [S1_TRACK] and s1["blocks_dropped_by_review"] == [S1_ARENA]
    assert (s6["reviewed"], s6["reviewed_by"], s6["review_rules"], s6["rules_differ"]) == (False, None, None, False)
    assert f"{S1} reviewed under other rules: JUMP_PX 30.0 now 40.0" in m["run"]["warnings"]
    assert m["run"]["written"] == [S1_TRACK, S6_TRACK]


def test_a_nan_position_inside_a_block_fails_it_and_the_run_exits_1_with_the_other_blocks_written(config, transformed, capsys):
    root = Path(config["PROCESSED_LAB_DATA"])
    table = frames_table(S1, **FRAMES[S1])
    x = table.column("mashup_x").to_numpy().copy()
    x[2499] = np.nan
    pq.write_table(table.set_column(table.column_names.index("mashup_x"), "mashup_x", pa.array(x)), transformed / "frames" / f"{S1}.parquet")
    assert entry.main([], config=config) == 1
    out = capsys.readouterr().out
    assert f"{S1}  1 blocks written, 1 failed" in out and f"  failed: {S1_TRACK} (position_finite)" in out and "2 blocks written, 1 failed" in out
    assert {str(p.relative_to(root)) for p in root.rglob("*.parquet")} == {f"arena/blocks/{S1_ARENA}.parquet", f"track/blocks/{S6_TRACK}.parquet"}
    assert [row["block_id"] for row in read_csv(root, "track")] == [S6_TRACK]
    m = manifest(root)
    assert m["run"]["failed"] == {S1_TRACK: {"position_finite": {"status": "fail", "detail": {"nan_frames": 1}}}}
    assert m["run"]["written"] == [S1_ARENA, S6_TRACK] and m["run"]["funnel"]["blocks, failed"] == 1
    assert m["sessions"][S1]["blocks_failed"] == [S1_TRACK] and m["sessions"][S1]["blocks_written"] == [S1_ARENA]


def test_each_block_check_fails_the_block_it_catches_which_is_not_written_and_the_run_exits_1(config, capsys):
    root = Path(config["PROCESSED_LAB_DATA"])
    (root / "review").mkdir(parents=True)
    blocks = [{"block_id": block_id, "epoch": "track", "environment": "triple_t", "frame_start": first, "frame_end": last,
               "status": "confirmed", "note": ""} for block_id, (first, last, _) in FAULTY.items()]
    (root / "review" / f"{S6}.json").write_text(json.dumps({**REVIEW, "session_id": S6, "blocks": blocks, "flagged_runs": []}))
    assert entry.main([], config=config) == 1
    assert f"{S6}  0 blocks written, 4 failed" in capsys.readouterr().out
    assert {p.name for p in root.rglob("*.parquet")} == {f"{S1_ARENA}.parquet", f"{S1_TRACK}.parquet"}
    assert [row["block_id"] for row in read_csv(root, "track")] == [S1_TRACK]
    failed = manifest(root)["run"]["failed"]
    assert {block_id: list(checks) for block_id, checks in failed.items()} == {block_id: [check] for block_id, (_, _, check) in FAULTY.items()}
    assert failed[f"{S6}_track_02"]["t_steps"]["detail"] == {"bad_steps": 1}
    assert failed[f"{S6}_track_03"]["inside_epoch"]["detail"] == {"epoch": [1801, 4500]}
    assert failed[f"{S6}_track_01"]["one_block"]["detail"] == {"overlapping": [f"{S6}_track_04"]}
    assert manifest(root)["sessions"][S6]["blocks_failed"] == sorted(FAULTY) and manifest(root)["sessions"][S6]["blocks_written"] == []


def test_run_label_mismatches_names_a_run_painted_off_its_range_and_a_label_no_run_has():
    frame = np.arange(100, 120)
    runs = [{"run": 1, "frame_start": 100, "frame_end": 104}, {"run": 2, "frame_start": 104, "frame_end": 110}]
    run = np.where(frame <= 103, 1, np.where(frame <= 110, 2, 0))
    assert entry.run_label_mismatches(frame, run, runs) == []
    run[0], run[15] = 0, 7
    assert entry.run_label_mismatches(frame, run, runs) == [1, 7]


def test_a_led_separation_outside_the_implants_range_warns_in_the_manifest_without_failing_the_run(config, transformed):
    table = frames_table(S6, **FRAMES[S6])
    back_x = table.column("back_x").to_numpy() - 20.0
    pq.write_table(table.set_column(table.column_names.index("back_x"), "back_x", pa.array(back_x)), transformed / "frames" / f"{S6}.parquet")
    assert entry.main([], config=config) == 0
    m = manifest(Path(config["PROCESSED_LAB_DATA"]))
    check = m["sessions"][S6]["checks"]["led_separation"]
    assert check["status"] == "warn" and check["detail"]["led_separation_m"]["track"] > entry.LED_SEPARATION_M[1]
    assert m["sessions"][S1]["checks"]["led_separation"]["status"] == "pass"
    assert any(re.fullmatch(rf"{S6} track LED separation \d+\.\d cm outside 4 to 8", w) for w in m["run"]["warnings"])


def test_only_writes_one_session_and_the_csv_files_hold_only_it_after_a_full_run_too(config):
    root = Path(config["PROCESSED_LAB_DATA"])
    assert entry.main([], config=config) == 0 and len(list(root.rglob("*.parquet"))) == 3
    assert entry.main(["--only", "NS16"], config=config) == 0
    assert {str(p.relative_to(root)) for p in root.rglob("*.parquet")} == {f"track/blocks/{S6_TRACK}.parquet"}
    assert [row["block_id"] for row in read_csv(root, "track")] == [S6_TRACK] and read_csv(root, "arena") == []
    m = manifest(root)
    assert list(m["sessions"]) == [S6] and m["run"]["only"] == "NS16" and m["run"]["written"] == [S6_TRACK]
    assert m["run"]["funnel"]["sessions, --only"] == 1


def test_a_dry_run_report_writes_the_whole_report_to_the_file_and_nothing_else(config, transformed, tmp_path, capsys):
    report = tmp_path / "report.txt"
    assert entry.main(["--dry-run", "--report", str(report)], config=config) == 0
    text = report.read_text()
    assert "funnel:" in text and "unreviewed, the automatic blocks are written" in text
    assert "frame parameters" in text and f"{S1}_track_01" in text
    assert text in capsys.readouterr().out
    assert not Path(config["PROCESSED_LAB_DATA"]).exists()


def test_confirmed_only_writes_the_reviewed_sessions_kept_blocks_and_nothing_from_unreviewed_ones(config, capsys):
    root = Path(config["PROCESSED_LAB_DATA"])
    assert entry.main(["--confirmed-only"], config=config) == 0
    assert not list(root.glob("*/blocks/*.parquet"))
    (root / "review").mkdir()
    (root / "review" / f"{S1}.json").write_text(json.dumps(REVIEW))
    assert entry.main(["--confirmed-only"], config=config) == 0
    written = sorted(p.stem for p in root.glob("*/blocks/*.parquet"))
    assert written and all(b.startswith(S1) for b in written)
    kept = sorted(b["block_id"] for b in REVIEW["blocks"] if b["status"] in entry.KEPT_STATUSES)
    assert written == kept
    assert json.loads((root / "manifest.json").read_text())["run"]["confirmed_only"] is True


def test_a_review_file_for_a_session_outside_the_funnel_is_named_in_the_warnings(config, capsys):
    root = Path(config["PROCESSED_LAB_DATA"])
    (root / "review").mkdir(parents=True)
    (root / "review" / "JL1_rec99_20150101_001.json").write_text(json.dumps({**REVIEW, "session_id": "JL1_rec99_20150101_001"}))
    assert entry.main([], config=config) == 0
    assert "review file for JL1_rec99_20150101_001 ignored, the session is outside the funnel" in capsys.readouterr().out
