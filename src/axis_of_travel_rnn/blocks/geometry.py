"""
The geometry the engine registers a session against: an environment yaml under configs/environments built into plain data, with a person's start offset laid over the yaml's.
"""

from dataclasses import asdict

import yaml

from environments import build_environment
from proj_helpers.paths import environments_dir

# A definition is a yaml file named for its environment. A file with a base is merged over the base. The start offset
# applies to the one type with a start site up a stem.
YAML = ".yaml"
BASE_KEY = "base"
START_OFFSET = "start_offset"
OFFSET_TYPE = "triple_t"


def read_config(name, root):
    """
    The environment's yaml as a dict, its base file's params and keys merged under its own when it names a base.
    """
    config = yaml.safe_load((root / f"{name}{YAML}").read_text())
    if BASE_KEY not in config:
        return config
    base = yaml.safe_load((root / f"{config[BASE_KEY]}{YAML}").read_text())
    own = {key: value for key, value in config.items() if key != BASE_KEY}
    return {**base, **own, "params": {**base.get("params", {}), **config.get("params", {})}}


def geometry(name, start_offset_m=None, root=None):
    """
    The environment's geometry as a dict (room, boundary, centerline, reward sites, walls, params), built with this start offset in metres in place of the yaml's when one is given and the type has a start site.
    """
    config = read_config(name, environments_dir() if root is None else root)
    if start_offset_m is not None and config.get("type") == OFFSET_TYPE:
        config = {**config, "params": {**config.get("params", {}), START_OFFSET: start_offset_m}}
    return asdict(build_environment(config, name=name))


def geometries(epochs, rules, start_offset_m=None, root=None):
    """
    The geometry by name of the environments of the epochs of the rules' kinds, what session and blocks take.
    """
    return {e["environment"]: geometry(e["environment"], start_offset_m, root) for e in epochs if e["epoch"] in rules["epochs"]}
