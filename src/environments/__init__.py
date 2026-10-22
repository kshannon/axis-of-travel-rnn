"""Environments: parametric geometry from the environments section of configs/project.yaml.

    from environments import load_environment
    spec = load_environment("triple_t")   # environments.triple_t in configs/project.yaml

Configs hold parameters, never raw geometry. An entry may name a ``base``
entry and a ``transform`` (rotation), which is how the rotation control is
defined once and derived from the original.
"""

from pathlib import Path

import yaml

from proj_helpers.project import section
from .common import EnvSpec, rotate_spec
from .open_field import build_circle
from .plus_maze import build_plus_maze
from .triple_t import build_triple_t

__all__ = ["EnvSpec", "BUILDERS", "build_environment", "environment_config",
           "list_environments", "load_environment", "rotate_spec"]

BUILDERS = {"triple_t": build_triple_t, "circle": build_circle,
            "plus_maze": build_plus_maze}
SECTION = "environments"
BASE_KEY = "base"


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


def list_environments(project=None) -> list[str]:
    """Names of every environment in the project config, sorted."""
    return sorted(section(SECTION, project))


def environment_config(name, project=None) -> dict:
    """The named entry of the environments section, merged over its base entry when it names one."""
    cfg = section(f"{SECTION}.{name}", project)
    if BASE_KEY not in cfg:
        return cfg
    base = section(f"{SECTION}.{cfg[BASE_KEY]}", project)
    merged = {**base, **{k: v for k, v in cfg.items() if k != BASE_KEY}}
    merged["params"] = {**base.get("params", {}), **cfg.get("params", {})}
    return merged


def load_environment(name_or_path, project=None) -> EnvSpec:
    """Load by name from the project config, or from a single environment yaml when given a path ending in .yaml. This is the entry point experiments use."""
    p = Path(name_or_path)
    if p.suffix == ".yaml":
        return build_environment(yaml.safe_load(p.read_text()), name=p.stem)
    return build_environment(environment_config(p.name, project), name=p.name)
