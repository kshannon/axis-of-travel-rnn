"""
SyntheticAccess over small hand made blocks: a set is written whole and once, its blocks, provenance and guesses read back as written, delete removes it and health names what is wrong.
"""

import numpy as np
import pytest

from ratreplay_api.access.synthetic import SyntheticAccess
from ratreplay_api.utilities import tables
from ratreplay_api.utilities.blocks import BLOCK_SCHEMA, BLOCKS_CSV_SCHEMA
from ratreplay_api.utilities.errors import Invalid, NotFound

SET = "syn_20261019_120000_7"
FRAMES = 120
FLOATS = ("t", "x", "y", "heading", "speed", "turn_rate")
BOOLS = ("heading_filled", "heading_held", "filled_front", "filled_back", "clean")
INTS = {"n_lights": np.int8, "trip": np.int32, "run": np.int32, "path_id": np.int16}
CELLS = {"string": "text", "int64": 1, "double": 0.5}
PROVENANCE = {"set_id": SET, "created_at": "2026-10-19T12:00:00+00:00", "created_by": "kyle", "sources": ["NS14_rec1_20150101_001"],
              "environments": {"arena": "circle_1m", "track": "triple_t"}, "camera": {"rate_hz": 60, "max_gap": 30}, "seed": 7,
              "length_s": {"arena": 60.0, "track": 120.0}, "rules": {"MIN_BLOCK_S": 10}, "settings": {"window_s": 40.0}, "code_version": "abc1234",
              "generator": {"version": 1}, "recipe_real": {"track": {"counts": {"blocks": 1}}}, "recipe_synthetic": {"track": {"counts": {"blocks": 1}}},
              "warnings": [], "failed": []}
GUESS = {"at": "2026-10-19T12:30:00+00:00", "by": "kyle", "pair_id": "p1", "real_block": "NS14_rec1_20150101_001_track_1",
         "synthetic_block": f"{SET}_track_1", "kind": "track", "guessed_real": f"{SET}_track_1", "correct": False}


def make_block(kind, first):
    """
    A hand made block of the set starting at the frame: its index row and its arrays in the block schema's dtypes.
    """
    rng = np.random.default_rng(first)
    arrays = {"frame": np.arange(first, first + FRAMES, dtype=np.int32), "phase": np.array(["outbound", "dwell"] * (FRAMES // 2))}
    arrays.update({name: rng.random(FRAMES) for name in FLOATS})
    arrays.update({name: rng.random(FRAMES) > 0.5 for name in BOOLS})
    arrays.update({name: rng.integers(0, 3, FRAMES).astype(dtype) for name, dtype in INTS.items()})
    row = {field.name: CELLS[str(field.type)] for field in BLOCKS_CSV_SCHEMA}
    row.update(block_id=f"{SET}_{kind}_{first}", session_id=SET, subject_id="synthetic", date="2026-10-19", kind=kind,
               frame_start=first, frame_end=first + FRAMES - 1, n_frames=FRAMES)
    return {"row": row, "arrays": arrays}


def files_of(root):
    """
    Every file under the folder, relative to it.
    """
    return sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())


@pytest.fixture
def access(tmp_path):
    """
    A SyntheticAccess over a folder that does not exist yet.
    """
    return SyntheticAccess(tmp_path / "synthetic")


@pytest.fixture
def written(access):
    """
    The access after one set of two blocks was written.
    """
    access.write_set(SET, [make_block("arena", 1), make_block("track", 1000)], PROVENANCE)
    return access


def test_a_set_is_listed_and_its_blocks_and_provenance_read_back_as_written(access):
    blocks = [make_block("arena", 1), make_block("track", 1000)]
    assert access.sets() == [] and access.find_block(f"{SET}_track_1000") is None
    assert access.write_set(SET, blocks, PROVENANCE) == {"blocks": 2, "folder": f"sets/{SET}"}
    assert access.sets() == [SET] and access.set(SET) == PROVENANCE
    assert access.blocks(SET) == [block["row"] for block in blocks]
    found = access.block(SET, f"{SET}_track_1000")
    assert found["row"] == blocks[1]["row"] and set(found["arrays"]) == set(BLOCK_SCHEMA.names)
    assert all(list(found["arrays"][name]) == list(blocks[1]["arrays"][name]) for name in BLOCK_SCHEMA.names)
    assert access.find_block(f"{SET}_track_1000") == SET and access.find_block("nope") is None
    assert files_of(access.root) == [f"sets/{SET}/blocks.csv", f"sets/{SET}/blocks/{SET}_arena_1.parquet", f"sets/{SET}/blocks/{SET}_track_1000.parquet",
                                     f"sets/{SET}/provenance.json"]
    with pytest.raises(NotFound, match="no set other"):
        access.set("other")
    with pytest.raises(NotFound, match=f"no block nope in set {SET}"):
        access.block(SET, "nope")


def test_a_second_write_of_the_same_set_is_refused_and_leaves_it_as_it_was(written):
    before = {name: (written.root / name).read_bytes() for name in files_of(written.root)}
    with pytest.raises(Invalid, match=f"set {SET} exists"):
        written.write_set(SET, [make_block("track", 5000)], {**PROVENANCE, "seed": 8})
    assert {name: (written.root / name).read_bytes() for name in files_of(written.root)} == before and written.set(SET)["seed"] == 7


def test_a_set_that_breaks_the_format_is_refused_and_writes_nothing(access):
    stray = make_block("track", 1)
    stray["row"]["block_id"] = "other_track_1"
    for blocks, provenance, message in [([stray], PROVENANCE, f"block other_track_1 does not start with the set id {SET}"),
                                        ([make_block("track", 1)], {key: value for key, value in PROVENANCE.items() if key != "seed"}, "provenance lacks seed"),
                                        ([make_block("track", 1)], {**PROVENANCE, "set_id": "other"}, f"provenance is of set other, not {SET}")]:
        with pytest.raises(Invalid, match=message):
            access.write_set(SET, blocks, provenance)
    assert not access.root.exists()


def test_a_write_that_fails_half_way_leaves_no_set_and_no_stage(access, monkeypatch):
    def broken(arrays, path, schema):
        """
        A parquet write that fails after the folder is made.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        raise OSError("disk full")

    monkeypatch.setattr(tables, "write_parquet", broken)
    with pytest.raises(OSError, match="disk full"):
        access.write_set(SET, [make_block("arena", 1)], PROVENANCE)
    assert access.sets() == [] and files_of(access.root) == [] and not (access.root / "sets" / f"{SET}.tmp").exists()
    assert access.health()["problems"] == []


def test_a_guess_appends_and_reads_back(written):
    assert written.guesses(SET) == []
    assert written.write_guess(SET, GUESS) == 1
    second = {**GUESS, "pair_id": "p2", "guessed_real": GUESS["real_block"], "correct": True}
    assert written.write_guess(SET, second) == 2
    assert written.guesses(SET) == [GUESS, second]
    with pytest.raises(Invalid, match="guess lacks correct"):
        written.write_guess(SET, {key: value for key, value in GUESS.items() if key != "correct"})
    with pytest.raises(NotFound, match="no set other"):
        written.write_guess("other", GUESS)
    assert written.health()["counts"] == {"sets": 1, "blocks": 2, "guesses": 2}


def test_deleting_a_set_removes_its_folder(written):
    assert written.delete_set(SET) == {"deleted": True, "blocks": 2}
    assert written.sets() == [] and files_of(written.root) == [] and written.find_block(f"{SET}_track_1000") is None
    with pytest.raises(NotFound, match=f"no set {SET}"):
        written.blocks(SET)
    assert written.delete_set(SET) == {"deleted": False, "blocks": 0}


def test_health_is_clean_on_an_empty_or_absent_folder_counts_a_set_and_names_what_is_wrong(access, written):
    health = SyntheticAccess(access.root / "nowhere").health()
    assert health["problems"] == [] and health["counts"] == {"sets": 0, "blocks": 0, "guesses": 0} and health["exists"] is False
    health = written.health()
    assert health["problems"] == [] and health["counts"] == {"sets": 1, "blocks": 2, "guesses": 0} and health["manifest"]["modified"]
    (written.root / "sets" / "syn_bare").mkdir()
    (written.root / "sets" / f"{SET}.tmp").mkdir()
    (written.root / "sets" / SET / "blocks" / f"{SET}_arena_1.parquet").unlink()
    health = written.health()
    assert health["problems"] == [f"sets/{SET} has 1 block files missing, the first is {SET}_arena_1", "sets/syn_bare has no provenance.json",
                                  "sets/syn_bare has no blocks.csv", f"1 temporary files or folders left by an interrupted write, the first is sets/{SET}.tmp"]
    assert health["counts"] == {} and health["manifest"] is None
