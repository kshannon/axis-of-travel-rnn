"""
Spans over a block's arrays: the stretches of equal values as indices, and the runs, trips and phases of a built block as the pages draw them.
"""

from itertools import groupby


def spans_of(values):
    """
    The (value, first, last) of every stretch of equal values, as indices into the values.
    """
    spans, first = [], 0
    for value, group in groupby(values):
        last = first + sum(1 for _ in group) - 1
        spans.append((value, first, last))
        first = last + 1
    return spans


def true_spans(mask):
    """
    The [first, last] index pairs of every stretch of True.
    """
    return [[first, last] for value, first, last in spans_of(mask.tolist()) if value]


def runs_of(arrays):
    """
    One span per run of the block with its path id and clean flag, a zero being no run.
    """
    return [{"run": run, "path_id": int(arrays["path_id"][first]), "clean": bool(arrays["clean"][first]), "first": first, "last": last}
            for run, first, last in spans_of(arrays["run"].tolist()) if run != 0]


def trips_of(arrays):
    """
    One span per trip of the block, numbered as the build numbers them, partial when the number is negative, a zero being no trip.
    """
    return [{"trip": abs(trip), "partial": trip < 0, "first": first, "last": last} for trip, first, last in spans_of(arrays["trip"].tolist()) if trip != 0]


def phases_of(arrays):
    """
    One span per stretch of a phase.
    """
    return [{"phase": phase, "first": first, "last": last} for phase, first, last in spans_of(arrays["phase"].tolist())]
