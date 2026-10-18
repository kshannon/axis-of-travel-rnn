"""
The app: the format route, the error body, the frontend at / once built, the composition root building its components once and again on reload, and the ValidationManager over a config that lacks a key.
"""

import re

import pytest
import yaml
from fastapi.testclient import TestClient

from ratreplay_api import app as app_module
from ratreplay_api.access.processed import ProcessedAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.app import UnsetAccess, create_app
from ratreplay_api.engines.trajectory import SETTINGS
from ratreplay_api.managers.review import ReviewManager
from ratreplay_api.managers.validation import ValidationManager
from ratreplay_api.utilities.errors import Invalid


def test_format_route_returns_the_contract(client):
    response = client.get("/api/format")
    assert response.status_code == 200
    assert {"version", "transformed", "processed"} <= response.json().keys()


def test_openapi_names_the_arrow_media_type_of_the_arrays_routes(client):
    paths = client.get("/api/openapi.json").json()["paths"]
    for path in ("/api/sessions/{session_id}/arrays", "/api/blocks/{block_id}/arrays"):
        assert list(paths[path]["get"]["responses"]["200"]["content"]) == ["application/vnd.apache.arrow.stream"]


def test_unknown_route_returns_an_error_body(client):
    response = client.get("/api/nothing")
    assert response.status_code == 404
    assert response.json() == {"error": "Not Found"}


def test_built_frontend_is_served_at_root_and_the_routes_still_win(tmp_path, monkeypatch):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<div id=app></div>")
    monkeypatch.setattr(app_module, "FRONTEND_DIST", tmp_path / "dist")
    client = TestClient(create_app(config_path=tmp_path / "local.yaml"))
    assert client.get("/").text == "<div id=app></div>"
    assert client.get("/api/format").status_code == 200


def test_the_config_file_is_the_repositorys_local_yaml_unless_one_is_given(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "LOCAL_CONFIG", tmp_path / "local.yaml")
    assert create_app().state.config.path == (tmp_path / "local.yaml").resolve()


def recording(method, seen):
    """
    The method, remembering the manager it is called on.
    """
    def recorded(self):
        seen.append(self)
        return method(self)
    return recorded


def test_every_request_is_served_by_the_managers_built_once_over_the_same_engine_and_accesses(client, monkeypatch):
    app, seen = client.app, []
    monkeypatch.setattr(ReviewManager, "index", recording(ReviewManager.index, seen))
    monkeypatch.setattr(ValidationManager, "format", recording(ValidationManager.format, seen))
    for _ in range(2):
        assert client.get("/api/sessions").status_code == 200 and client.get("/api/format").status_code == 200
    review, validation = app.state.review, app.state.validation
    assert len(seen) == 4 and seen[0] is seen[2] is review and seen[1] is seen[3] is validation
    assert review.trajectory is validation.trajectory and review.environment is validation.environment
    assert review.transformed is validation.transformed and review.processed is validation.processed


def test_reload_builds_the_components_again_from_the_config_read_again_and_a_plain_request_does_not(tmp_path, transformed):
    first, second, config = tmp_path / "first", tmp_path / "second", tmp_path / "local.yaml"
    for folder in (first, second):
        folder.mkdir()

    def point_at(processed):
        config.write_text(yaml.safe_dump({"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(processed)}))

    def processed_root(query=""):
        return client.get(f"/api/health{query}").json()["processed"]["root"]

    point_at(first)
    client = TestClient(create_app(config_path=config))
    app = client.app
    review, validation = app.state.review, app.state.validation
    assert processed_root() == str(first.resolve())
    point_at(second)
    assert processed_root() == str(first.resolve()) and app.state.validation is validation
    assert processed_root("?reload=true") == str(second.resolve())
    assert app.state.review is not review and app.state.validation is not validation
    assert app.state.review.processed.root == app.state.validation.processed.root == second.resolve()
    assert processed_root() == str(second.resolve())


def test_a_transformed_folder_that_is_not_there_is_a_404_naming_it_and_health_names_it_too(client_on, tmp_path):
    client = client_on({"TRANSFORMED_LAB_DATA": str(tmp_path / "nope"), "PROCESSED_LAB_DATA": str(tmp_path)})
    problem = f"{(tmp_path / 'nope').resolve()} does not exist"
    assert client.get("/api/sessions").status_code == 404 and client.get("/api/sessions").json() == {"error": problem}
    assert client.get("/api/health").json()["transformed"]["problems"] == [problem]


def test_a_window_setting_the_api_does_not_know_is_a_422_naming_it_in_a_query_and_in_a_body(client):
    query = client.get("/api/blocks/x/windows", params={"train_rate_hz": 20})
    assert query.status_code == 422 and query.json() == {"error": "train_rate_hz: Extra inputs are not permitted"}
    body = client.put("/api/windows", json={"settings": {"train_rate_hz": 20}})
    assert body.status_code == 422 and body.json() == {"error": "settings.train_rate_hz: Extra inputs are not permitted"}


def public(cls):
    """
    The names of a class that do not start with an underscore.
    """
    return {name for name in dir(cls) if not name.startswith("_")}


def test_the_stand_in_for_an_unset_folder_answers_every_public_name_of_the_accesses_it_stands_for():
    assert public(TransformedAccess) | public(ProcessedAccess) <= public(UnsetAccess)


def test_a_key_the_config_lacks_is_named_by_health_and_the_format_still_answers_while_the_folders_verbs_refuse(tmp_path):
    (tmp_path / "local.yaml").write_text(yaml.safe_dump({"PROCESSED_LAB_DATA": str(tmp_path / "processed")}))
    app = create_app(config_path=tmp_path / "local.yaml")
    manager, config_path = app.state.validation, app.state.config.path
    problem = f"TRANSFORMED_LAB_DATA is not set in {config_path}"
    health = manager.health(config_path)
    assert health["transformed"] == {"root": None, "exists": False, "problems": [problem], "counts": {}, "manifest": None}
    assert health["processed"]["problems"] == [] and health["environments"]["problems"] == [] and health["config_path"] == str(config_path)
    assert manager.format()["transformed"] == TransformedAccess(tmp_path).schema() and TestClient(app).get("/api/format").status_code == 200
    assert manager.readiness("real", SETTINGS)["totals"]["blocks"] == 0
    assert not hasattr(manager.transformed, "nothing")
    with pytest.raises(Invalid, match=re.escape(problem)):
        manager.transformed.sessions()
