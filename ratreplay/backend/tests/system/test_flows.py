"""
The flows of the HTTP surface over the synthetic folders and an empty processed folder: reviewing and saving a session, rebuilding, and judging and selecting readiness. Status codes, shapes, Arrow and the sequence of calls, the numbers are proven below this level.
"""

import io

import numpy as np
import pyarrow as pa
import pytest
from fixtures import S1, S2, S6

from ratreplay_api.managers.review import ARRAY_KEYS
from ratreplay_api.managers.validation import ARRAY_COLUMNS
from ratreplay_api.utilities.arrow import MEDIA_TYPE

# A window of 5 s so the 10 to 30 s blocks of the fixtures yield windows, one longer than any block yields none.
SHORT = {"window_s": 5}
LONGER = {"window_s": 10}
TOO_LONG = {"window_s": 1000}

# S1 has an arena and a track block, the edits confirm the arena block, split the track block in two, confirm the first and drop the second.
# S6 has one track block. The save result, the readiness and the selection answer with these keys.
SAVED = [{"op": "confirm", "frame": 1000}, {"op": "split", "frame": 2701}, {"op": "confirm", "frame": 2101}, {"op": "drop", "frame": 2701}]
ACCEPT = [{"op": "accept"}]
SAVE_KEYS = {"review", "replaced", "file", "built", "failed", "build_error"}
EXCLUSION_KEYS = {"review", "replaced", "file", "deleted", "built", "failed", "build_error"}
READINESS_KEYS = {"which", "settings", "blocks", "totals", "built"}
TOTALS_KEYS = {"blocks", "ok", "trouble", "windows", "windows_ok"}
BLOCK_HEADER_KEYS = {"row", "rate_hz", "geometry", "runs", "trips", "phases", "heading_filled", "heading_held", "one_light"}
WINDOWS_KEYS = {"rows", "verdict", "count"}
TRACK = f"{S1}_track_01"

# The start offset in metres a request gives, and one more than the track's stem leaves room for.
OFFSET, TOO_FAR = 0.1, 0.4


def table_of(response):
    """
    The Arrow table in the bytes of a response.
    """
    return pa.ipc.open_stream(io.BytesIO(response.content)).read_all()


def save(client, sid, edits, settings=SHORT):
    """
    Save the session's blocks through the API and return the response.
    """
    return client.put(f"/api/sessions/{sid}/blocks", json={"edits": edits, "notes": "", "settings": settings, "start_offset_m": None})


@pytest.fixture
def built(client):
    """
    The client after S1 and S6 were reviewed and built through the API.
    """
    assert save(client, S1, SAVED).status_code == 200 and save(client, S6, ACCEPT).status_code == 200
    return client


def test_a_session_is_listed_loaded_at_the_query_settings_and_streamed_as_arrow(client):
    index = client.get("/api/sessions")
    assert index.status_code == 200 and len(index.json()) == 6
    assert {row["session_id"] for row in index.json() if row["in_dataset"]} == {S1, S6}
    assert {"session_id", "in_dataset", "reason", "built", "reviewed", "epochs"} <= index.json()[0].keys()
    header = client.get(f"/api/sessions/{S1}", params=SHORT)
    assert header.status_code == 200 and header.json()["review"] is None and header.json()["in_dataset"] is True
    assert {"epochs", "runs", "environments", "blocks", "refusals", "warnings", "n_frames"} <= header.json().keys()
    blocks = header.json()["blocks"]
    assert len(blocks) == 2 and all(set(b["windows"]) == {"count", "verdict"} and b["windows"]["count"] > 0 for b in blocks)
    longer = client.get(f"/api/sessions/{S1}", params=TOO_LONG).json()["blocks"]
    assert [b["windows"]["count"] for b in longer] == [0, 0]
    arrays = client.get(f"/api/sessions/{S1}/arrays")
    assert arrays.status_code == 200 and arrays.headers["content-type"] == MEDIA_TYPE
    table = table_of(arrays)
    assert table.schema.names == list(ARRAY_KEYS) and table.num_rows == header.json()["n_frames"]


def test_the_session_arrays_travel_as_float32_but_t_and_the_lights(client):
    types = {field.name: field.type for field in table_of(client.get(f"/api/sessions/{S1}/arrays")).schema}
    assert types == {"t": pa.float64(), "n_lights": pa.int8(), **{name: pa.float32() for name in ARRAY_KEYS if name not in ("t", "n_lights")}}


def test_a_preview_returns_the_refusal_of_an_illegal_edit_and_writes_nothing(client, processed):
    body = {"edits": [*ACCEPT, {"op": "split", "frame": 100}], "settings": SHORT, "start_offset_m": None}
    response = client.post(f"/api/sessions/{S1}/preview", json=body)
    assert response.status_code == 200 and response.json().keys() == {"blocks", "refusals", "cuts", "flagged_runs"}
    refusal = response.json()["refusals"]
    assert len(refusal) == 1 and refusal[0].keys() == {"index", "op", "reason"} and refusal[0]["index"] == 1 and refusal[0]["reason"]
    assert all(set(b["windows"]) == {"count", "verdict"} for b in response.json()["blocks"])
    assert list(processed.iterdir()) == []


def test_save_blocks_names_the_review_file_and_the_blocks_built_and_health_then_counts_them(client, processed):
    before = client.get("/api/health").json()["processed"]
    assert before["problems"] == [] and before["counts"] == {"reviews": 0, "blocks": 0, "sessions": 0}
    saved = client.put(f"/api/sessions/{S1}/blocks", json={"edits": SAVED, "notes": "shaky", "settings": SHORT, "start_offset_m": None})
    assert saved.status_code == 200 and saved.json().keys() == SAVE_KEYS
    result = saved.json()
    assert (result["file"], result["replaced"], result["built"], result["failed"], result["build_error"]) == (f"review/{S1}.json", False, 2, [], None)
    assert result["review"]["notes"] == "shaky" and result["review"]["edits"] == SAVED
    assert (processed / result["file"]).is_file()
    after = client.get("/api/health").json()["processed"]
    assert after["problems"] == [] and after["counts"] == {"reviews": 1, "blocks": 2, "sessions": 1}
    header = client.get(f"/api/sessions/{S1}", params=SHORT).json()
    assert header["review"] == result["review"] and [b["status"] for b in header["blocks"]] == ["confirmed", "confirmed", "dropped"]
    row = next(r for r in client.get("/api/sessions").json() if r["session_id"] == S1)
    assert (row["reviewed"], row["built"]) == (True, 2)
    assert save(client, S1, SAVED).json()["replaced"] is True


def test_rebuild_all_reports_the_totals_and_builds_at_the_settings_it_is_sent(client):
    empty = client.post("/api/rebuild", json={"settings": SHORT})
    assert empty.status_code == 200 and empty.json() == {"sessions": {}, "skipped": {}, "excluded": {},
                                                           "totals": {"sessions": 0, "built": 0, "failed": 0, "errors": 0, "skipped": 0, "excluded": 0}}
    assert save(client, S1, SAVED).status_code == 200 and save(client, S6, ACCEPT).status_code == 200
    done = client.post("/api/rebuild", json={"settings": LONGER})
    assert done.status_code == 200 and done.json().keys() == {"sessions", "skipped", "excluded", "totals"}
    assert done.json()["sessions"] == {S1: {"built": 2, "failed": [], "build_error": None}, S6: {"built": 1, "failed": [], "build_error": None}}
    assert done.json()["skipped"] == {} and done.json()["excluded"] == {}
    assert done.json()["totals"] == {"sessions": 2, "built": 3, "failed": 0, "errors": 0, "skipped": 0, "excluded": 0}
    built = client.get("/api/blocks", params=SHORT).json()["built"]
    assert {sid: b["settings"]["window_s"] for sid, b in built.items()} == {S1: 10.0, S6: 10.0}


def test_a_session_is_excluded_through_the_api_which_clears_its_blocks_at_once_and_included_again(built):
    excluded = built.put(f"/api/sessions/{S1}/exclusion", json={"excluded": True, "note": "camera moved", "settings": SHORT})
    assert excluded.status_code == 200 and excluded.json().keys() == EXCLUSION_KEYS
    assert (excluded.json()["replaced"], excluded.json()["file"], excluded.json()["deleted"], excluded.json()["built"]) == (True, f"review/{S1}.json", False, 0)
    assert excluded.json()["review"]["excluded"] is True and excluded.json()["review"]["notes"] == "camera moved"
    assert {b["session_id"] for b in built.get("/api/blocks", params=SHORT).json()["blocks"]} == {S6}  # no rebuild needed, the blocks are gone
    row = next(r for r in built.get("/api/sessions").json() if r["session_id"] == S1)
    assert (row["excluded"], row["annotated_exclude"], row["built"]) == (True, False, 0)
    assert built.get(f"/api/sessions/{S1}", params=SHORT).json()["excluded"] is True
    refused = save(built, S1, SAVED)
    assert refused.status_code == 400 and refused.json() == {"error": f"session {S1} is excluded, include it first"}
    done = built.post("/api/rebuild", json={"settings": SHORT})
    assert done.json()["excluded"] == {S1: "camera moved"} and done.json()["skipped"] == {}
    assert done.json()["totals"] == {"sessions": 2, "built": 1, "failed": 0, "errors": 0, "skipped": 0, "excluded": 1}
    back = built.put(f"/api/sessions/{S1}/exclusion", json={"excluded": False})
    assert back.json()["review"]["excluded"] is False and back.json()["deleted"] is False and back.json()["built"] == 0
    assert built.post("/api/rebuild", json={"settings": SHORT}).json()["totals"] == {"sessions": 2, "built": 3, "failed": 0, "errors": 0, "skipped": 0, "excluded": 0}


def test_excluding_and_including_a_session_no_one_reviewed_leaves_the_folder_as_it_was(client, processed):
    def state():
        row = next(r for r in client.get("/api/sessions").json() if r["session_id"] == S1)
        return row, client.get("/api/blocks", params=SHORT).json(), sorted(str(path.relative_to(processed)) for path in processed.rglob("*") if path.is_file())
    before = state()
    assert client.put(f"/api/sessions/{S1}/exclusion", json={"excluded": True, "note": "x", "settings": SHORT}).json()["review"]["excluded"] is True
    assert state()[0]["excluded"] is True
    back = client.put(f"/api/sessions/{S1}/exclusion", json={"excluded": False, "note": "y", "settings": SHORT})
    assert back.status_code == 200 and back.json()["review"] is None and back.json()["deleted"] is True and back.json()["file"] == f"review/{S1}.json"
    assert state() == before
    assert client.put(f"/api/sessions/{S2}/exclusion", json={"excluded": True}).status_code == 404


def test_readiness_lists_the_blocks_with_verdicts_and_a_block_gives_its_header_arrays_and_windows(built):
    readiness = built.get("/api/blocks", params={"which": "real", **SHORT})
    assert readiness.status_code == 200 and readiness.json().keys() == READINESS_KEYS
    found = readiness.json()
    assert found["which"] == "real" and found["settings"]["window_s"] == 5.0 and found["totals"].keys() == TOTALS_KEYS
    assert len(found["blocks"]) == found["totals"]["blocks"] == 3
    assert all({"block_id", "session_id", "count", "verdict"} <= b.keys() and b["verdict"].keys() == {"ok", "reasons"} for b in found["blocks"])
    assert found["built"].keys() == {S1, S6} and all(b.keys() == {"settings", "built_at", "excluded", "failed"} for b in found["built"].values())
    header = built.get(f"/api/blocks/{TRACK}")
    assert header.status_code == 200 and header.json().keys() == BLOCK_HEADER_KEYS
    assert header.json()["rate_hz"] == header.json()["row"]["rate_hz"] and "walls" in header.json()["geometry"]
    arrays = built.get(f"/api/blocks/{TRACK}/arrays")
    assert arrays.status_code == 200 and arrays.headers["content-type"] == MEDIA_TYPE
    assert table_of(arrays).schema.names == list(ARRAY_COLUMNS) and table_of(arrays).num_rows == header.json()["row"]["n_frames"]
    windows = built.get(f"/api/blocks/{TRACK}/windows", params=SHORT)
    assert windows.status_code == 200 and windows.json().keys() == WINDOWS_KEYS
    assert windows.json()["count"] == len(windows.json()["rows"]) > 0 and windows.json()["verdict"].keys() == {"ok", "reasons"}
    assert built.get(f"/api/blocks/{TRACK}/windows", params=TOO_LONG).json()["count"] == 0


def test_the_selected_settings_are_written_to_windows_json_read_back_and_replaced(built, processed):
    assert built.get("/api/windows").json() == {"selected": None}
    first = built.put("/api/windows", json={"settings": SHORT})
    assert first.status_code == 200 and first.json() == {"replaced": False, "file": "windows.json"}
    assert (processed / first.json()["file"]).is_file()
    selected = built.get("/api/windows").json()["selected"]
    assert selected.keys() == {"settings", "totals", "selected_at", "selected_by"} and selected["settings"]["window_s"] == 5.0
    assert selected["totals"] == built.get("/api/blocks", params=SHORT).json()["totals"]
    assert built.put("/api/windows", json={"settings": LONGER}).json()["replaced"] is True
    assert built.get("/api/windows").json()["selected"]["settings"]["window_s"] == 10.0
    assert built.get("/api/health").json()["processed"]["problems"] == []


def test_environments_are_listed_with_their_geometry_and_the_sessions_registered_against_them_once_built(client):
    empty = client.get("/api/environments")
    assert empty.status_code == 200 and [e["name"] for e in empty.json()] == ["open_arena", "plus_maze", "triple_t", "triple_t_rot90"]
    assert all(e["sessions"] == [] and e["summary"] == {"n_sessions": 0, "n_warned": 0} for e in empty.json())
    assert save(client, S1, ACCEPT).status_code == 200 and save(client, S6, ACCEPT).status_code == 200
    by_name = {e["name"]: e for e in client.get("/api/environments").json()}
    assert "walls" in by_name["triple_t"]["geometry"] and by_name["triple_t"]["summary"].keys() == {"n_sessions", "n_warned"}
    assert {name: [r["session_id"] for r in e["sessions"]] for name, e in by_name.items()} == {
        "open_arena": [S1], "plus_maze": [], "triple_t": [S1, S6], "triple_t_rot90": []}
    assert "scale_px_per_m" in by_name["triple_t"]["sessions"][0]


def test_the_start_offset_travels_in_the_query_of_a_header_and_of_arrays_and_in_the_body_of_a_preview_and_a_save(client):
    def start_y(header):
        return header["environments"]["triple_t"]["reward_sites"]["start"][1]

    def heights(params):
        return table_of(client.get(f"/api/sessions/{S1}/arrays", params=params)).column("y").to_numpy(zero_copy_only=False)

    plain = client.get(f"/api/sessions/{S1}", params=SHORT).json()
    asked = client.get(f"/api/sessions/{S1}", params={**SHORT, "start_offset_m": OFFSET}).json()
    assert (plain["start_offset_m"], asked["start_offset_m"]) == (None, OFFSET) and start_y(asked) - start_y(plain) == pytest.approx(OFFSET)
    assert np.nanmax(heights({"start_offset_m": OFFSET}) - heights({})) == pytest.approx(OFFSET)
    for refused in (client.post(f"/api/sessions/{S1}/preview", json={"edits": ACCEPT, "start_offset_m": TOO_FAR}),
                    client.put(f"/api/sessions/{S1}/blocks", json={"edits": ACCEPT, "start_offset_m": TOO_FAR})):
        assert refused.status_code == 400 and "does not close" in refused.json()["error"]
    saved = client.put(f"/api/sessions/{S1}/blocks", json={"edits": SAVED, "notes": "", "settings": SHORT, "start_offset_m": OFFSET})
    assert saved.status_code == 200 and saved.json()["review"]["start_offset_m"] == OFFSET
    assert client.get(f"/api/sessions/{S1}", params=SHORT).json()["start_offset_m"] == OFFSET
    assert save(client, S1, SAVED).json()["review"]["start_offset_m"] is None
    assert client.get(f"/api/sessions/{S1}", params=SHORT).json()["start_offset_m"] is None
