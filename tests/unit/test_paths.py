"""
Machine-local paths: flag, then environment, then configs/local.yaml, then default.
"""

from pathlib import Path

from proj_helpers.paths import resolve_path


def test_resolution_order_is_flag_env_local_default(tmp_path: Path):
    local = tmp_path / "local.yaml"
    local.write_text("RAW_DATA: /drive/raw\n")
    default = tmp_path / "fallback"
    args = dict(env_var="X_RAW", key="RAW_DATA", default=default, local_file=local)

    assert resolve_path("/flag", env={"X_RAW": "/env"}, **args) == (Path("/flag"),
                                                                      "flag")
    assert resolve_path(None, env={"X_RAW": "/env"}, **args) == (Path("/env"), "env")
    assert resolve_path(None, env={}, **args) == (Path("/drive/raw"), "local")
    local.unlink()
    assert resolve_path(None, env={}, **args) == (default, "default")


def test_local_file_without_the_key_or_malformed_falls_through(tmp_path: Path):
    local = tmp_path / "local.yaml"
    default = tmp_path / "fallback"
    local.write_text("STORE: /drive/store\n")
    assert resolve_path(None, env={}, env_var="X", key="RAW_DATA", default=default,
                        local_file=local)[1] == "default"
    local.write_text("- not\n- a mapping\n")
    assert resolve_path(None, env={}, env_var="X", key="STORE", default=default,
                        local_file=local)[1] == "default"
