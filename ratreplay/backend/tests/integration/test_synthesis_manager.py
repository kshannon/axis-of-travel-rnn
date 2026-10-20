"""
SynthesisManager over the real engines and accesses on the synthetic folders, the real blocks built by ReviewManager: a set generated from two sessions with its provenance, listed and read, judged and found through ValidationManager, quizzed and tallied, deleted, and a source with no blocks refused.
"""

import getpass
import json
import shutil
from pathlib import Path

import pytest
from fixtures import S1, S2, S6

from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.processed import ProcessedAccess
from ratreplay_api.access.synthetic import GUESS_KEYS, PROVENANCE_KEYS, SyntheticAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.generator import GeneratorEngine
from ratreplay_api.engines.trajectory import RULES, SETTINGS, TrajectoryEngine
from ratreplay_api.managers.review import ReviewManager
from ratreplay_api.managers.synthesis import QUIZ_COLUMNS, QUIZ_ROW_KEYS, SIDES, SynthesisManager
from ratreplay_api.managers.validation import ValidationManager
from ratreplay_api.utilities.blocks import BLOCKS_CSV_SCHEMA
from ratreplay_api.utilities.errors import Invalid, NotFound

REAL = Path(__file__).resolve().parents[4] / "configs" / "environments"
COMMIT = "abc1234"
SHORT = {**SETTINGS, "window_s": 5.0}
ACCEPT = [{"op": "accept"}]

# The two built sessions give an arena block and two track blocks. The set is 20 s of arena and 60 s of track, so each kind
# gives one block of over min_block_s, and the seed names the set with the time it was made.
SOURCES = [S1, S6]
SEED, LENGTH_S = 3, {"arena": 20.0, "track": 60.0}
INDEX_KEYS = {"set_id", "created_at", "created_by", "sources", "seed", "length_s", "n_blocks", "kinds", "n_guesses", "n_correct"}
HEADER_KEYS = {"row", "rate_hz", "geometry"}
PROBLEM = "position not finite on 3 frames"


class Failing(TrajectoryEngine):
    """
    The engine with the first block of every build given a problem, so a build has a failed block.
    """

    def blocks(self, arrays, review, environment, rules):
        made = super().blocks(arrays, review, environment, rules)
        made["blocks"][0]["problems"] = [PROBLEM]
        return made


@pytest.fixture
def folders(tmp_path, transformed, synthetic):
    """
    The transformed folder, the processed folder built from S1 and S6 by ReviewManager, a copy of the environment yaml files and the empty synthetic folder.
    """
    shutil.copytree(REAL, tmp_path / "environments")
    processed = tmp_path / "processed"
    review = ReviewManager(TrajectoryEngine(), TransformedAccess(transformed), ProcessedAccess(processed), EnvironmentAccess(tmp_path / "environments"), COMMIT)
    for sid in SOURCES:
        review.save_blocks(sid, ACCEPT, "", SHORT)
    return transformed, processed, tmp_path / "environments", synthetic


@pytest.fixture
def managers(folders):
    """
    A SynthesisManager and a ValidationManager over the same accesses.
    """
    transformed, processed, environments, synthetic = folders
    trajectory, processed, synthetic, environment = TrajectoryEngine(), ProcessedAccess(processed), SyntheticAccess(synthetic), EnvironmentAccess(environments)
    synthesis = SynthesisManager(trajectory, GeneratorEngine(), processed, synthetic, environment, COMMIT)
    return synthesis, ValidationManager(trajectory, TransformedAccess(transformed), processed, synthetic, environment)


@pytest.fixture
def generated(managers):
    """
    The managers and the result of generating one set.
    """
    synthesis, validation = managers
    return synthesis, validation, synthesis.generate(SOURCES, SEED, LENGTH_S, SHORT)


def test_a_set_is_generated_from_two_built_sessions_with_both_recipes_and_its_provenance_then_listed_and_read(generated, folders):
    synthesis, _, made = generated
    set_id = made["set_id"]
    assert set(made) == {"set_id", "built", "failed", "warnings", "kinds"} and made["kinds"] == ["arena", "track"]
    assert made["built"] == 2 and made["failed"] == [] and set_id.startswith("syn_") and set_id.endswith(f"_{SEED}")
    access = SyntheticAccess(folders[3])
    provenance = access.set(set_id)
    assert set(provenance) == set(PROVENANCE_KEYS) and json.dumps(provenance)
    assert (provenance["sources"], provenance["seed"], provenance["length_s"], provenance["settings"]) == (SOURCES, SEED, LENGTH_S, SHORT)
    assert provenance["environments"] == {"arena": "open_arena", "track": "triple_t"} and provenance["created_by"] == getpass.getuser()
    assert provenance["recipe_real"]["arena"]["environment"] == "open_arena" and provenance["recipe_synthetic"]["arena"]["environment"] == "open_arena"
    assert provenance["camera"]["led_separation_m"] == ProcessedAccess(folders[1]).metadata(S1)["frame"]["track"]["led_separation_m"]
    assert set(provenance["recipe_real"]) == set(provenance["recipe_synthetic"]) == {"arena", "track"}
    assert provenance["recipe_real"]["track"]["counts"]["blocks"] == 2 and provenance["recipe_synthetic"]["track"]["counts"]["blocks"] == 1
    assert provenance["rules"] == json.loads(json.dumps(RULES)) and provenance["generator"] == {"version": 3} and provenance["code_version"].endswith(COMMIT)
    rows = access.blocks(set_id)
    assert [row["kind"] for row in rows] == ["arena", "track"] and all(row["block_id"].startswith(set_id) and row["session_id"] == set_id for row in rows)
    assert all(set(row) == set(BLOCKS_CSV_SCHEMA.names) and row["subject_id"] == "synthetic" and row["date"] == provenance["created_at"][:10] for row in rows)
    index = synthesis.index()
    assert len(index) == 1 and set(index[0]) == INDEX_KEYS
    assert (index[0]["set_id"], index[0]["n_blocks"], index[0]["kinds"], index[0]["n_guesses"], index[0]["n_correct"]) == (set_id, 2, ["arena", "track"], 0, 0)
    header = synthesis.set(set_id)
    assert header["blocks"] == rows and {key: header[key] for key in PROVENANCE_KEYS} == provenance


def test_readiness_on_the_set_judges_its_blocks_under_its_rules_and_a_synthetic_block_is_found_by_its_id(generated):
    _, validation, made = generated
    set_id = made["set_id"]
    ready = validation.readiness(f"set:{set_id}", SHORT)
    assert ready["which"] == f"set:{set_id}" and ready["totals"]["blocks"] == 2 and ready["totals"]["windows"] > 0
    assert list(ready["built"]) == [set_id] and ready["built"][set_id].keys() == {"settings", "built_at", "excluded", "failed"}
    assert ready["built"][set_id]["settings"] == SHORT and ready["built"][set_id]["excluded"] is False
    track = next(block for block in ready["blocks"] if block["kind"] == "track")
    header = validation.block(track["block_id"])
    assert header["row"] == {key: value for key, value in track.items() if key not in ("count", "verdict")}
    assert header["geometry"]["name"] == "triple_t" and header["trips"] and header["one_light"] == []
    arrays = validation.arrays(track["block_id"])
    assert len(arrays["t"]) == track["n_frames"] and arrays["frame"][0] == track["frame_start"]
    windows = validation.windows(track["block_id"], SHORT)
    assert (windows["count"], windows["verdict"]) == (track["count"], track["verdict"])
    assert {block["session_id"] for block in validation.readiness("real", SHORT)["blocks"]} == set(SOURCES)


def test_a_pair_hides_both_sources_and_a_correct_and_a_wrong_guess_give_the_tally(generated, folders):
    synthesis, _, made = generated
    set_id = made["set_id"]
    opened = synthesis.pair(set_id, "track")
    assert set(opened) == {"pair_id", "kind", "sides"} and opened["kind"] == "track" and opened["sides"] == list(SIDES)
    pair = synthesis.pairs[opened["pair_id"]]
    assert pair["real_block"] in (f"{S1}_track_01", f"{S6}_track_01") and pair["synthetic_block"].startswith(set_id)
    for side in SIDES:
        header = synthesis.pair_block(opened["pair_id"], side)
        assert set(header) == HEADER_KEYS and set(header["row"]) == set(QUIZ_ROW_KEYS)
        assert header["row"]["kind"] == "track" and header["geometry"]["name"] == "triple_t"
        arrays = synthesis.pair_arrays(opened["pair_id"], side)
        assert tuple(arrays) == QUIZ_COLUMNS and "t" not in arrays and len(arrays["x"]) == header["row"]["n_frames"]
        assert S1 not in json.dumps(header) and S6 not in json.dumps(header) and set_id not in json.dumps(header)
    right = synthesis.guess(set_id, opened["pair_id"], pair["real_side"])
    assert right["correct"] is True and right["real_side"] == pair["real_side"] and right["real_block"] == pair["real_block"]
    assert right["tally"] == {"n": 1, "correct": 1, "by": {getpass.getuser(): {"n": 1, "correct": 1}}}
    with pytest.raises(NotFound):
        synthesis.pair_block(opened["pair_id"], "left")
    second = synthesis.pair(set_id)
    wrong_side = next(side for side in SIDES if side != synthesis.pairs[second["pair_id"]]["real_side"])
    wrong = synthesis.guess(set_id, second["pair_id"], wrong_side)
    assert wrong["correct"] is False and wrong["tally"] == {"n": 2, "correct": 1, "by": {getpass.getuser(): {"n": 2, "correct": 1}}}
    guesses = SyntheticAccess(folders[3]).guesses(set_id)
    assert len(guesses) == 2 and all(set(guess) == set(GUESS_KEYS) for guess in guesses)
    assert [guess["guessed_real"] for guess in guesses] == [guesses[0]["real_block"], guesses[1]["synthetic_block"]]
    assert synthesis.tally(set_id) == wrong["tally"] and synthesis.guesses(set_id) == {"tally": wrong["tally"], "guesses": guesses}
    assert (synthesis.index()[0]["n_guesses"], synthesis.index()[0]["n_correct"]) == (2, 1)
    with pytest.raises(Invalid, match="not other"):
        synthesis.guess("other", synthesis.pair(set_id)["pair_id"], "left")
    with pytest.raises(NotFound, match="no open pair nope"):
        synthesis.guess(set_id, "nope", "left")


class Relabelled(ProcessedAccess):
    """
    The processed folder with the blocks of some sessions listed in another environment, as if those sources had been recorded on a rotated track.
    """

    def __init__(self, root, sessions):
        super().__init__(root)
        self.sessions = sessions

    def blocks(self):
        return [{**row, "environment": OTHER_ENVIRONMENT} if row["session_id"] in self.sessions else row for row in super().blocks()]


OTHER_ENVIRONMENT = "triple_t_rot90"
DRAWS = 20


def test_the_real_block_of_a_pair_is_drawn_from_the_environment_the_set_was_generated_in(generated, folders):
    _, _, made = generated
    _, processed, environments, synthetic = folders

    def relabelled(sessions):
        return SynthesisManager(TrajectoryEngine(), GeneratorEngine(), Relabelled(processed, sessions), SyntheticAccess(synthetic), EnvironmentAccess(environments), COMMIT)

    synthesis = relabelled([S6])
    for _ in range(DRAWS):
        opened = synthesis.pair(made["set_id"], "track")
        assert synthesis.pairs[opened["pair_id"]]["real_block"] == f"{S1}_track_01"
        left, right = (synthesis.pair_block(opened["pair_id"], side) for side in SIDES)
        assert left["row"]["environment"] == right["row"]["environment"] == "triple_t" and left["geometry"] == right["geometry"]
    with pytest.raises(Invalid, match="no track block in triple_t to pair"):
        relabelled(SOURCES).pair(made["set_id"], "track")


def test_deleting_the_set_removes_it_with_its_open_pairs_and_the_index_no_longer_lists_it(generated, folders):
    synthesis, validation, made = generated
    set_id = made["set_id"]
    opened = synthesis.pair(set_id)
    assert synthesis.delete_set(set_id) == {"deleted": True, "blocks": 2}
    assert synthesis.index() == [] and not (folders[3] / "sets" / set_id).exists() and synthesis.pairs == {}
    with pytest.raises(NotFound):
        synthesis.pair_block(opened["pair_id"], "left")
    with pytest.raises(NotFound):
        validation.readiness(f"set:{set_id}", SHORT)
    assert synthesis.delete_set(set_id) == {"deleted": False, "blocks": 0}


def test_a_block_with_problems_is_listed_as_failed_and_not_written(folders):
    transformed, processed, environments, synthetic = folders
    manager = SynthesisManager(Failing(), GeneratorEngine(), ProcessedAccess(processed), SyntheticAccess(synthetic), EnvironmentAccess(environments), COMMIT)
    made = manager.generate(SOURCES, SEED, LENGTH_S, SHORT)
    set_id = made["set_id"]
    assert made["built"] == 1 and made["kinds"] == ["track"] and made["failed"] == [{"block_id": f"{set_id}_arena_01", "problems": [PROBLEM]}]
    access = SyntheticAccess(synthetic)
    assert access.set(set_id)["failed"] == made["failed"] and [row["kind"] for row in access.blocks(set_id)] == ["track"]
    assert sorted(path.name for path in (synthetic / "sets" / set_id / "blocks").iterdir()) == [f"{set_id}_track_01.parquet"]
    assert list(access.set(set_id)["recipe_synthetic"]) == ["track"] and access.health()["problems"] == []


def test_a_source_with_no_built_blocks_and_a_kind_the_sources_lack_are_refused_and_nothing_is_written(managers, folders):
    synthesis, _ = managers
    with pytest.raises(Invalid, match=f"session {S2} has no built blocks"):
        synthesis.generate([S1, S2], SEED, LENGTH_S, SHORT)
    with pytest.raises(Invalid, match="no arena blocks"):
        synthesis.generate([S6], SEED, LENGTH_S, SHORT)
    assert list(folders[3].iterdir()) == [] and synthesis.index() == []
