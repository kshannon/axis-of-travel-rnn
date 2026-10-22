"""Environments: parametric geometry loaded from configs/environments/.

    from environments import load_environment
    spec = load_environment("triple_t")   # configs/environments/triple_t.yaml

Configs hold parameters, never raw geometry. A config may name a ``base``
config and a ``transform`` (rotation), which is how the rotation control is
defined once and derived from the original.
"""

from pathlib import Path

import yaml

from proj_helpers.paths import environments_dir
from .common import EnvSpec, rotate_spec
from .open_field import build_circle
from .plus_maze import build_plus_maze
from .triple_t import build_triple_t

__all__ = ["EnvSpec", "BUILDERS", "build_environment", "list_environments",
           "load_environment", "rotate_spec"]

BUILDERS = {"triple_t": build_triple_t, "circle": build_circle,
            "plus_maze": build_plus_maze}


def build_environment(cfg: dict, name=None) -> EnvSpec:
    kind = cfg["type"]
    if kind not in BUILDERS:
        raise ValueError(f"unknown environment type {kind!r}; "
                         f"known: {sorted(BUILDERS)}")
    spec = BUILDERS[kind](cfg.get("params", {}), cfg["room"]["extent"],
                          name=name or kind)
    if cfg.get("transform", {}).get("rotate_deg"):
        spec = rotate_spec(spec, cfg["transform"]["rotate_deg"], name=name)
    return spec


def _config_dir(config_dir) -> Path:
    return Path(config_dir) if config_dir is not None else environments_dir()


def list_environments(config_dir=None) -> list[str]:
    """Names of every environment config, sorted."""
    return sorted(p.stem for p in _config_dir(config_dir).glob("*.yaml"))


def load_environment(name_or_path, config_dir=None) -> EnvSpec:
    """Load by config path or bare name ('triple_t' resolves against
    configs/environments/). This is the entry point experiments use."""
    p = Path(name_or_path)
    if p.suffix != ".yaml":
        p = _config_dir(config_dir) / f"{p.name}.yaml"
    if not p.is_file():
        raise FileNotFoundError(
            f"no environment config {name_or_path!r} at {p}; "
            f"available: {list_environments(p.parent)}")
    cfg = yaml.safe_load(p.read_text())
    if "base" in cfg:
        base = yaml.safe_load((p.parent / f"{cfg['base']}.yaml").read_text())
        merged = {**base, **{k: v for k, v in cfg.items() if k != "base"}}
        merged["params"] = {**base.get("params", {}), **cfg.get("params", {})}
        cfg = merged
    return build_environment(cfg, name=p.stem)
