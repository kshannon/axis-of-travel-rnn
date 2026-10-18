"""
The windows of a built block at window settings with the checks of each, and the verdict of the block.
"""

import math

import numpy as np

from .cuts import runs_of
from .frame import TRACK

# Window counts are computed in seconds, so a block exactly as long as one window plus the horizon yields one window
# through float rounding, within this tolerance.
TOLERANCE_S = 1e-9

# The reasons a window or a block fails, in the order the checks run.
NO_WINDOW = "no window fits"
POSITION_LOST = "position not finite"
HEADING_UNDER = "measured heading {:.0%} under {:.0%}"
TRIPS_UNDER = "{} complete trips under {}"


def window_count(n_frames, rate_hz, settings):
    """
    How many windows of window_s plus horizon_s fit in the block every stride_s, 0 when not even one does.
    """
    usable = n_frames / rate_hz - settings["window_s"] - settings["horizon_s"]
    if usable < -TOLERANCE_S:
        return 0
    return math.floor((usable + TOLERANCE_S) / settings["stride_s"]) + 1


def position_finite(arrays, at):
    """
    The share of the frames in the slice with a finite position.
    """
    return float(np.mean(np.isfinite(arrays["x"][at]) & np.isfinite(arrays["y"][at])))


def heading_measured(arrays, at):
    """
    The share of the frames in the slice with a measured heading, finite and neither filled nor held.
    """
    measured = np.isfinite(arrays["heading"][at]) & ~arrays["heading_filled"][at] & ~arrays["heading_held"][at]
    return float(np.mean(measured))


def trip_extents(arrays, return_paths):
    """
    The trips of the block as (complete, first, last) frame indices: a complete trip from its outbound start to the end of its first stretch of frames on a return path, any other trip over all of its frames.
    """
    extents = []
    for number in np.unique(arrays["trip"][arrays["trip"] != 0]):
        frames = np.flatnonzero(arrays["trip"] == number)
        first, last = int(frames[0]), int(frames[-1])
        if number > 0:
            returning = np.isin(arrays["path_id"][first:last + 1], return_paths)
            last = first + runs_of(returning)[0][1] - 1
        extents.append((bool(number > 0), first, last))
    return extents


def trips_in(extents, first, stop):
    """
    The trips touching the frames from first to stop (exclusive) as (complete, partial) counts. A trip is complete when its outbound start and its return end both lie inside, partial when the range cuts it or the block did.
    """
    inside = [complete and start >= first and end < stop for complete, start, end in extents if start < stop and end >= first]
    return sum(inside), len(inside) - sum(inside)


def window_rows(arrays, extents, count, rate_hz, settings):
    """
    The count windows of the block with their frame ranges (indices into the block, stops exclusive) for the whole, the burn-in and the window without its horizon, their seconds, their checks over the window plus its horizon (the trips inside from the block's trip extents) and the first check each fails.
    """
    span = round((settings["window_s"] + settings["horizon_s"]) * rate_hz)
    rows = []
    for index in range(count):
        start_s = index * settings["stride_s"]
        first = round(start_s * rate_hz)
        at = slice(first, first + span)
        finite, measured = position_finite(arrays, at), heading_measured(arrays, at)
        complete, partial = trips_in(extents, first, first + span)
        if finite < 1.0:
            reason = POSITION_LOST
        elif measured < settings["min_heading_measured"]:
            reason = HEADING_UNDER.format(measured, settings["min_heading_measured"])
        else:
            reason = None
        rows.append({"index": index, "first": first, "burn_in_stop": first + round(settings["burn_in_s"] * rate_hz),
                     "window_stop": first + round(settings["window_s"] * rate_hz), "stop": first + span,
                     "start_s": start_s, "stop_s": start_s + settings["window_s"] + settings["horizon_s"],
                     "position_finite": finite, "heading_measured": measured, "trips_complete": complete, "trips_partial": partial,
                     "ok": reason is None, "reason": reason})
    return rows


def block_verdict(row, arrays, count, settings):
    """
    Whether the block is fit for training and every rule it breaks: no window fits, too little measured heading, too few complete trips on the track.
    """
    measured, complete = heading_measured(arrays, slice(None)), len(np.unique(arrays["trip"][arrays["trip"] > 0]))
    reasons = [NO_WINDOW] if count == 0 else []
    if measured < settings["min_heading_measured"]:
        reasons.append(HEADING_UNDER.format(measured, settings["min_heading_measured"]))
    if row["kind"] == TRACK and complete < settings["min_complete_trips"]:
        reasons.append(TRIPS_UNDER.format(complete, settings["min_complete_trips"]))
    return {"ok": not reasons, "reasons": reasons}


def windows(block, settings, rules):
    """
    The window rows of a block (its row and arrays) at the settings and the rules it was built with, the verdict of the block and the window count, in seconds at the block's own rate.
    """
    row, arrays = block["row"], block["arrays"]
    rate_hz = round(row["n_frames"] / row["duration_s"])
    count = window_count(row["n_frames"], rate_hz, settings)
    extents = trip_extents(arrays, rules["return_paths"])
    return {"rows": window_rows(arrays, extents, count, rate_hz, settings), "verdict": block_verdict(row, arrays, count, settings), "count": count}
