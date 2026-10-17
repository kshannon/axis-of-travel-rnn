"""
The training windows of a block: the project's window logic, and the checks of each window for the Windows page.
"""

import numpy as np

from axis_of_travel_rnn.windows import DEFAULTS, heading_shares, summarize, verdict, window_count, window_starts
from process_lab_data import select
from process_lab_data.labels import RETURN_PATHS

from . import spans

__all__ = ["DEFAULTS", "heading_shares", "summarize", "verdict", "window_count", "window_rows"]

# The block columns a window's checks read over its range.
CHECK_COLUMNS = ("x", "y", "heading", "heading_filled", "heading_held")


def trip_extents(block):
    """
    The trips of the block as (complete, first, last) frame indices: a complete trip from its outbound start to the end of its return run, any other trip over all of its frames.
    """
    extents = []
    for trip in spans.trip_spans(block):
        first, last = trip["first"], trip["last"]
        if not trip["partial"]:
            returning = np.isin(block["path_id"][first:last + 1], RETURN_PATHS)
            last = first + select.runs_of(returning)[0][1] - 1
        extents.append((not trip["partial"], first, last))
    return extents


def trips_in(extents, first, stop):
    """
    The trips touching the frames from first to stop (exclusive) as (complete, partial) counts. A trip is complete when its outbound start and its return end both lie inside, partial when the range cuts it or the block did.
    """
    inside = [complete and start >= first and end < stop for complete, start, end in extents if start < stop and end >= first]
    return sum(inside), len(inside) - sum(inside)


def window_rows(block, rate_hz, settings):
    """
    Every window the settings give in the block: its frame ranges (indices into the block, stops exclusive) for the whole, the burn-in and the window without its horizon, and its checks over the window plus its horizon. A window is ok when its position is finite throughout and its measured heading share reaches the settings' minimum.
    """
    span = round((settings["window_s"] + settings["horizon_s"]) * rate_hz)
    extents = trip_extents(block)
    rows = []
    for index, start_s in enumerate(window_starts(len(block["t"]), rate_hz, settings)):
        first = round(start_s * rate_hz)
        part = {name: block[name][first:first + span] for name in CHECK_COLUMNS}
        finite = float(np.mean(np.isfinite(part["x"]) & np.isfinite(part["y"])))
        measured = heading_shares(part)["measured"]
        complete, partial = trips_in(extents, first, first + span)
        rows.append({"index": index, "first": first, "burn_in_stop": first + round(settings["burn_in_s"] * rate_hz),
                     "window_stop": first + round(settings["window_s"] * rate_hz), "stop": first + span,
                     "position_finite": finite, "heading_measured": measured, "trips_complete": complete, "trips_partial": partial,
                     "ok": bool(finite == 1.0 and measured >= settings["min_heading_measured"])})
    return rows
