"""
Notebook section 4: the brief's section 9 table read from the analysis rows, and the decision line.
"""

import numpy as np

COMPARISON_SETS = ("place_only", "place_motion", "full")  # the sets that row 2 compares


# ---------------------------------------------------------------------------
# what the rows read
# ---------------------------------------------------------------------------

def released_fractions(rows, input_sets):
    """
    The released fraction of each run, as {input set: {"trained both" | "trained open field" | "untrained": [...]}}.
    """
    def of(input_set, kind, diet):
        return [r["released"] for r in rows if (r["input_set"], r["kind"], r["diet"]) == (input_set, kind, diet)]

    return {s: {"trained both": of(s, "trained", "both"), "trained open field": of(s, "trained", "open_field"),
                "untrained": of(s, "untrained", "both")} for s in input_sets}


def untrained_cutoffs(released, thr):
    """
    The untrained_percentile of the untrained draws' released fractions, for each input set.
    """
    return {s: float(np.percentile(groups["untrained"], thr["untrained_percentile"])) for s, groups in released.items()}


def facts_of(rows, input_sets, thr):
    """
    For each input set what the table rows read: the trained seeds against the untrained cutoff, and summed counts.
    """
    assert thr["seeds_required"] == "all"  # the bar is read as every trained seed
    released = released_fractions(rows, input_sets)
    cutoffs = untrained_cutoffs(released, thr)

    def total(input_set, key):
        return sum(r[key] for r in rows if (r["input_set"], r["kind"], r["diet"]) == (input_set, "trained", "both"))

    facts = {}
    for s in input_sets:
        trained, cutoff = released[s]["trained both"], cutoffs[s]
        facts[s] = {"released": trained, "cutoff": cutoff, "n_untrained": len(released[s]["untrained"]),
                    "meets": all(v >= thr["min_unit_fraction"] and v > cutoff for v in trained),
                    "above": sum(v > cutoff for v in trained),
                    "axis": total(s, "n_axis"), "persist": total(s, "n_persist"), "direction": total(s, "n_direction"),
                    "both_mean": np.mean(trained), "open_mean": np.mean(released[s]["trained open field"])}
    return facts


# ---------------------------------------------------------------------------
# the rows of the table; each function answers one row as (answer, numbers), the answer None if it cannot be computed
# ---------------------------------------------------------------------------

def percent(values):
    """
    Fractions as percentages with one decimal, joined by commas.
    """
    return ", ".join(f"{100 * v:.1f}%" for v in values)


def bar_numbers(input_set, facts, thr):
    """
    The numbers behind the bar for one input set, in words.
    """
    f = facts[input_set]
    verb = "meets" if f["meets"] else "does not meet"
    return (f"{input_set}: released {percent(f['released'])} per trained seed; "
            f"minimum {100 * thr['min_unit_fraction']:.0f}%, untrained {thr['untrained_percentile']}th percentile "
            f"{100 * f['cutoff']:.1f}% ({f['n_untrained']} draws); {verb} the bar")


def place_only_meets(facts, thr):
    return facts["place_only"]["meets"], bar_numbers("place_only", facts, thr)


def only_full(facts, thr):
    meets = {s: facts[s]["meets"] for s in COMPARISON_SETS}
    return (meets["full"] and not meets["place_only"] and not meets["place_motion"],
            "; ".join(bar_numbers(s, facts, thr) for s in COMPARISON_SETS))


def motion_without_place(facts, thr):
    return (facts["place_motion"]["meets"] and not facts["place_only"]["meets"],
            bar_numbers("place_motion", facts, thr) + "; " + bar_numbers("place_only", facts, thr))


def trained_matches_untrained(facts, thr):
    return (all(f["above"] == 0 for f in facts.values()),
            "; ".join(f"{s}: {f['above']} of {len(f['released'])} trained seeds above the untrained cutoff"
                      for s, f in facts.items()))


def mostly_persist(facts, thr):
    with_axis = {s: f for s, f in facts.items() if f["axis"] > 0}
    if not with_axis:
        return None, "cannot be computed: no trained seed has an axis unit"
    return (all(f["persist"] / f["axis"] > thr["persist_majority"] for f in with_axis.values()),
            "; ".join(f"{s}: {f['persist']} of {f['axis']} axis units persist ({100 * f['persist'] / f['axis']:.0f}%)"
                      for s, f in with_axis.items()) + f", majority is above {thr['persist_majority']}")


def same_diet(facts, thr):
    ratio = thr["diet_match_ratio"]
    return (all(f["open_mean"] >= ratio * f["both_mean"] for f in facts.values()),
            "; ".join(f"{s}: open-field-only {100 * f['open_mean']:.2f}% against loop-and-arena "
                      f"{100 * f['both_mean']:.2f}% of units released (limit {ratio} x)" for s, f in facts.items()))


def direction_only(facts, thr):
    f = facts["place_only"]
    return (f["direction"] > 0 and f["axis"] == 0,
            f"place_only trained seeds: {f['direction']} direction units and {f['axis']} axis units in all")


# (result, decision if yes, the input sets the row needs, the function that answers it); row 8 is added by table_of
ROWS = (
    ("place_only meets the bar", "Go. This is the headline", ("place_only",), place_only_meets),
    ("Only full meets the bar", "Go, with the narrower claim. The arena release carries it", COMPARISON_SETS,
     only_full),
    ("place_motion meets it and place_only does not", "Go. Report the ladder", ("place_only", "place_motion"),
     motion_without_place),
    ("Trained matches untrained everywhere", "No-go. Change horizon, noise or bottleneck", (),
     trained_matches_untrained),
    ("Axis units mostly persist in the arena", "No-go as designed. Report it", (), mostly_persist),
    ("Loop-and-arena diet matches arena-only diet", "No-go. Rethink the task", (), same_diet),
    ("Direction units appear in place_only but no axis units", "Report as a pilot observation, not a failure",
     ("place_only",), direction_only),
)


def table_of(facts, input_sets, thr, failed):
    """
    The eight rows as (result, decision if yes, answer True, False or None, numbers); None when an input set is missing.
    """
    table = []
    for result, decision, needed, answer_of in ROWS:
        absent = [s for s in needed if s not in input_sets]
        answer, numbers = ((None, f"cannot be computed: {', '.join(absent)} not being run") if absent
                           else answer_of(facts, thr))
        table.append((result, decision, None if answer is None else bool(answer), numbers))
    table.append(("Section 2 checks fail", "Fix the task first", bool(failed),
                  "; ".join(failed) or "all section 2 checks pass"))
    return table


def table_lines(table):
    """
    The table as printable lines, three per row.
    """
    lines = []
    for number, (result, decision, answer, numbers) in enumerate(table, 1):
        mark = {True: "yes", False: "no", None: "n/a"}[answer]
        lines += [f"{number}. [{mark:>3}] {result}", f"         {numbers}", f"         if yes: {decision}"]
    return lines


def verdict_of(table, failed):
    """
    Go is the first of rows 1 to 3 that holds, else No-go; rows 4 to 6 are named beside it and row 7 is noted.
    """
    def holding(numbers):
        return [n for n in numbers if table[n - 1][2] is True]

    go, nogo = holding((1, 2, 3)), holding((4, 5, 6))
    unknown = [n for n in (1, 2, 3) if table[n - 1][2] is None]
    named = ", ".join(f"row {n} ({table[n - 1][0]})" for n in nogo)
    if go:
        verdict = f"{table[go[0] - 1][1]} (row {go[0]} holds)" + (f"; qualified by {named}" if nogo else "")
    else:
        verdict = "No-go" + (f" ({named})" if nogo else " (no input set meets the bar)")
        if unknown:
            verdict += (f"; {'row' if len(unknown) == 1 else 'rows'} {', '.join(str(n) for n in unknown)} cannot be "
                        f"computed because their input sets are not being run, so this is not final")
    if holding((7,)):
        verdict += f". Row 7 holds ({table[6][0]}): {table[6][1]}"
    if failed:
        verdict = "Fix the task first, the section 2 checks failed. The other rows alone would say: " + verdict
    return verdict
