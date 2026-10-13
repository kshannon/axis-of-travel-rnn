import os
from collections.abc import Mapping
from pathlib import Path

import yaml

LOCAL_CONFIG = "configs/local.yaml"


def repo_root() -> Path:
    """The checkout containing this package (src/proj_helpers/paths.py)."""
    return Path(__file__).resolve().parents[2]


def configs_dir() -> Path:
    return repo_root() / "configs"


def environments_dir() -> Path:
    return configs_dir() / "environments"


def local_config(path: Path | None = None) -> dict:
    """
    The machine-local paths file as a dict; empty when absent or not a mapping.
    """
    path = repo_root() / LOCAL_CONFIG if path is None else Path(path)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def resolve_path(flag: str | None, *, env_var: str, key: str, default: Path,
                 env: Mapping[str, str] | None = None,
                 local_file: Path | None = None) -> tuple[Path, str]:
    """
    A machine-local path and how it was chosen: flag, env, local or default.
    """
    env = os.environ if env is None else env
    if flag:
        return Path(flag).expanduser(), "flag"
    if env.get(env_var):
        return Path(env[env_var]).expanduser(), "env"
    local = local_config(local_file).get(key)
    if local:
        return Path(str(local)).expanduser(), "local"
    return Path(default), "default"
