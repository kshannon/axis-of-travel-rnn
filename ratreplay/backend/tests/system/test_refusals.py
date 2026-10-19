"""
The refusals and edges of the HTTP surface: a malformed body or query is a 422 naming the field, an unknown id a 404, a write the rules refuse a 400 with the reason and nothing written, a folder that is missing or changed in the config named by health and the routes.
"""

import yaml
from fixtures import S1, S2

from ratreplay_api.managers.review import STILL_AUTO
from ratreplay_api.managers.validation import NOTHING_BUILT

UNPROCESSABLE, INVALID, NOT_FOUND = 422, 400, 404
SHORT = {"window_s": 5}
ACCEPT = [{"op": "accept"}]
NO_OFFSET = {"start_offset_m": None}  # the body of a preview and a save always gives the start offset, none being the yaml's

# Each malformed edit with the field the 422 names. The edit is the first of the list, so its path starts at edits.0.
MALFORMED_EDITS = {
    "a field missing": ({"op": "split"}, "edits.0.split.frame"),
    "a field of the wrong type": ({"op": "split", "frame": "x"}, "edits.0.split.frame"),
    "a field the op does not take": ({"op": "accept", "frame": 1}, "edits.0.accept.frame"),
    "an op the API does not know": ({"op": "nope"}, "edits.0"),
    "a range that ends before it starts": ({"op": "cut", "frame_start": 5, "frame_end": 2}, "edits.0.cut"),
}

# Each request with window settings or an exclusion flag the API refuses, as (method, path, how it travels, what it carries) and the field the 422 names.
BAD_SETTINGS = {
    "a window of no length in the query of a header": ("get", f"/api/sessions/{S1}", "params", {"window_s": -1}, "window_s"),
    "a share above one in the query of readiness": ("get", "/api/blocks", "params", {"min_heading_measured": 2}, "min_heading_measured"),
    "an unknown key in the query of a header": ("get", f"/api/sessions/{S1}", "params", {"bogus": 1}, "bogus"),
    "an unknown key in the query of readiness": ("get", "/api/blocks", "params", {"bogus": 1}, "bogus"),
    "a stride of no length in the body of a preview": ("post", f"/api/sessions/{S1}/preview", "json", {"edits": [], "settings": {"stride_s": 0}}, "settings.stride_s"),
    "an unknown key in the body of a save": ("put", f"/api/sessions/{S1}/blocks", "json", {"edits": ACCEPT, "settings": {"bogus": 1}}, "settings.bogus"),
    "an unknown key in the body of a rebuild": ("post", "/api/rebuild", "json", {"settings": {"bogus": 1}}, "settings.bogus"),
    "no settings in the body of a rebuild": ("post", "/api/rebuild", "json", {}, "settings"),
    "no start offset in the body of a preview": ("post", f"/api/sessions/{S1}/preview", "json", {"edits": []}, "start_offset_m"),
    "no start offset in the body of a save": ("put", f"/api/sessions/{S1}/blocks", "json", {"edits": ACCEPT}, "start_offset_m"),
    "a flag that is not true or false in the body of an exclusion": ("put", f"/api/sessions/{S1}/exclusion", "json", {"excluded": "yes"}, "excluded"),
    "no flag in the body of an exclusion": ("put", f"/api/sessions/{S1}/exclusion", "json", {"note": "x"}, "excluded"),
    "an unknown key in the body of an exclusion": ("put", f"/api/sessions/{S1}/exclusion", "json", {"excluded": True, "bogus": 1}, "bogus"),
}

# Each request for an id the data does not hold, as (method, path, json). S2 is in the index but has no frames file.
UNKNOWN = [
    ("get", "/api/sessions/nope", None),
    ("get", "/api/sessions/nope/arrays", None),
    ("post", "/api/sessions/nope/preview", {"edits": [], **NO_OFFSET}),
    ("put", "/api/sessions/nope/blocks", {"edits": ACCEPT, **NO_OFFSET}),
    ("put", "/api/sessions/nope/exclusion", {"excluded": True}),
    ("put", f"/api/sessions/{S2}/exclusion", {"excluded": True}),
    ("get", f"/api/sessions/{S2}", None),
    ("get", "/api/blocks/nope", None),
    ("get", "/api/blocks/nope/arrays", None),
    ("get", "/api/blocks/nope/windows", None),
]


def test_a_malformed_edit_is_a_422_naming_the_field_on_preview_and_on_save_and_nothing_is_written(client, processed):
    for what, (edit, field) in MALFORMED_EDITS.items():
        for response in (client.post(f"/api/sessions/{S1}/preview", json={"edits": [edit]}), client.put(f"/api/sessions/{S1}/blocks", json={"edits": [edit]})):
            assert response.status_code == UNPROCESSABLE and response.json().keys() == {"error"}, what
            assert response.json()["error"].startswith(field), what
    missing = client.put(f"/api/sessions/{S1}/blocks", json={})
    assert missing.status_code == UNPROCESSABLE and missing.json() == {"error": "edits: Field required"}
    assert list(processed.iterdir()) == []


def test_a_setting_or_flag_out_of_range_missing_or_unknown_is_a_422_naming_it(client):
    for what, (method, path, how, settings, field) in BAD_SETTINGS.items():
        response = client.request(method, path, **{how: settings})
        assert response.status_code == UNPROCESSABLE and response.json().keys() == {"error"}, what
        assert response.json()["error"].startswith(f"{field}:"), what


def test_an_unknown_session_or_block_is_a_404_with_an_error_body(client):
    for method, path, body in UNKNOWN:
        response = client.request(method, path, json=body)
        assert response.status_code == NOT_FOUND and response.json().keys() == {"error"} and response.json()["error"], path


def test_a_save_the_rules_refuse_and_a_selection_with_nothing_built_are_400s_with_the_reason_and_write_nothing(client, processed):
    illegal = client.put(f"/api/sessions/{S1}/blocks", json={"edits": [*ACCEPT, {"op": "split", "frame": 100}], **NO_OFFSET})
    assert illegal.status_code == INVALID and illegal.json()["error"].startswith("edit 2 (split at frame 100): ")
    auto = client.put(f"/api/sessions/{S1}/blocks", json={"edits": [{"op": "confirm", "frame": 1000}], **NO_OFFSET})
    assert auto.status_code == INVALID and auto.json() == {"error": STILL_AUTO}
    left_out = client.put(f"/api/sessions/{S2}/blocks", json={"edits": ACCEPT, **NO_OFFSET})
    assert left_out.status_code == INVALID and left_out.json()["error"].startswith(f"session {S2} is not in the dataset: ")
    selection = client.put("/api/windows", json={"settings": SHORT})
    assert selection.status_code == INVALID and selection.json() == {"error": NOTHING_BUILT}
    assert list(processed.iterdir()) == []


def test_a_missing_transformed_folder_is_a_404_on_every_session_route_and_reload_picks_up_the_fixed_config_for_the_first_save(client_on, tmp_path, transformed):
    nowhere, later = tmp_path / "nowhere", tmp_path / "later"
    client = client_on({"TRANSFORMED_LAB_DATA": str(nowhere), "PROCESSED_LAB_DATA": str(later)})
    problem = f"{nowhere.resolve()} does not exist"
    health = client.get("/api/health").json()
    assert health["transformed"]["problems"] == [problem] and health["processed"]["exists"] is False and health["processed"]["problems"] == []
    session_routes = (client.get("/api/sessions"), client.get(f"/api/sessions/{S1}"), client.get(f"/api/sessions/{S1}/arrays"),
                      client.post(f"/api/sessions/{S1}/preview", json={"edits": [], **NO_OFFSET}),
                      client.put(f"/api/sessions/{S1}/blocks", json={"edits": ACCEPT, **NO_OFFSET}))
    assert [r.status_code for r in session_routes] == [NOT_FOUND] * 5 and all(r.json() == {"error": problem} for r in session_routes)
    (tmp_path / "local.yaml").write_text(yaml.safe_dump({"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(later)}))
    assert client.get("/api/sessions").status_code == NOT_FOUND
    reloaded = client.get("/api/health", params={"reload": "true"}).json()
    assert reloaded["transformed"]["problems"] == [] and reloaded["transformed"]["root"] == str(transformed.resolve())
    assert client.get("/api/sessions").status_code == 200 and not later.exists()
    assert client.put(f"/api/sessions/{S1}/blocks", json={"edits": ACCEPT, "settings": SHORT, **NO_OFFSET}).json()["built"] == 2
    assert client.get("/api/health").json()["processed"]["exists"] is True and later.is_dir()
