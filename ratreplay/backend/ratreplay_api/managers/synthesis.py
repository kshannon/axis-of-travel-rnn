"""
SynthesisManager: the synthetic sets, one generated from the built blocks of some real sessions and blocked like real data, a set deleted, and the quiz over a set, a real and a synthetic block of one kind shown without their names and the guesses tallied.
"""

import datetime
import getpass
import secrets

from ..engines.trajectory import RULES, VERSION
from ..utilities import clock
from ..utilities.errors import Invalid, NotFound

# The id of a set, from the time it was made and its seed, and the version of the generator recorded in its provenance.
SET_ID = "syn_{date}_{time}_{seed}"
GENERATOR_VERSION = 2
CODE_VERSION = "trajectory {} {}"

# The epoch kind whose registration gives the LED separation, and the rate and longest gap a synthetic session is generated at.
TRACK = "track"
RATE_HZ, MAX_GAP = 60, 30

# The quiz: the two sides a pair is shown on, and what the page gets of a block, only what it draws (the trail and playback
# from x, y and heading, the speed trace) and the facts both sides share. Everything else in a block (its ids, runs, trips,
# phases, fills, lights, the registration numbers, and t, which a real block keeps from its place in the session) would tell
# a real block from a synthetic one and void the tally.
SIDES = ("left", "right")
QUIZ_ROW_KEYS = ("kind", "environment", "n_frames", "duration_s", "rate_hz")
QUIZ_COLUMNS = ("x", "y", "heading", "speed")

# What the manager says.
NO_BLOCKS = "session {sid} has no built blocks"
NO_KIND = "the sources have no {kind} blocks to fit a recipe from"
NO_REAL_OF_KIND = "the sources have no {kind} block in {environment} to pair"
NOT_A_KIND = "set {set_id} has no {kind} blocks"
NO_PAIR = "no open pair {pair_id}"
OTHER_SET = "pair {pair_id} is of set {other}, not {set_id}"


def set_id_at(stamp, seed):
    """
    The id of a set made at the ISO timestamp with the seed.
    """
    return SET_ID.format(date=stamp[:10].replace("-", ""), time=stamp[11:19].replace(":", ""), seed=seed)


def tally_of(guesses):
    """
    How many guesses were made and how many were right, in all and per person.
    """
    by = {}
    for guess in guesses:
        who = by.setdefault(guess["by"], {"n": 0, "correct": 0})
        who["n"] += 1
        who["correct"] += guess["correct"]
    return {"n": len(guesses), "correct": sum(guess["correct"] for guess in guesses), "by": by}


class SynthesisManager:
    """
    The engines and the accesses it works with, handed in at the composition root, and the one piece of state a manager holds, the open pairs of the quiz by their opaque id, lost on restart.
    """

    def __init__(self, trajectory, generator, processed, synthetic, environment, code_version):
        self.trajectory, self.generator, self.processed, self.synthetic, self.environment = trajectory, generator, processed, synthetic, environment
        self.code_version = code_version
        self.pairs = {}

    def index(self):
        """
        Every set with when and by whom it was made, its sources, seed and lengths, how many blocks of which kinds it holds and how the guesses against it stand.
        """
        rows = []
        for set_id in self.synthetic.sets():
            provenance, blocks, tally = self.synthetic.set(set_id), self.synthetic.blocks(set_id), tally_of(self.synthetic.guesses(set_id))
            rows.append({**{key: provenance[key] for key in ("set_id", "created_at", "created_by", "sources", "seed", "length_s")},
                         "n_blocks": len(blocks), "kinds": sorted({row["kind"] for row in blocks}), "n_guesses": tally["n"], "n_correct": tally["correct"]})
        return rows

    def set(self, set_id):
        """
        A set's provenance with the rows of its blocks.
        """
        return {**self.synthetic.set(set_id), "blocks": self.synthetic.blocks(set_id)}

    def generate(self, sources, seed, length_s, settings):
        """
        Generate a set from the built blocks of the source sessions: fit the recipe, generate a session of the lengths asked for per kind under the first source's camera and environments, dated the day it is made, block it with the same engine call as real data, fit the recipe of the result and write the set with its provenance, refused when a source has no built blocks, the sources have no blocks of a kind asked for, or the generator cannot draw from the recipe or the geometry. Blocks with problems are listed in failed and not written. The settings are recorded for readiness, which windows the set's blocks on demand.
        """
        rows = {sid: [row for row in self.processed.blocks() if row["session_id"] == sid] for sid in sources}
        for sid, found in rows.items():
            if not found:
                raise Invalid(NO_BLOCKS.format(sid=sid))
        blocks = [self.processed.block(row["block_id"]) for found in rows.values() for row in found]
        geometry = {row["environment"]: self.environment.environment(row["environment"]) for found in rows.values() for row in found}
        recipe_real = self.trajectory.recipe(blocks, geometry, RULES)
        first = rows[sources[0]]
        names = {row["kind"]: row["environment"] for row in first}
        frame = self.processed.metadata(sources[0])["frame"]
        for kind in length_s:
            if kind not in recipe_real or kind not in names or kind not in frame:
                raise Invalid(NO_KIND.format(kind=kind))
        environments = {kind: names[kind] for kind in length_s}
        camera = {**{kind: frame[kind] for kind in length_s}, "led_separation_m": frame[TRACK]["led_separation_m"], "rate_hz": RATE_HZ, "max_gap": MAX_GAP}
        created_at = clock.iso_now()
        set_id = set_id_at(created_at, seed)
        by_kind = {kind: geometry[name] for kind, name in environments.items()}
        session = self.generator.session(recipe_real, by_kind, camera, seed, length_s, set_id, datetime.date.fromisoformat(created_at[:10]))
        made = self.trajectory.blocks(session, None, {g["name"]: g for g in by_kind.values()}, RULES)
        kept = [{"row": block["row"], "arrays": block["arrays"]} for block in made["blocks"] if not block["problems"]]
        failed = [{"block_id": block["row"]["block_id"], "problems": block["problems"]} for block in made["blocks"] if block["problems"]]
        provenance = {"set_id": set_id, "created_at": created_at, "created_by": getpass.getuser(), "sources": list(sources), "environments": environments,
                      "camera": camera, "seed": seed, "length_s": length_s, "rules": RULES, "settings": settings,
                      "code_version": CODE_VERSION.format(VERSION, self.code_version), "generator": {"version": GENERATOR_VERSION},
                      "recipe_real": recipe_real, "recipe_synthetic": self.trajectory.recipe(kept, geometry, RULES), "warnings": made["warnings"], "failed": failed}
        self.synthetic.write_set(set_id, kept, provenance)
        return {"set_id": set_id, "built": len(kept), "failed": failed, "warnings": made["warnings"], "kinds": sorted({b["row"]["kind"] for b in kept})}

    def delete_set(self, set_id):
        """
        Remove the set whole with its open pairs and say whether there was one and how many blocks went.
        """
        for pair_id in [pair_id for pair_id, pair in self.pairs.items() if pair["set_id"] == set_id]:
            del self.pairs[pair_id]
        return self.synthetic.delete_set(set_id)

    def pair(self, set_id, kind=None):
        """
        Open a pair for the quiz: one real block of the set's sources and one synthetic block of the set, both of one kind (the one asked for, else any kind the set has) and of the environment the set was generated in, so the backdrop tells nothing, the real one on a side drawn at random, kept under an opaque id until the guess.
        """
        provenance, synthetic = self.synthetic.set(set_id), self.synthetic.blocks(set_id)
        kinds = sorted({row["kind"] for row in synthetic})
        if kind is not None and kind not in kinds:
            raise Invalid(NOT_A_KIND.format(set_id=set_id, kind=kind))
        kind = kind or secrets.choice(kinds)
        environment = provenance["environments"][kind]
        real = [row for row in self.processed.blocks() if row["session_id"] in provenance["sources"] and row["kind"] == kind and row["environment"] == environment]
        if not real:
            raise Invalid(NO_REAL_OF_KIND.format(kind=kind, environment=environment))
        pair_id = secrets.token_urlsafe()
        self.pairs[pair_id] = {"set_id": set_id, "kind": kind, "real_block": secrets.choice(real)["block_id"],
                               "synthetic_block": secrets.choice([row for row in synthetic if row["kind"] == kind])["block_id"], "real_side": secrets.choice(SIDES)}
        return {"pair_id": pair_id, "kind": kind, "sides": list(SIDES)}

    def pair_block(self, pair_id, side):
        """
        The block on one side of an open pair as the quiz player's header: the facts both sides share, its rate and the geometry of its environment, nothing that would tell its source.
        """
        row = self._block(self._pair(pair_id), side)["row"]
        return {"row": {key: row[key] for key in QUIZ_ROW_KEYS}, "rate_hz": row["rate_hz"], "geometry": self.environment.environment(row["environment"])}

    def pair_arrays(self, pair_id, side):
        """
        The arrays of the block on one side of an open pair, only what the quiz player draws.
        """
        arrays = self._block(self._pair(pair_id), side)["arrays"]
        return {name: arrays[name] for name in QUIZ_COLUMNS}

    def guess(self, set_id, pair_id, guessed_side):
        """
        Record which side the person called real against the open pair of the set, by whom and when, close the pair and reveal it with the set's tally.
        """
        pair = self._pair(pair_id)
        if pair["set_id"] != set_id:
            raise Invalid(OTHER_SET.format(pair_id=pair_id, other=pair["set_id"], set_id=set_id))
        correct = guessed_side == pair["real_side"]
        guess = {"at": clock.iso_now(), "by": getpass.getuser(), "pair_id": pair_id, "real_block": pair["real_block"], "synthetic_block": pair["synthetic_block"],
                 "kind": pair["kind"], "guessed_real": pair["real_block"] if correct else pair["synthetic_block"], "correct": correct}
        self.synthetic.write_guess(set_id, guess)
        del self.pairs[pair_id]
        return {"correct": correct, "real_side": pair["real_side"], "real_block": pair["real_block"], "synthetic_block": pair["synthetic_block"], "tally": self.tally(set_id)}

    def tally(self, set_id):
        """
        How the guesses against the set stand, in all and per person.
        """
        return tally_of(self.synthetic.guesses(set_id))

    def guesses(self, set_id):
        """
        The set's tally and every guess made against it.
        """
        guesses = self.synthetic.guesses(set_id)
        return {"tally": tally_of(guesses), "guesses": guesses}

    def _pair(self, pair_id):
        """
        An open pair by its id, NotFound when none is open under it.
        """
        if pair_id not in self.pairs:
            raise NotFound(NO_PAIR.format(pair_id=pair_id))
        return self.pairs[pair_id]

    def _block(self, pair, side):
        """
        The block on the side of the pair: the real one from the processed folder, the synthetic one from the set.
        """
        if side == pair["real_side"]:
            return self.processed.block(pair["real_block"])
        return self.synthetic.block(pair["set_id"], pair["synthetic_block"])
