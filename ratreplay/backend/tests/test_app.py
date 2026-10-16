"""
The app: the format route, the error body, and the frontend at / once built.
"""

from fastapi.testclient import TestClient

from ratreplay_api import app as app_module
from ratreplay_api.app import create_app


def test_format_route_returns_the_contract(client):
    response = client.get("/api/format")
    assert response.status_code == 200
    assert {"version", "transformed", "processed"} <= response.json().keys()


def test_unknown_route_returns_an_error_body(client):
    response = client.get("/api/nothing")
    assert response.status_code == 404
    assert response.json() == {"error": "Not Found"}


def test_built_frontend_is_served_at_root_and_the_routes_still_win(tmp_path, monkeypatch):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<div id=app></div>")
    monkeypatch.setattr(app_module, "FRONTEND_DIST", tmp_path / "dist")
    client = TestClient(create_app(registry_path=tmp_path / "sources.json"))
    assert client.get("/").text == "<div id=app></div>"
    assert client.get("/api/format").status_code == 200
