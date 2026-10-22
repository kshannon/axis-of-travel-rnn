"""
The decision table on fake analysis rows: the bar, each row of the brief's section 9 table, and the decision line.
"""

import pytest

from pilot import decision
from pilot.analysis import load_thresholds

THR = load_thresholds()  # the pre-registered numbers: 5 percent of units, the 95th percentile, majority 0.5, ratio 0.8
MEETS = (0.10, 0.12, 0.09, 0.11, 0.10)  # five trained seeds over 5 percent; the untrained draws below are all 0
BELOW = (0.0,) * 5  # no better than the untrained draws


def input_set_rows(input_set, trained=MEETS, open_field=(0.01,) * 5, untrained=(0.0,) * 20, axis=10, persist=2,
                   direction=0):
    """
    One row per run: the trained seeds on both worlds (with these counts each), the open-field-only seeds, the draws.
    """
    def runs(kind, diet, released, counts):
        return [{"input_set": input_set, "kind": kind, "diet": diet, "released": r, **counts} for r in released]

    counts = {"n_axis": axis, "n_persist": persist, "n_direction": direction}
    none = {"n_axis": 0, "n_persist": 0, "n_direction": 0}
    return (runs("trained", "both", trained, counts) + runs("trained", "open_field", open_field, none)
            + runs("untrained", "both", untrained, none))


def decide(sets, failed=()):
    """
    The table and the decision line for input sets given as {name: keyword arguments of input_set_rows}.
    """
    rows = [row for name, kwargs in sets.items() for row in input_set_rows(name, **kwargs)]
    facts = decision.facts_of(rows, tuple(sets), THR)
    table = decision.table_of(facts, tuple(sets), THR, failed)
    return table, decision.verdict_of(table, failed)


def answers(table):
    return [row[2] for row in table]


def test_the_bar_needs_every_seed_over_the_minimum_and_strictly_over_the_untrained_percentile():
    def meets(**kwargs):
        rows = input_set_rows("place_only", **kwargs)
        return decision.facts_of(rows, ("place_only",), THR)["place_only"]["meets"]

    assert meets()
    assert not meets(trained=(0.10, 0.10, 0.10, 0.10, 0.04))  # one seed under 5 percent
    assert not meets(trained=(0.10, 0.10, 0.10, 0.10, 0.06), untrained=(0.06,) * 20)  # equal to the cutoff
    assert not meets(trained=(0.10, 0.10, 0.10, 0.10, 0.06), untrained=(0.07,) * 20)  # over 5 percent, under the draws
    outlier = (0.0,) * 19 + (0.5,)  # one lucky draw does not set the bar: it is the 95th percentile
    rows = input_set_rows("place_only", trained=(0.06,) * 5, untrained=outlier)
    facts = decision.facts_of(rows, ("place_only",), THR)["place_only"]
    assert facts["meets"] and facts["cutoff"] == pytest.approx(0.025)


def test_place_only_meeting_the_bar_is_the_headline_go():
    table, verdict = decide({"place_only": {}})
    assert answers(table) == [True, None, None, False, False, False, False, False]
    assert verdict == "Go. This is the headline (row 1 holds)"


def test_only_full_meeting_the_bar_is_the_narrower_go():
    table, verdict = decide({"place_only": {"trained": BELOW}, "place_motion": {"trained": BELOW}, "full": {}})
    assert answers(table)[:3] == [False, True, False]
    assert answers(table)[3] is False  # one input set is over its untrained draws, so trained does not match untrained
    assert verdict.startswith("Go, with the narrower claim. The arena release carries it (row 2 holds)")


def test_place_motion_meeting_the_bar_without_place_only_is_the_ladder():
    table, verdict = decide({"place_only": {"trained": BELOW}, "place_motion": {}, "full": {"trained": BELOW}})
    assert answers(table)[:3] == [False, False, True]
    assert verdict.startswith("Go. Report the ladder (row 3 holds)")


def test_a_trained_net_that_matches_the_untrained_draws_is_a_no_go_that_is_not_final_without_the_other_sets():
    sets = {"place_only": {"trained": (0.02,) * 5, "untrained": (0.03,) * 20, "open_field": (0.02,) * 5, "axis": 0}}
    table, verdict = decide(sets)
    assert answers(table)[3:7] == [True, None, True, False]  # no axis units, so row 5 cannot be computed
    assert verdict.startswith("No-go (row 4 (Trained matches untrained everywhere), row 6 (Loop-and-arena diet")
    assert "rows 2, 3 cannot be computed" in verdict and verdict.endswith("so this is not final")


def test_axis_units_that_mostly_persist_qualify_a_go():
    table, verdict = decide({"place_only": {"persist": 8}})
    assert answers(table)[4] is True
    assert verdict == ("Go. This is the headline (row 1 holds); "
                       "qualified by row 5 (Axis units mostly persist in the arena)")
    assert answers(decide({"place_only": {"persist": 5}})[0])[4] is False  # half is not a majority


def test_an_arena_only_diet_that_does_as_well_qualifies_a_go():
    table, verdict = decide({"place_only": {"open_field": (0.09,) * 5}})
    assert answers(table)[5] is True
    assert verdict == ("Go. This is the headline (row 1 holds); "
                       "qualified by row 6 (Loop-and-arena diet matches arena-only diet)")
    assert answers(decide({"place_only": {"open_field": (0.08,) * 5}})[0])[5] is False  # 0.8 x 0.104 is 0.083


def test_direction_units_without_axis_units_are_noted_in_the_decision_line():
    table, verdict = decide({"place_only": {"trained": BELOW, "axis": 0, "direction": 3}})
    assert answers(table)[6] is True and answers(table)[0] is False
    assert verdict.startswith("No-go")
    assert verdict.endswith(". Row 7 holds (Direction units appear in place_only but no axis units): "
                            "Report as a pilot observation, not a failure")


def test_no_input_set_over_the_bar_and_nothing_else_is_a_no_go_that_says_so():
    table, verdict = decide({"place_only": {"trained": (0.04,) * 5}})  # above the draws, under 5 percent
    assert answers(table) == [False, None, None, False, False, False, False, False]
    assert verdict.startswith("No-go (no input set meets the bar); rows 2, 3 cannot be computed")


def test_failed_section_2_checks_put_fix_the_task_first_in_front():
    failed = ["place_only: position decodable from hidden state"]
    table, verdict = decide({"place_only": {}}, failed)
    assert answers(table)[7] is True and table[7][3] == failed[0]
    assert verdict == ("Fix the task first, the section 2 checks failed. The other rows alone would say: "
                       "Go. This is the headline (row 1 holds)")


def test_rows_that_need_an_input_set_that_is_not_run_have_no_answer_and_say_which():
    table, _ = decide({"place_only": {}})
    assert table[1][2] is None and table[1][3] == "cannot be computed: place_motion, full not being run"
    assert table[2][3] == "cannot be computed: place_motion not being run"
    lines = decision.table_lines(table)
    assert lines[0].startswith("1. [yes] place_only meets the bar") and lines[3].startswith("2. [n/a] Only full")
