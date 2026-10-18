"""
The API through the test client on the synthetic folders: sources, blocks and the window settings. The sessions and the reviews are ReviewManager's, tested in tests/integration.
"""

import numpy as np
import pyarrow as pa
import yaml

from fixtures import S1, S6, STAMP


def arrays_of(response):
    """
    The columns of an Arrow response as numpy arrays.
    """
    table = pa.ipc.open_stream(response.content).read_all()
    return {name: table[name].to_numpy() for name in table.column_names}


def test_the_sources_are_the_two_folders_of_the_config_with_their_counts_and_manifests(client, tmp_path, transformed, processed):
    sources = client.get("/api/sources").json()
    assert sources["config_path"] == str((tmp_path / "local.yaml").resolve())
    assert sources["transformed"] == {"path": str(transformed.resolve()), "status": "ok", "problems": [], "manifest": sources["transformed"]["manifest"],
                                      "counts": {"sessions": 6, "epochs": 13, "runs": 6, "frames": 2}}
    assert sources["processed"]["status"] == "ok" and sources["processed"]["counts"] == {"blocks": 3, "reviews": 0}
    assert sources["transformed"]["manifest"]["timestamp"] == STAMP and sources["processed"]["manifest"]["timestamp"]


def test_a_key_the_config_lacks_is_named_with_the_file_by_the_sources_and_the_routes_that_need_it(client_on, processed):
    client = client_on({"PROCESSED_LAB_DATA": str(processed)})
    sources = client.get("/api/sources").json()
    problem = f"TRANSFORMED_LAB_DATA is not set in {sources['config_path']}"
    assert (sources["transformed"]["path"], sources["transformed"]["status"], sources["transformed"]["problems"]) == (None, "invalid", [problem])
    assert sources["processed"]["status"] == "ok"
    assert client.get("/api/sessions").json() == {"error": problem}
    assert client.get("/api/blocks").status_code == 200


def test_a_folder_that_is_missing_or_breaks_the_format_is_invalid_and_its_routes_refuse_it(client_on, tmp_path, transformed, processed):
    (transformed / "epochs.csv").unlink()
    next((processed / "track" / "blocks").glob("*.parquet")).unlink()
    config = {"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(processed)}
    sources = client_on(config).get("/api/sources").json()
    assert sources["transformed"]["problems"] == ["missing epochs.csv"] and sources["processed"]["problems"][0].startswith("1 block files missing")
    gone = client_on({**config, "TRANSFORMED_LAB_DATA": str(tmp_path / "nope")})
    problem = f"TRANSFORMED_LAB_DATA {tmp_path / 'nope'} does not exist"
    assert gone.get("/api/sources").json()["transformed"]["problems"] == [problem]
    assert gone.get("/api/sessions").json() == {"error": problem} and gone.get("/api/sessions").status_code == 404


def test_reload_reads_the_config_file_again_and_nothing_else_does(client_on, tmp_path, transformed, processed):
    client = client_on({"TRANSFORMED_LAB_DATA": str(transformed)})
    (tmp_path / "local.yaml").write_text(yaml.safe_dump({"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(processed)}))  # edited while the app runs
    assert client.get("/api/sources").json()["processed"]["path"] is None
    assert client.get("/api/sessions").status_code == 400
    reloaded = client.get("/api/sources", params={"reload": "true"}).json()
    assert reloaded["processed"]["path"] == str(processed.resolve()) and client.get("/api/sessions").status_code == 200


def test_block_verdicts_follow_the_window_settings(client):
    url = f"/api/blocks"
    default = client.get(url).json()
    assert {b["reason"] for b in default["blocks"]} == {"no window fits"} and default["totals"]["overall"]["windows"] == 0
    short = client.get(url, params={"window_s": 5}).json()
    verdicts = {b["block_id"]: (b["ok"], b["n_windows"]) for b in short["blocks"]}
    assert verdicts[f"{S1}_arena_01"] == (True, 2) and verdicts[f"{S6}_track_01"][0] is False
    assert short["totals"]["overall"]["blocks_ok"] == 2 and short["settings"]["window_s"] == 5
    assert client.get(url, params={"window_s": -1}).status_code == 422


def test_a_block_is_served_in_metres_with_its_environment_and_windows(client):
    url = f"/api/blocks"
    track = client.get(f"{url}/{S1}_track_01", params={"window_s": 5}).json()
    assert track["geometry"]["walls"] and "start" in track["geometry"]["reward_sites"] and track["geometry"]["circle"] is None
    assert [r["run"] for r in track["runs"]] == [1, 2, 3] and track["verdict"] == {"ok": True, "reason": None}
    assert track["one_light"] == [[699, 818]]  # the back light lost at lab frames 2800 to 2919, the block starting at 2101
    assert [w["first"] for w in track["windows"]] == [0, 600] and track["windows"][0]["ok"] and not track["windows"][1]["ok"]
    counted = {b["block_id"]: b["n_windows"] for b in client.get(url, params={"window_s": 5}).json()["blocks"]}
    assert counted[f"{S1}_track_01"] == len(track["windows"])
    assert [(w["trips_complete"], w["trips_partial"]) for w in track["windows"]] == [(0, 2), (0, 1)]  # trip 2 returns after the first window
    longer = client.get(f"{url}/{S1}_track_01", params={"window_s": 10}).json()["windows"]
    assert [(w["trips_complete"], w["trips_partial"]) for w in longer] == [(1, 2)]
    assert client.get(f"{url}/{S1}_arena_01").json()["geometry"]["circle"]["radius"] > 0
    columns = arrays_of(client.get(f"{url}/{S1}_track_01/arrays"))
    assert list(columns) == ["frame", "t", "x", "y", "heading", "speed", "n_lights"] and len(columns["x"]) == track["n_frames"]
    assert columns["frame"][0] == track["frame_start"] and 0 < np.nanmax(np.abs(columns["x"])) < 3
    assert client.get(f"{url}/nothing").status_code == 404


def test_window_settings_are_saved_whole_and_read_back(client, tmp_path):
    assert client.get("/api/windows/settings").json()["saved"] is None
    body = {"settings": {"window_s": 5}}
    first = client.put("/api/windows/settings", json=body).json()
    assert first["overwrote"] is False and (tmp_path / "lab_blocks.yaml").is_file()
    assert first["saved"]["totals"]["overall"]["blocks_ok"] == 2
    assert client.put("/api/windows/settings", json=body).json()["overwrote"] is True
    assert client.get("/api/windows/settings").json()["settings"]["window_s"] == 5


def test_the_format_contract_lists_the_frames_columns_the_tool_reads(client):
    frames = next(f for f in client.get("/api/format").json()["transformed"]["files"] if f["path"].startswith("frames/"))
    assert {c["name"] for c in frames["columns"] if c["required"]} >= {"frame", "t", "mashup_x", "head_dir"}


def test_a_processed_folder_not_built_yet_is_ok_and_its_routes_say_so(client_on, tmp_path, transformed):
    later = tmp_path / "later"
    client = client_on({"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(later)})
    source = client.get("/api/sources").json()["processed"]
    assert (source["status"], source["counts"], source["manifest"]) == ("ok", {"reviews": 0}, None)
    assert "no processed dataset" in client.get("/api/blocks").json()["error"]
    assert client.put("/api/windows/settings", json={"settings": {}}).status_code == 404
