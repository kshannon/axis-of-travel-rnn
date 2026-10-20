"""
The layering of docs/architecture.md (Static architecture), checked on the imports of every module under ratreplay_api.
"""

import ast
import sys
from importlib.util import resolve_name
from pathlib import Path

ROOT = "ratreplay_api"
PACKAGE = Path(__file__).resolve().parents[2] / ROOT
UTILITIES = ("utilities",)
STDLIB = tuple(sys.stdlib_module_names)
EVERYTHING = None

# The chart, one row per file or folder under ratreplay_api, the first row a file falls under being its rule: the modules of
# ratreplay_api it may import by prefix and the outside packages it may import by prefix. A project package (axis_of_travel_rnn,
# environments, proj_helpers) is in no list, so none can be imported.
# Routers call managers, read the request models and share routers.deps, never each other. Managers call engines and accesses.
# An engine calls its own package and utilities, never another engine, an access calls utilities, never another access, and
# environment.py its private builders. Utilities call utilities. The request models read two constants, the engine's default
# settings and the access's edit fields. The composition root builds the lot, and the entry point starts it.
LAYERS = [
    ("routers", ("managers", "schemas", "routers.deps", *UTILITIES), ("fastapi", *STDLIB)),
    ("schemas.py", ("access.processed", "engines.trajectory", *UTILITIES), ("pydantic", *STDLIB)),
    ("managers", ("engines", "access", *UTILITIES), STDLIB),
    ("engines/trajectory", ("engines.trajectory", *UTILITIES), ("numpy", "scipy", *STDLIB)),
    ("engines", UTILITIES, ("numpy", "scipy", *STDLIB)),
    ("access/environment.py", ("access.environment_builders", *UTILITIES), ("numpy", "pyarrow", "yaml", *STDLIB)),
    ("access", UTILITIES, ("numpy", "pyarrow", "yaml", *STDLIB)),
    ("utilities", UTILITIES, ("fastapi", "pyarrow", "yaml", *STDLIB)),
    ("app.py", EVERYTHING, ("fastapi", "starlette", *STDLIB)),
    ("__main__.py", ("app",), ("uvicorn", *STDLIB)),
    ("__init__.py", (), ()),
]

# The private helper modules of a component, by module prefix, and the files that may import them: the component's own.
PRIVATE = {"engines.trajectory.": "engines/trajectory", "access.environment_builders": "access/environment.py"}
MODULES = sorted(PACKAGE.rglob("*.py"))


def is_module(name):
    """
    Whether the dotted name may be a module: any outside name, and a name of ratreplay_api only when it is a module or a package of it.
    """
    if not name.startswith(f"{ROOT}."):
        return True
    path = PACKAGE / name.removeprefix(f"{ROOT}.").replace(".", "/")
    return path.is_dir() or path.with_suffix(".py").is_file()


def imports_of(path):
    """
    The modules a file imports, made absolute, as two sets: those of ratreplay_api named relative to it, and the outside ones. A name of a from import counts when it is a module.
    """
    package = ".".join(path.relative_to(PACKAGE.parent).parts[:-1])
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_name("." * node.level + (node.module or ""), package) if node.level else node.module
            found.update([base, *(name for name in (f"{base}.{alias.name}" for alias in node.names) if is_module(name))])
    inside = {name.removeprefix(f"{ROOT}.") for name in found if name.startswith(f"{ROOT}.")}
    return inside, {name for name in found if name != ROOT and not name.startswith(f"{ROOT}.")}


def within(name, prefixes):
    """
    Whether the module is one of the prefixes or inside one.
    """
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


def under(relative, row):
    """
    Whether the file, relative to ratreplay_api, is the row's file or inside its folder.
    """
    return relative == row or relative.startswith(f"{row}/")


def layer_of(path):
    """
    The row of LAYERS the file falls under, none when no row covers it.
    """
    relative = path.relative_to(PACKAGE).as_posix()
    return next((layer for layer in LAYERS if under(relative, layer[0])), None)



def test_every_module_of_the_package_falls_under_a_layer_and_every_layer_covers_a_module():
    assert [path for path in MODULES if layer_of(path) is None] == []
    assert {layer_of(path)[0] for path in MODULES} == {row[0] for row in LAYERS}


def test_every_module_imports_only_what_its_layer_may():
    broken = []
    for path in [path for path in MODULES if layer_of(path)]:
        _, internal, external = layer_of(path)
        inside, outside = imports_of(path)
        broken += [f"{path.relative_to(PACKAGE)} imports {name}" for name in sorted(inside) if internal is not EVERYTHING and not within(name, internal)]
        broken += [f"{path.relative_to(PACKAGE)} imports {name}" for name in sorted(outside) if not within(name, external)]
    assert broken == []


def test_a_private_helper_module_is_imported_by_its_component_alone():
    broken = []
    for path in MODULES:
        relative = path.relative_to(PACKAGE).as_posix()
        broken += [f"{relative} imports {name}, private to {owner}" for name in sorted(imports_of(path)[0]) for prefix, owner in PRIVATE.items()
                   if name.startswith(prefix) and not under(relative, owner)]
    assert broken == []
