"""
Fixtures for the backend tests: the synthetic folders under tmp_path and an app whose registry lives there too.
"""

import pytest
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
def client(tmp_path):
    """
    A test client on an app with its registry and its window settings file under tmp_path.
    """
    return TestClient(create_app(registry_path=tmp_path / "sources.json", settings_path=tmp_path / "lab_blocks.yaml"))


@pytest.fixture
def attached(client, transformed, processed):
    """
    The ids of the synthetic transformed source, paired with the processed folder, and of the processed source, both attached.
    """
    paired = client.post("/api/sources", json={"path": str(transformed), "kind": "transformed", "processed_path": str(processed)})
    alone = client.post("/api/sources", json={"path": str(processed), "kind": "processed"})
    return paired.json()["id"], alone.json()["id"]
