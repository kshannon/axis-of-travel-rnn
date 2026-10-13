"""
The artifact store: resolution order, the marker, the layout and the scan.
"""

from pathlib import Path

import pytest
import yaml

from proj_helpers.paths import repo_root
from axis_of_travel_rnn.store import (ENV_VAR, KINDS, STORE_VERSION, Store,
                                      StoreError, open_store, resolve_store)


def _artifact(store: Store, kind: str, name: str, declared_id: str) -> None:
    d = store.kind_dir(kind) / name
    d.mkdir()
    (d / "manifest.yaml").write_text(f"id: {declared_id}\n")


def test_resolution_order_is_flag_then_env_then_local_then_default(tmp_path: Path):
    flag, env, local = tmp_path / "flag", tmp_path / "env", tmp_path / "local.yaml"
    local.write_text(f"STORE: {tmp_path / 'from-file'}\n")
    chosen = resolve_store(str(flag), env={ENV_VAR: str(env)}, local_file=local)
    assert (chosen.root, chosen.source) == (flag, "flag")
    chosen = resolve_store(None, env={ENV_VAR: str(env)}, local_file=local)
    assert (chosen.root, chosen.source) == (env, "env")
    chosen = resolve_store(None, env={}, local_file=local)
    assert (chosen.root, chosen.source) == (tmp_path / "from-file", "local")
    chosen = resolve_store(None, env={}, local_file=tmp_path / "absent.yaml")
    assert (chosen.root, chosen.source) == (repo_root() / "artifacts", "default")


def test_init_creates_the_layout_and_the_marker(tmp_path: Path):
    store = Store(tmp_path / "s", "flag")
    marker = store.init()
    assert all(store.kind_dir(kind).is_dir() for kind in KINDS)
    assert set(marker) == {"store_version", "created", "hostname", "tool_version"}
    assert marker["store_version"] == STORE_VERSION
    assert store.init() == marker


def test_open_store_requires_a_marker_and_says_how_the_path_was_chosen(tmp_path: Path):
    missing = tmp_path / "missing"
    with pytest.raises(StoreError) as caught:
        open_store(str(missing), env={})
    message = str(caught.value)
    assert str(missing) in message and "store init" in message
    assert "--store" in message and "drive" in message

    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(StoreError, match="store init"):
        open_store(None, env={ENV_VAR: str(bare)})

    with pytest.raises(StoreError) as caught:
        Store(tmp_path / "default", "default").read_marker()
    message = str(caught.value)
    assert "default" in message and ENV_VAR in message and "drive" not in message


def test_open_store_refuses_a_marker_from_a_newer_tool(tmp_path: Path):
    store = Store(tmp_path / "s", "flag")
    store.init()
    store.marker.write_text(yaml.safe_dump({"store_version": STORE_VERSION + 1}))
    with pytest.raises(StoreError, match="store_version"):
        open_store(str(store.root), env={})


def test_open_store_reports_an_unreadable_marker(tmp_path: Path):
    store = Store(tmp_path / "s", "flag")
    store.init()
    store.marker.chmod(0)
    with pytest.raises(StoreError, match="cannot read"):
        open_store(str(store.root), env={})


def test_counts_include_only_valid_artifacts(tmp_path: Path):
    store = Store(tmp_path / "s", "flag")
    store.init()
    _artifact(store, "datasets", "ds_0001", "ds_0001")
    _artifact(store, "datasets", "ds_0002", "ds_0009")
    (store.kind_dir("models") / "scratch").mkdir()
    assert store.counts() == {"datasets": 1, "models": 0, "experiments": 0}


def test_artifacts_skips_unmarked_directories_and_refuses_a_wrong_id(tmp_path: Path):
    store = Store(tmp_path / "s", "flag")
    store.init()
    _artifact(store, "datasets", "ds_0001", "ds_0001")
    (store.kind_dir("datasets") / "scratch").mkdir()
    assert [a.id for a in store.artifacts("datasets")] == ["ds_0001"]

    _artifact(store, "datasets", "ds_0002", "ds_0009")
    with pytest.raises(StoreError, match="ds_0009"):
        store.artifacts("datasets")
