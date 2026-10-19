"""
Parity of TrajectoryEngine.apply with the old Dash tool: 3,200 random edit lists over the synthetic sessions S1 and S6 give the tool's cuts and flagged runs exactly and its blocks until a documented difference. This file imports the old tool on purpose, it is the parity oracle and goes with it. The frozen record beside it holds 180 edit lists per session with what apply returned for them at task L, and stays when the tool goes as the only exact record.
"""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from fixtures import S1, S6
from ratreplay import data as dash
from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.trajectory import RULES, TrajectoryEngine
from ratreplay_api.engines.trajectory import edits as rules_of

ENVIRONMENTS = Path(__file__).resolve().parents[4] / "configs" / "environments"
LISTS, LONGEST = 1600, 8
FROZEN = Path(__file__).resolve().parent / "frozen" / "apply_expected.json"

# What a random list is drawn from: the ops with their weights, how far from an interesting frame (a block, stretch or run
# edge) a frame lies, the lengths of a new block or a cut around the 600 frames of the minimum block, and how often a list
# opens by dropping a block and making a new one over it, which is where a removed block meets a kept one.
OPS = ("accept", "confirm", "move", "split", "drop", "new", "cut", "flag")
WEIGHTS = (0.06, 0.12, 0.18, 0.16, 0.16, 0.14, 0.12, 0.06)
JITTER = (-600, -60, -1, 0, 1, 30, 59, 60, 61, 599, 600, 601)
LENGTHS = (50, 300, 599, 600, 601, 900, 1200, 2000)
OVER_REMOVED = 0.35

# The documented differences of the old Dash tool, and what each counts as. Its edits reach the first block holding a
# frame whether it is removed or not, the new rules reach a kept one first (reach). It lets a removed block come back over a
# kept one and a split or a move leave a kept block under the minimum length, the new rules refuse both and the refusal is
# the cause. It toggles a confirm and leaves an edited block as it is under a confirm or an accept, the new rules confirm an
# edited block and never take a confirm back. It offers a block in an epoch outside the rules' condition, the new session has
# none (checked per session).
REACH = "reach"
ACCEPTS = "accepts"
REFUSALS = {rules_of.RESTORES_MESSAGE: "restores", rules_of.TOO_SHORT_MESSAGE.format(10.0): "too short"}
SAME = "same"
# The refusal texts that carry a frame, by their first word, counted under one name: no block holds frame N, frame N is in no epoch the rules cut.
NUMBERED = {"no": "no block", "frame": "uncut"}
SESSIONS = [(S1, 1, 0), (S6, 6, 1)]


def loaded(transformed, sid):
    """
    The new session, the Dash tool's session cut to the epochs the new one selects, and how many blocks that cut away.
    """
    access = EnvironmentAccess(ENVIRONMENTS)
    environments = {name: access.environment(name) for name in access.environments()}
    session = TrajectoryEngine().session(TransformedAccess(transformed).session(sid), environments, RULES)
    old = dash.load_session(transformed, sid)
    kinds = {e["epoch"] for e in session["epochs"]}
    cut = {**old, **{key: [row for row in old[key] if row["epoch"] in kinds] for key in ("epochs", "stretches", "blocks")}}
    return session, cut, len(old["blocks"]) - len(cut["blocks"])


def random_edit(rng, edges, n_frames):
    """
    One random edit, its frames drawn mostly near the edges so that the refusals fire.
    """
    def frame():
        return max(1, int(rng.choice(edges)) + int(rng.choice(JITTER))) if rng.random() < 0.6 else int(rng.integers(1, n_frames + 1))
    op, first = str(rng.choice(OPS, p=WEIGHTS)), frame()
    last = first + (int(rng.choice(LENGTHS)) if rng.random() < 0.7 else int(rng.integers(1, 2400)))
    fields = {"accept": {}, "confirm": {"frame": first}, "move": {"frame": first, "edge": str(rng.choice(("start", "end"))), "at": frame()},
              "split": {"frame": first}, "drop": {"frame": first}, "new": {"frame_start": first, "frame_end": last},
              "cut": {"frame_start": first, "frame_end": last}, "flag": {"run": int(rng.integers(1, 5))}}
    return {"op": op, **fields[op]}


def random_list(rng, initial, edges, n_frames):
    """
    A random list of one to LONGEST edits, opening in OVER_REMOVED of the cases with a drop of a block and a new block over it.
    """
    edits = []
    if rng.random() < OVER_REMOVED:
        block = initial[int(rng.integers(len(initial)))]
        start = block["frame_start"] + int(rng.choice((0, 1, 50, 100)))
        edits = [{"op": "drop", "frame": block["frame_start"]}, {"op": "new", "frame_start": start, "frame_end": start + int(rng.choice(LENGTHS[2:]))}]
    return edits + [random_edit(rng, edges, n_frames) for _ in range(int(rng.integers(1, LONGEST + 1)))]


def noted(blocks):
    """
    The blocks cut to the review's block keys, the old tool's empty note read as no note.
    """
    return [{**{key: b[key] for key in rules_of.BLOCK_KEYS}, "note": b["note"] or None} for b in blocks]


def cause(initial, session, edits, k):
    """
    The documented difference that explains why the Dash tool and the new rules first differ at the k-th edit, found from the state both share before it, else None.
    """
    engine, edit = TrajectoryEngine(), edits[k - 1]
    for r in engine.apply(initial, edits[:k], session)["refusals"]:
        if r["index"] == k - 1 and r["reason"] in REFUSALS:
            return REFUSALS[r["reason"]]
    before = engine.apply(initial, edits[:k - 1], session)["blocks"]
    if edit["op"] in rules_of.ANCHORS:
        holding = [b for b in before if b["frame_start"] <= edit[rules_of.ANCHORS[edit["op"]]] <= b["frame_end"]]
        if 0 < sum(b["status"] == rules_of.REMOVED for b in holding) < len(holding):
            return REACH
    if edit["op"] == "accept" and any(b["status"] == rules_of.EDITED for b in before):
        return ACCEPTS
    reached = rules_of.reaching(before, edit["frame"]) if edit["op"] == "confirm" else None
    if reached and reached["status"] in (rules_of.EDITED, rules_of.CONFIRMED):
        return ACCEPTS
    return None


def compare(session, old, seed):
    """
    Random edit lists through the new rules and the Dash tool: the cuts and flagged runs agree on every list, the blocks until a documented cause, and the lists counted by that cause, the refusal reasons by their text.
    """
    initial, engine, rng = session["initial_blocks"], TrajectoryEngine(), np.random.default_rng(seed)
    edges = sorted({b[key] + d for b in initial for key in ("frame_start", "frame_end") for d in (0, 1)} |
                   {r[key] for r in session["runs"] for key in ("frame_start", "frame_end")} |
                   {s[key] for s in session["stretches"] for key in ("frame_start", "frame_end")})
    causes, reasons = Counter(), Counter()
    for _ in range(LISTS):
        edits = random_list(rng, initial, edges, session["n_frames"])
        made = engine.apply(initial, edits, session)
        assert made["cuts"] == dash.cuts_of(edits), edits
        assert made["flagged_runs"] == dash.flagged_runs(edits), edits
        reasons.update(NUMBERED.get(r["reason"].split(" ")[0], r["reason"]) for r in made["refusals"])
        for k in range(1, len(edits) + 1):
            if noted(dash.apply_edits(old["blocks"], edits[:k], old)) != engine.apply(initial, edits[:k], session)["blocks"]:
                why = cause(initial, session, edits, k)
                assert why, f"edit {k} of {edits} differs from the Dash tool and no documented difference explains it"
                causes[why] += 1
                break
        else:
            causes[SAME] += 1
    return causes, reasons


@pytest.mark.parametrize("sid, seed, offered", SESSIONS)
def test_random_edit_lists_equal_the_dash_tool_until_a_documented_difference(transformed, sid, seed, offered):
    session, old, extra = loaded(transformed, sid)
    assert extra == offered  # S6's arena is under another condition, only the Dash tool offers a block there
    assert [{key: b[key] for key in rules_of.BLOCK_KEYS[:5]} for b in old["blocks"]] == [{key: b[key] for key in rules_of.BLOCK_KEYS[:5]} for b in session["initial_blocks"]]
    causes, reasons = compare(session, old, seed)
    assert sum(causes.values()) == LISTS and set(causes) == {SAME, REACH, ACCEPTS, *REFUSALS.values()}
    assert set(reasons) == {"no block", "uncut", rules_of.CROSSES_MESSAGE, rules_of.SHORT_MESSAGE.format(10.0), rules_of.OVERLAPS_MESSAGE, *REFUSALS}


@pytest.mark.parametrize("sid", [S1, S6])
def test_the_frozen_edit_lists_give_the_recorded_blocks_cuts_flagged_runs_and_refusals_exactly(transformed, sid):
    session, _, _ = loaded(transformed, sid)
    engine = TrajectoryEngine()
    for case in json.loads(FROZEN.read_text())[sid]:
        made = engine.apply(session["initial_blocks"], case["edits"], session)
        assert json.loads(json.dumps(made)) == {key: case[key] for key in ("blocks", "refusals", "cuts", "flagged_runs")}, case["edits"]
