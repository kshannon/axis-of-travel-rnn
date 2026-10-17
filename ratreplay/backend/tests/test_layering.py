"""
The layering of docs/architecture.md, checked on the imports of every module under ratreplay_api.
"""

import ast
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "ratreplay_api"
UTILITIES = ("arrow", "clock", "contract", "errors")
PROJECT = ("axis_of_travel_rnn", "process_lab_data", "environments", "proj_helpers")

# The modules of ratreplay_api each layer may import, by prefix. Engines may use each other, stores no other store.
ALLOWED = {
    "managers": ("engines", "stores", *UTILITIES),
    "engines": ("engines", *UTILITIES),
    "stores": ("clock", "errors"),
    "routers": ("managers", "routers.deps", "schemas", *UTILITIES),
}
ENGINES_EXTERNAL = ("numpy", *PROJECT, *sys.stdlib_module_names)
PATHS_USER = "data_sources.py"


def imports_of(path):
    """
    The modules a file imports, made absolute, a name of a from import also tried as a module.
    """
    package = ".".join(path.relative_to(PACKAGE.parent).parts[:-1])
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_name("." * node.level + (node.module or ""), package) if node.level else node.module
            found.update([base, *(f"{base}.{alias.name}" for alias in node.names)])
    return found


def within(name, prefixes):
    """
    Whether the module is one of the prefixes or inside one.
    """
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


@pytest.mark.parametrize("layer", ALLOWED)
def test_a_layer_imports_only_the_layers_it_may(layer):
    for path in (PACKAGE / layer).glob("*.py"):
        for name in imports_of(path):
            if name.startswith("ratreplay_api."):
                assert within(name.removeprefix("ratreplay_api."), ALLOWED[layer]), f"{layer}/{path.name} imports {name}"


def test_engines_import_only_numpy_and_the_project_packages():
    for path in (PACKAGE / "engines").glob("*.py"):
        for name in imports_of(path):
            assert name.startswith("ratreplay_api") or within(name, ENGINES_EXTERNAL), f"{path.name} imports {name}"


def test_only_the_data_sources_import_the_paths_helper():
    for path in PACKAGE.rglob("*.py"):
        assert path.name == PATHS_USER or "proj_helpers.paths" not in imports_of(path), f"{path.name} imports proj_helpers.paths"
