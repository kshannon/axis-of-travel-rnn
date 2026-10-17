"""
The API through the test client on the synthetic folders: sources, sessions, reviews, blocks and the window settings.
"""

import numpy as np
import pyarrow as pa
import pytest

from fixtures import S1, S2, S6, STAMP

EDITS = [{"op": "drop", "frame": 1000}, {"op": "split", "frame": 2700}, {"op": "accept"}, {"op": "flag", "run": 2}]


def arrays_of(response):
    """
    The columns of an Arrow response as numpy arrays.
    """
    table = pa.ipc.open_stream(response.content).read_all()
    return {name: table[name].to_numpy() for name in table.column_names}


def test_attach_lists_and_detaches_without_touching_the_data(client, transformed, processed):
    body = {"path": str(transformed), "kind": "transformed", "processed_path": str(processed)}
    source = client.post("/api/sources", json=body).json()
    assert client.post("/api/sources", json=body).json()["id"] == source["id"]
    assert source["status"] == "ok" and source["counts"] == {"sessions": 6, "epochs": 13, "runs": 6, "frames": 2, "blocks": 3, "reviews": 0}
    assert source["manifests"]["transformed"]["timestamp"] == STAMP
    assert [s["id"] for s in client.get("/api/sources").json()] == [source["id"]]
    assert client.delete(f"/api/sources/{source['id']}").json() == {"detached": source["id"]}
    assert client.get("/api/sources").json() == [] and (transformed / "sessions.csv").is_file()
    assert client.delete(f"/api/sources/{source['id']}").status_code == 404


def test_attach_refuses_a_folder_that_breaks_the_format(client, tmp_path, transformed, processed):
    (transformed / "epochs.csv").unlink()
    cases = [{"path": str(tmp_path / "nope"), "kind": "processed"},
             {"path": str(transformed), "kind": "transformed", "processed_path": str(processed)},
             {"path": str(transformed), "kind": "transformed"}]
    for body in cases:
        response = client.post("/api/sources", json=body)
        assert response.status_code == 400 and response.json()["error"]
    assert "missing epochs.csv" in client.post("/api/sources", json=cases[1]).json()["error"]
    assert client.get("/api/sources").json() == []


def test_session_index_lists_the_funnel_and_the_automatic_blocks(client, attached):
    rows = client.get(f"/api/sources/{attached[0]}/sessions").json()
    assert [r["session_id"] for r in rows][:2] == [S1, S6] and len(rows) == 6
    assert [(r["in_dataset"], r["n_automatic"]) for r in rows[:2]] == [(True, 2), (True, 2)]
    assert all(not r["in_dataset"] and r["n_automatic"] is None for r in rows[2:])
    assert client.get(f"/api/sources/{attached[1]}/sessions").status_code == 400


def test_a_session_is_served_as_a_header_and_arrow_arrays(client, attached):
    header = client.get(f"/api/sources/{attached[0]}/sessions/{S1}").json()
    assert header["n_frames"] == 5400 and header["heading_filled"] == [[2800, 2919]] and header["block_epochs"] == ["arena", "track"]
    assert [b["frame_start"] for b in header["blocks"]] == [301, 2101]
    assert header["occupancy"]["bins"] ** 2 == len(header["occupancy"]["counts"]["arena"])
    columns = arrays_of(client.get(f"/api/sources/{attached[0]}/sessions/{S1}/arrays"))
    assert list(columns) == ["t", "x", "y", "heading", "speed", "motion", "n_lights"]
    assert all(len(values) == 5400 for values in columns.values()) and columns["n_lights"].dtype == np.int8
    assert np.isfinite(columns["heading"][2800:2920]).all()  # the lab's 2 s heading gap is filled
    for session_id in (S2, "nobody"):
        assert client.get(f"/api/sources/{attached[0]}/sessions/{session_id}").status_code == 404


def test_a_review_is_saved_whole_and_read_back_and_the_index_follows(client, attached, processed):
    url = f"/api/sources/{attached[0]}/sessions/{S1}/review"
    assert client.get(url).json() is None
    saved = client.put(url, json={"edits": EDITS, "notes": "shaky"}).json()
    assert saved["overwrote"] is False and saved["path"] == str(processed / "review" / f"{S1}.json")
    assert client.put(url, json={"edits": EDITS, "notes": "shaky"}).json()["overwrote"] is True
    stored = client.get(url).json()
    assert [b["status"] for b in stored["blocks"]] == ["dropped", "edited", "edited"] and stored["notes"] == "shaky"
    rows = client.get(f"/api/sources/{attached[0]}/sessions").json()
    assert [r["session_id"] for r in rows][:2] == [S6, S1]  # the dataset's unreviewed session comes first
    assert (rows[1]["reviewed"], rows[1]["n_confirmed"]) == (True, 2)
    assert rows[1]["confirmed_s"] == pytest.approx({"arena": 0, "track": 20.0})  # 599 and 601 frames at 60 Hz, ends included


def test_a_review_is_refused_while_a_block_is_auto_and_a_bad_edit_is_named(client, attached, processed):
    url = f"/api/sources/{attached[0]}/sessions/{S1}/review"
    assert "still auto" in client.put(url, json={"edits": [], "notes": ""}).json()["error"]
    bad = client.put(url, json={"edits": [{"op": "drop"}]})
    assert bad.status_code == 422 and "drop.frame" in bad.json()["error"]
    wrong = [{"op": "split", "frame": 2700.5}, {"op": "split", "frame": True}, {"op": "drop", "frame": "2700"}, {"op": "drop", "frame": None},
             {"op": "flag", "run": [1]}, {"op": "move", "edge": "middle", "at": 2700, "frame": 2000},
             {"op": "cut", "frame_start": 3000, "frame_end": 2500}]
    for edit in wrong:  # none reaches the edit logic or the review file
        response = client.put(url, json={"edits": [edit, {"op": "accept"}]})
        assert response.status_code == 422 and response.json()["error"], edit
    assert not (processed / "review").exists()


def test_a_preview_applies_the_edits_and_writes_nothing(client, attached, processed):
    url = f"/api/sources/{attached[0]}/sessions/{S1}/review"
    edits = [{"op": "drop", "frame": 1000}, {"op": "confirm", "frame": 5}, {"op": "flag", "run": 2}, {"op": "cut", "frame_start": 2200, "frame_end": 2300}]
    preview = client.post(f"{url}/preview", json={"edits": edits}).json()
    assert [b["status"] for b in preview["blocks"]] == ["dropped", "dropped", "edited"]  # the cut leaves a piece under 10 s
    assert preview["flagged_runs"] == [2]
    assert [e["frame"] for e in preview["skipped"]] == [5] and preview["cuts"][0]["frame_start"] == 2200
    assert not (processed / "review").exists()


def test_a_preview_says_why_each_edit_was_skipped(client, attached):
    url = f"/api/sources/{attached[0]}/sessions/{S1}/review/preview"
    new = [{"op": "new", "frame_start": 400, "frame_end": 410}, {"op": "new", "frame_start": 1400, "frame_end": 1600},
           {"op": "new", "frame_start": 400, "frame_end": 1100}]
    edits = [{"op": "drop", "frame": 1000}, {"op": "confirm", "frame": 5}, *new, {"op": "new", "frame_start": 400, "frame_end": 1100}]
    skipped = client.post(url, json={"edits": edits}).json()["skipped"]
    assert [e["reason"] for e in skipped] == ["no block holds frame 5", "a new block must last 10 s or more",
                                              "a new block must lie between two cuts: no pause, gap or epoch bound inside it",
                                              "a new block cannot overlap a block that is kept, remove that block first"]
    assert [e["op"] for e in skipped] == ["confirm", "new", "new", "new"]


def arena_blocks(blocks):
    """
    The frame range and status of the arena blocks.
    """
    return [(b["frame_start"], b["frame_end"], b["status"]) for b in blocks if b["epoch"] == "arena"]


def test_an_edit_at_a_frame_a_removed_block_and_a_kept_one_share_reaches_the_kept_one(client, attached):
    url = f"/api/sources/{attached[0]}/sessions/{S6}/review"
    edits = [{"op": "accept"}, {"op": "drop", "frame": 301}, {"op": "new", "frame_start": 399, "frame_end": 1299},
             {"op": "move", "frame": 449, "edge": "start", "at": 399}]
    expected = [(301, 1500, "dropped"), (449, 1299, "edited")]
    assert arena_blocks(client.post(f"{url}/preview", json={"edits": edits}).json()["blocks"]) == expected
    assert arena_blocks(client.put(url, json={"edits": edits}).json()["review"]["blocks"]) == expected
    removed = client.post(f"{url}/preview", json={"edits": [*edits[:3], {"op": "drop", "frame": 399}]}).json()["blocks"]
    assert arena_blocks(removed) == [(301, 1500, "dropped"), (399, 1299, "dropped")]


def test_blocks_that_start_on_the_same_frame_are_numbered_in_the_order_they_were_made(client, attached):
    url = f"/api/sources/{attached[0]}/sessions/{S1}/review/preview"
    over = [{"op": "accept"}, {"op": "drop", "frame": 301}, {"op": "new", "frame_start": 301, "frame_end": 1299}]
    restored = [*over, {"op": "drop", "frame": 301}, {"op": "drop", "frame": 1400}]  # the new block is removed, then the first one is back
    for edits, expected in ((over, [(1500, "dropped"), (1299, "edited")]), (restored, [(1500, "edited"), (1299, "dropped")])):
        blocks = [b for b in client.post(url, json={"edits": edits}).json()["blocks"] if b["epoch"] == "arena"]
        assert [(b["block_id"], b["frame_end"], b["status"]) for b in blocks] == [(f"{S1}_arena_{i:02d}", *made) for i, made in enumerate(expected, 1)]


def test_block_verdicts_follow_the_window_settings(client, attached):
    url = f"/api/sources/{attached[1]}/blocks"
    default = client.get(url).json()
    assert {b["reason"] for b in default["blocks"]} == {"no window fits"} and default["totals"]["overall"]["windows"] == 0
    short = client.get(url, params={"window_s": 5}).json()
    verdicts = {b["block_id"]: (b["ok"], b["n_windows"]) for b in short["blocks"]}
    assert verdicts[f"{S1}_arena_01"] == (True, 2) and verdicts[f"{S6}_track_01"][0] is False
    assert short["totals"]["overall"]["blocks_ok"] == 2 and short["settings"]["window_s"] == 5
    assert client.get(url, params={"window_s": -1}).status_code == 422


def test_a_block_is_served_in_metres_with_its_environment_and_windows(client, attached):
    url = f"/api/sources/{attached[1]}/blocks"
    track = client.get(f"{url}/{S1}_track_01", params={"window_s": 5}).json()
    assert track["geometry"]["walls"] and "start" in track["geometry"]["reward_sites"] and track["geometry"]["circle"] is None
    assert [r["run"] for r in track["runs"]] == [1, 2, 3] and track["verdict"] == {"ok": True, "reason": None}
    assert track["one_light"] == [[699, 818]]  # the back light lost at lab frames 2800 to 2919, the block starting at 2101
    assert [w["first"] for w in track["windows"]] == [0, 600] and track["windows"][0]["ok"] and not track["windows"][1]["ok"]
    assert client.get(f"{url}/{S1}_arena_01").json()["geometry"]["circle"]["radius"] > 0
    columns = arrays_of(client.get(f"{url}/{S1}_track_01/arrays"))
    assert list(columns) == ["frame", "t", "x", "y", "heading", "speed", "n_lights"] and len(columns["x"]) == track["n_frames"]
    assert columns["frame"][0] == track["frame_start"] and 0 < np.nanmax(np.abs(columns["x"])) < 3
    assert client.get(f"{url}/nothing").status_code == 404


def test_window_settings_are_saved_whole_and_read_back(client, attached, tmp_path):
    assert client.get("/api/windows/settings").json()["saved"] is None
    body = {"settings": {"window_s": 5}, "source": attached[1]}
    first = client.put("/api/windows/settings", json=body).json()
    assert first["overwrote"] is False and (tmp_path / "lab_blocks.yaml").is_file()
    assert first["saved"]["totals"]["overall"]["blocks_ok"] == 2
    assert client.put("/api/windows/settings", json=body).json()["overwrote"] is True
    assert client.get("/api/windows/settings").json()["settings"]["window_s"] == 5
    assert client.put("/api/windows/settings", json={"settings": {}, "source": "nobody"}).status_code == 404


def test_the_format_contract_lists_the_frames_columns_the_tool_reads(client):
    frames = next(f for f in client.get("/api/format").json()["transformed"]["files"] if f["path"].startswith("frames/"))
    assert {c["name"] for c in frames["columns"] if c["required"]} >= {"frame", "t", "mashup_x", "head_dir"}


def test_a_transformed_source_can_be_attached_before_the_processor_has_run(client, transformed, tmp_path):
    later = tmp_path / "later"
    source = client.post("/api/sources", json={"path": str(transformed), "kind": "transformed", "processed_path": str(later)}).json()
    assert source["status"] == "ok" and "blocks" not in source["counts"] and source["manifests"]["processed"] is None
    assert "no processed dataset" in client.get(f"/api/sources/{source['id']}/blocks").json()["error"]
    saved = client.put(f"/api/sources/{source['id']}/sessions/{S6}/review", json={"edits": [{"op": "accept"}]}).json()
    assert saved["overwrote"] is False and (later / "review" / f"{S6}.json").is_file()
    assert client.get("/api/sources").json()[0]["counts"]["reviews"] == 1
