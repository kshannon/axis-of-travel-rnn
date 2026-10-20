"""
EnvironmentAccess over a copy of the repository's four environment yaml files: each expands to the geometry the project's builders give, and a broken file is named by health.
"""

import json
import math
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
START_OFFSET, TOLERANCE = 0.15, 1e-6


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


def test_a_start_offset_lifts_the_start_up_the_stem_in_both_builders_and_leaves_the_envelope_as_it_was(folder):
    (folder / "lifted.yaml").write_text((folder / "triple_t.yaml").read_text() + f"  start_offset: {START_OFFSET}\n")
    spec = load_environment("lifted", config_dir=folder)
    access = EnvironmentAccess(folder)
    lifted, plain = access.environment("lifted"), access.environment("triple_t")
    for field in COMPARED:
        assert lifted[field] == getattr(spec, field), field

    def bottom(geometry):
        return next(s for s in geometry["centerline"] if s["name"] == "bottom_w")["p0"][1]

    def outline(geometry):
        points = [p for wall in geometry["walls"] for p in wall]
        return [max(c) - min(c) for c in zip(*points)]

    assert plain["reward_sites"]["start"][1] == bottom(plain)
    assert lifted["reward_sites"]["start"][1] - bottom(lifted) == pytest.approx(START_OFFSET, abs=TOLERANCE)
    assert outline(lifted) == pytest.approx(outline(plain), abs=TOLERANCE)
    assert outline(lifted) == pytest.approx(lifted["params"]["envelope"], abs=TOLERANCE)


def test_a_start_offset_given_lifts_the_start_up_the_stem_of_the_track_and_its_rotation_and_none_leaves_the_yaml_as_it_was(folder):
    before = (folder / "triple_t.yaml").read_text()
    access = EnvironmentAccess(folder)

    def start_to_foot(geometry):
        foot = next(s for s in geometry["centerline"] if s["name"] == "bottom_w")["p1"]
        return math.dist(geometry["reward_sites"]["start"], foot)

    for name in ("triple_t", "triple_t_rot90"):
        plain, lifted = access.environment(name), access.environment(name, START_OFFSET)
        assert access.environment(name, None) == plain and start_to_foot(plain) == pytest.approx(0.0, abs=TOLERANCE)
        assert start_to_foot(lifted) == pytest.approx(START_OFFSET, abs=TOLERANCE) and lifted["params"]["start_offset"] == START_OFFSET
    assert access.environment("open_arena", START_OFFSET) == access.environment("open_arena")
    assert (folder / "triple_t.yaml").read_text() == before


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
