"""
The project config, configs/project.yaml: its environments, blueprints, EDA defaults and analysis thresholds by dotted name.
"""

import copy
import functools
from pathlib import Path

import yaml

from .paths import repo_root

PROJECT_CONFIG = "configs/project.yaml"


@functools.cache
def project_config():
    """
    The project config as a dict, the file read once per process.
    """
    return yaml.safe_load((repo_root() / PROJECT_CONFIG).read_text())


def section(name, path=None):
    """
    A copy of the value at a dotted name such as blueprints.blocks_v1, from the project config or the yaml at path, a KeyError naming the keys available where it is missing.
    """
    found = project_config() if path is None else yaml.safe_load(Path(path).read_text())
    for key in name.split("."):
        if not isinstance(found, dict) or key not in found:
            available = ", ".join(sorted(found)) if isinstance(found, dict) else "none"
            raise KeyError(f"no {name} in the project config, {key} is not one of: {available}")
        found = found[key]
    return copy.deepcopy(found)
