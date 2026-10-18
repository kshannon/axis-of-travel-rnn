"""
The layering of docs/architecture.md, checked on the imports of every module under ratreplay_api.
"""

import ast
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "ratreplay_api"
UTILITIES = ("utilities",)
PROJECT = ("axis_of_travel_rnn", "process_lab_data", "environments", "proj_helpers")

# The modules of ratreplay_api each layer may import, by prefix. The old flat engine modules may use each other, stores no
# other store, and environment.py its private builders, the one module of access an access may import.
ALLOWED = {
    "managers": ("contract", "engines", "stores", *UTILITIES),
    "engines": ("engines", *UTILITIES),
    "access": ("access.environment_builders", *UTILITIES),
    "stores": UTILITIES,
    "routers": ("contract", "managers", "routers.deps", "schemas", *UTILITIES),
}
ENGINES_EXTERNAL = ("numpy", *PROJECT, *sys.stdlib_module_names)

# The engines of the rebuild, by their files under ratreplay_api and what each may import from it: utilities and, for a
# package, itself. Engines never call engines. Outside ratreplay_api they use numpy, scipy and the standard library alone.
# The old flat engine modules, every other file of engines, keep the looser rule above until task L deletes them.
NEW_ENGINES = {
    "engines/trajectory/**/*.py": ("engines.trajectory", *UTILITIES),
    "engines/generator.py": UTILITIES,
}
NEW_ENGINES_EXTERNAL = ("numpy", "scipy", *sys.stdlib_module_names)
ACCESS_EXTERNAL = ("numpy", "pyarrow", "yaml", *sys.stdlib_module_names)
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


def modules_of(layer):
    """
    The top level files of a layer's folder, for engines the old flat modules alone since the new ones have their own rule.
    """
    return [path for path in (PACKAGE / layer).glob("*.py") if not (layer == "engines" and path.name == "generator.py")]


def within(name, prefixes):
    """
    Whether the module is one of the prefixes or inside one.
    """
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)


def may_import(name, internal, external):
    """
    Whether a name is inside the ratreplay_api prefixes in internal, or for any other module inside the prefixes in external.
    """
    if name.startswith("ratreplay_api."):
        return within(name.removeprefix("ratreplay_api."), internal)
    return within(name, external)


@pytest.mark.parametrize("layer", ALLOWED)
def test_a_layer_imports_only_the_layers_it_may(layer):
    for path in modules_of(layer):
        for name in imports_of(path):
            if name.startswith("ratreplay_api."):
                assert within(name.removeprefix("ratreplay_api."), ALLOWED[layer]), f"{layer}/{path.name} imports {name}"


def test_the_old_flat_engines_import_only_numpy_and_the_project_packages_until_task_l():
    for path in modules_of("engines"):
        for name in imports_of(path):
            assert name.startswith("ratreplay_api") or within(name, ENGINES_EXTERNAL), f"{path.name} imports {name}"


@pytest.mark.parametrize("pattern", NEW_ENGINES)
def test_the_new_engines_import_only_utilities_themselves_numpy_scipy_and_the_standard_library(pattern):
    files = list(PACKAGE.glob(pattern))
    assert files, f"no file matches {pattern}"
    for path in files:
        for name in imports_of(path) - {"ratreplay_api"}:
            assert may_import(name, NEW_ENGINES[pattern], NEW_ENGINES_EXTERNAL), f"{path.relative_to(PACKAGE)} imports {name}"


def test_access_imports_only_numpy_pyarrow_yaml_and_the_standard_library_never_a_project_package():
    for path in (PACKAGE / "access").glob("*.py"):
        for name in imports_of(path):
            assert name.startswith("ratreplay_api") or within(name, ACCESS_EXTERNAL), f"access/{path.name} imports {name}"


def test_an_access_imports_no_other_access_except_environment_its_private_builders():
    for path in (PACKAGE / "access").glob("*.py"):
        allowed = ("ratreplay_api.access.environment_builders",) if path.name == "environment.py" else ()
        for name in imports_of(path):
            assert not name.startswith("ratreplay_api.access.") or within(name, allowed), f"access/{path.name} imports {name}"


def test_only_the_data_sources_import_the_paths_helper():
    for path in PACKAGE.rglob("*.py"):
        assert path.name == PATHS_USER or "proj_helpers.paths" not in imports_of(path), f"{path.name} imports proj_helpers.paths"


def test_utilities_import_nothing_from_the_package_outside_utilities():
    for path in (PACKAGE / "utilities").glob("*.py"):
        for name in imports_of(path):
            assert not name.startswith("ratreplay_api") or within(name, ("ratreplay_api.utilities",)), f"utilities/{path.name} imports {name}"
