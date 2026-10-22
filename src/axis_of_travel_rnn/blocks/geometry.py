"""
The geometry the engine registers a session against: an entry of the environments section of configs/project.yaml built into plain data, with a person's start offset laid over the entry's.
"""

from dataclasses import asdict

from environments import build_environment, environment_config

# The start offset applies to the one type with a start site up a stem.
START_OFFSET = "start_offset"
OFFSET_TYPE = "triple_t"


def geometry(name, start_offset_m=None, project=None):
    """
    The environment's geometry as a dict (room, boundary, centerline, reward sites, walls, params), built with this start offset in metres in place of the entry's when one is given and the type has a start site.
    """
    config = environment_config(name, project)
    if start_offset_m is not None and config.get("type") == OFFSET_TYPE:
        config = {**config, "params": {**config.get("params", {}), START_OFFSET: start_offset_m}}
    return asdict(build_environment(config, name=name))


def geometries(epochs, rules, start_offset_m=None, project=None):
    """
    The geometry by name of the environments of the epochs of the rules' kinds, what session and blocks take.
    """
    return {e["environment"]: geometry(e["environment"], start_offset_m, project) for e in epochs if e["epoch"] in rules["epochs"]}
