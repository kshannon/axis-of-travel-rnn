"""
Fixtures for the backend tests: the synthetic folders under tmp_path and an app whose local.yaml there names them, never the real configs/local.yaml.
"""

import shutil

import pytest
import yaml
from fastapi.testclient import TestClient

from fixtures import write_transformed
from ratreplay_api import app as app_module
from ratreplay_api.app import create_app


@pytest.fixture
def transformed(tmp_path):
    """
    A synthetic transformed folder.
    """
    root = tmp_path / "transformed"
    write_transformed(root)
    return root


@pytest.fixture
def processed(tmp_path):
    """
    An empty processed folder, what the tool finds before the first save.
    """
    root = tmp_path / "processed"
    root.mkdir()
    return root


@pytest.fixture
def synthetic(tmp_path):
    """
    An empty synthetic folder, what the tool finds before the first set is generated.
    """
    root = tmp_path / "synthetic"
    root.mkdir()
    return root


@pytest.fixture
def environments(tmp_path, monkeypatch):
    """
    A copy of the repository's environment yaml files, which the app reads in place of the originals.
    """
    root = tmp_path / "environments"
    shutil.copytree(app_module.ENVIRONMENTS, root)
    monkeypatch.setattr(app_module, "ENVIRONMENTS", root)
    return root


@pytest.fixture
def client_on(tmp_path, environments):
    """
    A function making a test client on an app whose local.yaml under tmp_path holds the given config.
    """
    def make(config):
        (tmp_path / "local.yaml").write_text(yaml.safe_dump(config))
        return TestClient(create_app(config_path=tmp_path / "local.yaml"))
    return make


@pytest.fixture
def client(client_on, transformed, processed, synthetic):
    """
    A test client on an app whose config names the synthetic transformed folder and the empty processed and synthetic ones.
    """
    return client_on({"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(processed), "SYNTHETIC_DATA": str(synthetic)})
