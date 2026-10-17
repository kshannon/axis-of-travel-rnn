"""
Fixtures for the backend tests: the synthetic folders under tmp_path and an app whose local.yaml there names them, never the real configs/local.yaml.
"""

import pytest
import yaml
from fastapi.testclient import TestClient

from fixtures import write_processed, write_transformed
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
def processed(tmp_path, transformed):
    """
    The processed folder the processor builds from the synthetic transformed one.
    """
    root = tmp_path / "processed"
    write_processed(transformed, root)
    return root


@pytest.fixture
def client_on(tmp_path):
    """
    A function making a test client on an app whose local.yaml under tmp_path holds the given config and whose window settings file is there too.
    """
    def make(config):
        (tmp_path / "local.yaml").write_text(yaml.safe_dump(config))
        return TestClient(create_app(config_path=tmp_path / "local.yaml", settings_path=tmp_path / "lab_blocks.yaml"))
    return make


@pytest.fixture
def client(client_on, transformed, processed):
    """
    A test client on an app whose config names the synthetic folders.
    """
    return client_on({"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(processed)})
