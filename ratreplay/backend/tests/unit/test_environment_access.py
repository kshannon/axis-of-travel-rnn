"""
EnvironmentAccess over a copy of the repository's four environment yaml files: each expands to the geometry the project's builders give, and a broken file is named by health.
"""

import json
import shutil
from pathlib import Path

import pytest
from environments import load_environment

from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.utilities.errors import Invalid, NotFound

REAL = Path(__file__).resolve().parents[4] / "configs" / "environments"
NAMES = ("open_arena", "plus_maze", "triple_t", "triple_t_rot90")
SHAPE = {"name", "kind", "room", "boundary", "walls", "centerline", "reward_sites", "circle", "params"}
COMPARED = ("name", "kind", "room", "boundary", "walls", "centerline", "reward_sites", "params")
BROKEN = "type: circle\nroom: {extent: [1.8, 1.8]}\n"


@pytest.fixture
def folder(tmp_path):
    """
    A copy of the four environment yaml files under tmp_path.
    """
    root = tmp_path / "environments"
    shutil.copytree(REAL, root)
    return root


@pytest.mark.parametrize("name", NAMES)
def test_the_geometry_equals_the_projects_builders_and_is_json_data(folder, name):
    spec = load_environment(name, config_dir=folder)
    geometry = EnvironmentAccess(folder).environment(name)
    assert set(geometry) == SHAPE and json.loads(json.dumps(geometry)) == geometry
    for field in COMPARED:
        assert geometry[field] == getattr(spec, field), field


def test_the_circle_is_given_for_the_open_arena_only(folder):
    access = EnvironmentAccess(folder)
    assert access.environment("open_arena")["circle"] == {"center": [0.9, 0.9], "radius": 0.3}
    assert all(access.environment(name)["circle"] is None for name in NAMES[1:])


def test_a_name_that_is_not_a_yaml_stem_is_not_found_before_any_path_is_formed(folder):
    with pytest.raises(NotFound, match="no environment ../triple_t"):
        EnvironmentAccess(folder).environment("../triple_t")


def test_health_of_the_real_folder_is_clean_with_four_environments():
    health = EnvironmentAccess(REAL).health()
    assert health["root"] == str(REAL) and health["exists"] and health["problems"] == []
    assert health["counts"] == {"environments": 4} and health["manifest"]["modified"]


def test_a_file_that_cannot_be_built_is_named_by_health_and_raises_invalid(folder):
    (folder / "broken.yaml").write_text(BROKEN)
    access = EnvironmentAccess(folder)
    health = access.health()
    assert health["problems"] == ["broken.yaml cannot be built: KeyError 'diameter'"]
    assert health["counts"] == {} and health["manifest"] is None
    with pytest.raises(Invalid, match="broken.yaml"):
        access.environment("broken")


def test_a_root_that_does_not_exist_is_reported(tmp_path):
    assert EnvironmentAccess(tmp_path / "nope").health() == {
        "root": str(tmp_path / "nope"), "exists": False, "problems": [f"{tmp_path / 'nope'} does not exist"], "counts": {}, "manifest": None}
