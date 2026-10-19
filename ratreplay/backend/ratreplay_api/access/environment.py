"""
The environment definitions: a folder of yaml files of parameters, expanded here into the geometry in the room frame in metres.
"""

import yaml

from ..utilities import paths
from ..utilities.errors import Invalid, NotFound
from .environment_builders import BUILDERS, rotated

# A definition is a yaml file named for its environment. A file with a base is merged over the base and turned by its transform.
YAML = ".yaml"
BASE_KEY = "base"
START_OFFSET = "start_offset"


def read_config(path):
    """
    The yaml file as a dict, Invalid naming the file when it does not parse or is not a mapping.
    """
    try:
        config = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise Invalid(f"{path.name} is not valid yaml") from error
    if not isinstance(config, dict):
        raise Invalid(f"{path.name} is not a mapping of keys")
    return config


def merged(config, base):
    """
    The config laid over its base file's, the params merged key by key and the base key dropped.
    """
    own = {key: value for key, value in config.items() if key != BASE_KEY}
    return {**base, **own, "params": {**base.get("params", {}), **config.get("params", {})}}


def with_start_offset(config, start_offset):
    """
    The config with the person's start offset in its params in place of the yaml's, unchanged when none is given or the type has no start site up a stem.
    """
    if start_offset is None or config.get("type") != "triple_t":
        return config
    return {**config, "params": {**config.get("params", {}), START_OFFSET: start_offset}}


def build(name, config):
    """
    The geometry a resolved config describes, turned when it carries a transform, Invalid naming the file when it cannot be built.
    """
    kind = config.get("type")
    if kind not in BUILDERS:
        raise Invalid(f"{name}{YAML} names unknown type {kind}, expected one of {', '.join(sorted(BUILDERS))}")
    try:
        geometry = BUILDERS[kind](config.get("params", {}), config["room"]["extent"], name)
    except (KeyError, TypeError, ValueError) as error:
        raise Invalid(f"{name}{YAML} cannot be built: {type(error).__name__} {error}") from error
    degrees = config.get("transform", {}).get("rotate_deg")
    return rotated(geometry, degrees, name) if degrees else geometry


def circle_of(geometry):
    """
    The centre and radius of a circle environment for the browser to draw, none for any other kind.
    """
    if geometry["kind"] != "circle":
        return None
    return {"center": [geometry["room"][0] / 2, geometry["room"][1] / 2], "radius": geometry["params"]["diameter"] / 2}


class EnvironmentAccess:
    """
    The environment yaml files in the folder at root, each read as the geometry it describes.
    """

    def __init__(self, root):
        self.root = root

    def environments(self):
        """
        The names of the environments, the stems of the yaml files, sorted.
        """
        return sorted(path.stem for path in self.root.glob(f"*{YAML}"))

    def environment(self, name, start_offset=None):
        """
        One environment's geometry as json data, a base and transform resolved, built with this start offset in metres in place of the yaml's when one is given, NotFound for an unknown name, Invalid for a file that cannot be built.
        """
        if name not in self.environments():
            raise NotFound(f"no environment {name}")
        return self._geometry(name, start_offset)

    def health(self):
        """
        The folder's root, whether it exists, which files cannot be built, and when whole its count and when it last changed.
        """
        exists = self.root.is_dir()
        problems = self._problems() if exists else [f"{self.root} does not exist"]
        health = {"root": str(self.root), "exists": exists, "problems": problems, "counts": {}, "manifest": None}
        if problems:
            return health
        return {**health, "counts": {"environments": len(self.environments())}, "manifest": {"modified": paths.newest_mtime(self.root)}}

    def _geometry(self, name, start_offset=None):
        """
        The geometry of the named file with the circle the browser draws, its base file read first when it names one, the start offset laid over the merged params.
        """
        config = read_config(self.root / f"{name}{YAML}")
        if BASE_KEY in config:
            if config[BASE_KEY] not in self.environments():
                raise Invalid(f"{name}{YAML} names missing base {config[BASE_KEY]}")
            config = merged(config, read_config(self.root / f"{config[BASE_KEY]}{YAML}"))
        geometry = build(name, with_start_offset(config, start_offset))
        return {**geometry, "circle": circle_of(geometry)}

    def _problems(self):
        """
        The files that do not parse, name an unknown type or a missing base or cannot be built, or that the folder holds none.
        """
        names = self.environments()
        if not names:
            return [f"{self.root} holds no {YAML} files"]
        problems = []
        for name in names:
            try:
                self._geometry(name)
            except Invalid as error:
                problems.append(str(error))
        return problems
