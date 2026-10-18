"""
The app: the format route, the error body, the frontend at / once built, and the composition of the ValidationManager over a config that lacks a key.
"""

import re

import pytest
import yaml
from fastapi.testclient import TestClient

from proj_helpers import paths
from ratreplay_api import app as app_module
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.app import create_app
from ratreplay_api.engines.trajectory import SETTINGS
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
    monkeypatch.setattr(paths, "repo_root", lambda: tmp_path)
    app = create_app()
    assert app.state.sources.config_path == (tmp_path / paths.LOCAL_CONFIG).resolve()


def test_a_key_the_config_lacks_is_named_by_health_and_the_format_still_answers_while_the_folders_verbs_refuse(tmp_path):
    (tmp_path / "local.yaml").write_text(yaml.safe_dump({"PROCESSED_LAB_DATA": str(tmp_path / "processed")}))
    app = create_app(config_path=tmp_path / "local.yaml")
    manager, config_path = app.state.validation(), app.state.sources.config_path
    problem = f"TRANSFORMED_LAB_DATA is not set in {config_path}"
    health = manager.health(config_path)
    assert health["transformed"] == {"root": None, "exists": False, "problems": [problem], "counts": {}, "manifest": None}
    assert health["processed"]["problems"] == [] and health["environments"]["problems"] == [] and health["config_path"] == str(config_path)
    assert manager.format()["transformed"] == TransformedAccess(tmp_path).schema() and TestClient(app).get("/api/format").status_code == 200
    assert manager.readiness("real", SETTINGS)["totals"]["blocks"] == 0
    assert not hasattr(manager.transformed, "nothing")
    with pytest.raises(Invalid, match=re.escape(problem)):
        manager.transformed.sessions()
