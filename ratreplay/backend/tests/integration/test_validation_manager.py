"""
ValidationManager over the real engine and accesses on the synthetic folders, the blocks built by ReviewManager: the health of the folders, readiness at settings under the rules each session was built with, a block for the player and its windows, and the selection of the settings.
"""

import getpass
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from fixtures import S1, S6

import ratreplay_api.managers.validation as validation_module
from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.processed import BLOCKS_CSV_SCHEMA, WINDOWS_KEYS, ProcessedAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.trajectory import RULES, SETTINGS, TrajectoryEngine
from ratreplay_api.managers.review import ReviewManager
from ratreplay_api.managers.validation import ARRAY_COLUMNS, NOTHING_BUILT, SYNTHETIC_LATER, ValidationManager, spans_of
from ratreplay_api.utilities.errors import Invalid, NotFound

REAL = Path(__file__).resolve().parents[4] / "configs" / "environments"
FROZEN = "2026-10-18T10:00:00+00:00"
COMMIT = "abc1234"
CONFIG = "/somewhere/local.yaml"

# S1 is built at a window of 5 s and S6 at 10 s, so each session shows the settings its own build used. The 10 to 30 s blocks of
# the fixtures yield windows at 5 s, the defaults of 40 s yield none. S1's track block holds a trip whose return path is 9.
SHORT = {**SETTINGS, "window_s": 5.0}
LONGER = {**SETTINGS, "window_s": 10.0}
ACCEPT = [{"op": "accept"}]
ARENA, TRACK, OTHER = f"{S1}_arena_01", f"{S1}_track_01", f"{S6}_track_01"

# The four environment files, and the registration keys a row holds that the build recorded per epoch kind and for the session.
YAML_ENVIRONMENTS = ["open_arena", "plus_maze", "triple_t", "triple_t_rot90"]
PER_KIND = ("scale_px_per_m", "led_separation_m", "rotation_rad", "flip", "offset_m")
PER_SESSION = ("led_offset_rad", "led_offset_r", "led_offset_n")


class Recording(TrajectoryEngine):
    """
    The engine, noting the return paths of the rules each windows call is made under.
    """

    def __init__(self):
        self.return_paths = []

    def windows(self, block, settings, rules):
        """
        The windows as the engine finds them.
        """
        self.return_paths.append(rules["return_paths"])
        return super().windows(block, settings, rules)


def review_over(folders):
    """
    A ReviewManager on the folders.
    """
    transformed, processed, environments = folders
    return ReviewManager(TrajectoryEngine(), TransformedAccess(transformed), ProcessedAccess(processed), EnvironmentAccess(environments), COMMIT)


def trips_in_first_window(folders):
    """
    The complete and partial trips the first window of S1's track block holds at the short settings.
    """
    row = manager_over(folders).windows(TRACK, SHORT)["rows"][0]
    return row["trips_complete"], row["trips_partial"]


def manager_over(folders, trajectory=None):
    """
    A ValidationManager on the folders.
    """
    transformed, processed, environments = folders
    return ValidationManager(trajectory or TrajectoryEngine(), TransformedAccess(transformed), ProcessedAccess(processed), EnvironmentAccess(environments))


@pytest.fixture
def folders(tmp_path, transformed):
    """
    The transformed folder, a processed folder not made yet and a copy of the environment yaml files.
    """
    shutil.copytree(REAL, tmp_path / "environments")
    return transformed, tmp_path / "processed", tmp_path / "environments"


@pytest.fixture
def built(folders):
    """
    The folders with the processed one built by ReviewManager from two sessions.
    """
    review = review_over(folders)
    review.save_blocks(S1, ACCEPT, "", SHORT)
    review.save_blocks(S6, ACCEPT, "", LONGER)
    return folders


@pytest.fixture
def manager(built):
    """
    A ValidationManager over the built folders.
    """
    return manager_over(built)


def snapshot(root):
    """
    Every file under the root by relative path with its bytes.
    """
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_health_of_the_three_folders_is_ok_with_their_counts_and_the_config_file(manager):
    health = manager.health(CONFIG)
    assert set(health) == {"transformed", "processed", "environments", "config_path"} and health["config_path"] == CONFIG
    assert [health[name]["problems"] for name in ("transformed", "processed", "environments")] == [[], [], []]
    assert health["transformed"]["counts"] == {"sessions": 6, "epochs": 13, "runs": 6, "frames": 2}
    assert health["processed"]["counts"] == {"reviews": 2, "blocks": 3, "sessions": 2}
    assert health["environments"]["counts"] == {"environments": len(list(REAL.glob("*.yaml")))}
    json.dumps(health)


def test_a_broken_processed_folder_names_the_problem_and_leaves_the_others_ok(built, manager):
    next((built[1] / "blocks").glob("*.parquet")).unlink()
    health = manager.health(CONFIG)
    assert len(health["processed"]["problems"]) == 1 and health["processed"]["problems"][0].startswith("1 block files missing")
    assert health["transformed"]["problems"] == [] and health["environments"]["problems"] == []


def test_environments_list_every_yaml_with_the_registration_each_built_session_was_given(built, manager):
    found = manager.environments()
    by_name = {e["name"]: e for e in found}
    assert [e["name"] for e in found] == YAML_ENVIRONMENTS and all(e.keys() == {"name", "kind", "params", "geometry", "sessions", "summary"} for e in found)
    access = EnvironmentAccess(built[2])
    assert all(e["geometry"] == access.environment(e["name"]) and (e["kind"], e["params"]) == (e["geometry"]["kind"], e["geometry"]["params"]) for e in found)
    assert by_name["open_arena"]["params"]["diameter"] == 0.6 and by_name["triple_t_rot90"]["params"]["rotated_deg"] == 90
    metadata = {sid: ProcessedAccess(built[1]).metadata(sid) for sid in (S1, S6)}
    # S1 is registered on its arena and its track, S6 on its track alone (its arena is of another condition), and the rest of the files are used by none.
    assert [(r["session_id"], r["kind"]) for r in by_name["triple_t"]["sessions"]] == [(S1, "track"), (S6, "track")]
    assert [(r["session_id"], r["kind"]) for r in by_name["open_arena"]["sessions"]] == [(S1, "arena")]
    assert by_name["plus_maze"]["sessions"] == by_name["triple_t_rot90"]["sessions"] == []
    for environment in found:
        for row in environment["sessions"]:
            made, frame = metadata[row["session_id"]], metadata[row["session_id"]]["frame"]
            expected = {**{key: frame[row["kind"]][key] for key in PER_KIND}, **{key: frame[key] for key in PER_SESSION},
                        "warnings": made["warnings"], "built_at": made["built_at"]}
            axes = {"scale_x": frame["track"]["scale_x_px_per_m"], "scale_y": frame["track"]["scale_y_px_per_m"]} if row["kind"] == "track" else {}
            assert row == {"session_id": row["session_id"], "kind": row["kind"], **expected, **axes}
    assert all(e["summary"] == {"n_sessions": len(e["sessions"]), "n_warned": sum(bool(r["warnings"]) for r in e["sessions"])} for e in found)
    json.dumps(found)


def test_an_excluded_session_has_no_registration_to_show_and_nothing_is_written(built, manager):
    review = review_over(built)
    review.exclude(S1, True, "camera moved", SHORT)
    review.rebuild_all(SHORT)
    before = snapshot(built[1])
    by_name = {e["name"]: e for e in manager.environments()}
    assert [r["session_id"] for r in by_name["triple_t"]["sessions"]] == [S6] and by_name["open_arena"]["sessions"] == []
    assert by_name["triple_t"]["summary"]["n_sessions"] == 1 and snapshot(built[1]) == before


def test_readiness_gives_a_row_per_block_with_count_and_verdict_the_totals_and_the_settings_each_session_was_built_with(manager):
    done = manager.readiness("real", SHORT)
    rows = done["blocks"]
    assert set(done) == {"which", "settings", "blocks", "totals", "built"} and done["settings"] == SHORT
    assert [b["block_id"] for b in rows] == [ARENA, TRACK, OTHER] and all(set(b) == {*BLOCKS_CSV_SCHEMA.names, "count", "verdict"} for b in rows)
    assert all(set(b["verdict"]) == {"ok", "reasons"} and b["verdict"]["ok"] == (not b["verdict"]["reasons"]) for b in rows)
    ok = [b for b in rows if b["verdict"]["ok"]]
    # At 5 s every block yields windows and the track block of S6 holds no complete trip, so the windows of all blocks exceed those of the ok ones.
    assert 0 < len(ok) < 3 and done["totals"]["windows"] > done["totals"]["windows_ok"] > 0
    assert done["totals"] == {"blocks": 3, "ok": len(ok), "trouble": 3 - len(ok), "windows": sum(b["count"] for b in rows), "windows_ok": sum(b["count"] for b in ok)}
    assert {sid: b["settings"] for sid, b in done["built"].items()} == {S1: SHORT, S6: LONGER} and all(b["built_at"] for b in done["built"].values())
    assert manager.readiness("real", SETTINGS)["totals"]["windows"] == 0
    json.dumps(done)


def test_a_session_whose_blocks_were_all_dropped_still_shows_the_settings_of_its_build(built, manager):
    review_over(built).save_blocks(S6, [{"op": "drop", "frame": 3500}], "", SHORT)
    done = manager.readiness("real", SHORT)
    assert {b["session_id"] for b in done["blocks"]} == {S1} and {sid: b["settings"] for sid, b in done["built"].items()} == {S1: SHORT, S6: SHORT}


def test_blocks_are_judged_under_the_rules_their_session_was_built_with_not_todays(built):
    path = built[1] / "metadata" / f"{S1}.json"
    metadata = json.loads(path.read_text())
    assert metadata["rules"]["return_paths"] == list(RULES["return_paths"])
    before = trips_in_first_window(built)
    # With the outbound path 1 counted as a return path the second trip ends with its outbound run, so it lies whole inside the first window.
    path.write_text(json.dumps({**metadata, "rules": {**metadata["rules"], "return_paths": [1, 9]}}))
    assert (before, trips_in_first_window(built)) == ((0, 2), (1, 1))
    engine = Recording()
    manager_over(built, engine).readiness("real", SHORT)
    assert engine.return_paths == [[1, 9], [1, 9], list(RULES["return_paths"])]


def test_a_block_comes_with_its_row_geometry_and_spans_as_indices_and_its_arrays_in_metres(built, manager):
    assert spans_of([0, 0, 1, 1, 1, 0, 2, 2]) == [(0, 0, 1), (1, 2, 4), (0, 5, 5), (2, 6, 7)]
    track, arena = manager.block(TRACK), manager.block(ARENA)
    n, arrays = track["row"]["n_frames"], manager.arrays(TRACK)
    assert track["row"] == next(row for row in ProcessedAccess(built[1]).blocks() if row["block_id"] == TRACK)
    assert track["rate_hz"] == track["row"]["rate_hz"] == arena["rate_hz"] == 60 and track["rate_hz"] == round(1 / (arrays["t"][1] - arrays["t"][0]))
    assert track["geometry"]["name"] == track["row"]["environment"] and track["geometry"]["walls"] and arena["geometry"]["circle"]["radius"] > 0
    spans = [*track["runs"], *track["trips"], *track["phases"]]
    assert spans and all(0 <= s["first"] <= s["last"] < n for s in spans) and (track["phases"][0]["first"], track["phases"][-1]["last"]) == (0, n - 1)
    one_light = track["one_light"]
    assert one_light and sum(last - first + 1 for first, last in one_light) == (arrays["n_lights"] == 1).sum()
    assert all((arrays["n_lights"][first:last + 1] == 1).all() for first, last in one_light)
    assert tuple(arrays) == ARRAY_COLUMNS and all(len(values) == n for values in arrays.values())
    assert arrays["frame"][0] == track["row"]["frame_start"] and 0 < np.nanmax(np.abs(arrays["x"])) < 3
    json.dumps(track)
    with pytest.raises(NotFound):
        manager.block("nothing")


def test_windows_of_a_block_are_its_rows_with_checks_and_agree_with_readiness(manager):
    found = manager.windows(TRACK, SHORT)
    assert set(found) == {"rows", "verdict", "count"} and found["count"] == len(found["rows"]) > 0
    assert all({"first", "stop", "ok", "reason", "trips_complete", "trips_partial"} <= set(w) for w in found["rows"])
    ready = next(b for b in manager.readiness("real", SHORT)["blocks"] if b["block_id"] == TRACK)
    assert (found["count"], found["verdict"]) == (ready["count"], ready["verdict"])
    json.dumps(found)


def test_selecting_the_settings_writes_windows_json_whole_with_the_totals_and_a_second_call_replaces_it(built, manager, monkeypatch):
    monkeypatch.setattr(validation_module.clock, "iso_now", lambda: FROZEN)
    before, access = snapshot(built[1]), ProcessedAccess(built[1])
    assert manager.selected() == {"selected": None}
    assert manager.select_settings(SHORT) == {"replaced": False, "file": "windows.json"}
    expected = {"settings": SHORT, "totals": manager.readiness("real", SHORT)["totals"], "selected_at": FROZEN, "selected_by": getpass.getuser()}
    assert access.window_settings() == expected and set(expected) == set(WINDOWS_KEYS) and manager.selected() == {"selected": expected}
    after = snapshot(built[1])
    assert set(after) - set(before) == {"windows.json"} and all(after[name] == before[name] for name in before)
    assert manager.select_settings(LONGER) == {"replaced": True, "file": "windows.json"} and access.window_settings()["settings"] == LONGER


def test_a_synthetic_set_is_refused_and_so_is_selecting_settings_before_anything_is_built(built, folders, tmp_path, manager):
    before = snapshot(built[1])
    with pytest.raises(Invalid, match=SYNTHETIC_LATER):
        manager.readiness("set:abc", SHORT)
    assert snapshot(built[1]) == before
    fresh = manager_over((folders[0], tmp_path / "fresh", folders[2]))
    with pytest.raises(Invalid, match=NOTHING_BUILT):
        fresh.select_settings(SHORT)
    assert not (tmp_path / "fresh").exists()
