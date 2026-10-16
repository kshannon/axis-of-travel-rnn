"""
Run length spans of a block's per frame labels and masks, as index pairs into the block.
"""

import numpy as np

from process_lab_data import select


def value_spans(values):
    """
    The (value, first, last) triples of every run of equal values.
    """
    values = np.asarray(values)
    edges = np.flatnonzero(values[1:] != values[:-1]) + 1
    starts, stops = np.concatenate(([0], edges)), np.concatenate((edges, [len(values)]))
    return [(values[first].item(), int(first), int(stop - 1)) for first, stop in zip(starts, stops)]


def true_spans(mask):
    """
    The [first, last] index pairs of every stretch of True.
    """
    return [[first, stop - 1] for first, stop in select.runs_of(mask)]


def run_spans(block):
    """
    One span per run of the block with its path id and clean flag.
    """
    return [{"run": run, "path_id": int(block["path_id"][first]), "clean": bool(block["clean"][first]), "first": first, "last": last}
            for run, first, last in value_spans(block["run"]) if run != 0]


def trip_spans(block):
    """
    One span per trip of the block, numbered as the processor numbers them, partial when the number is negative.
    """
    return [{"trip": abs(trip), "partial": trip < 0, "first": first, "last": last} for trip, first, last in value_spans(block["trip"]) if trip != 0]


def phase_spans(block):
    """
    One span per stretch of a phase.
    """
    return [{"phase": phase, "first": first, "last": last} for phase, first, last in value_spans(block["phase"])]
