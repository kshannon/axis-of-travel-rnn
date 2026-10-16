"""
The training windows of a block: the project's window logic, and the checks of each window for the Windows page.
"""

import numpy as np

from axis_of_travel_rnn.windows import DEFAULTS, heading_shares, summarize, complete_trips, verdict, window_count, window_starts

__all__ = ["DEFAULTS", "heading_shares", "summarize", "verdict", "window_count", "window_rows"]

# The block columns a window's checks read.
CHECK_COLUMNS = ("x", "y", "heading", "heading_filled", "heading_held", "trip")


def window_rows(block, rate_hz, settings):
    """
    Every window the settings give in the block: its frame ranges (indices into the block, stops exclusive) for the whole, the burn-in and the window without its horizon, and its checks. A window is ok when its position is finite throughout and its measured heading share reaches the settings' minimum.
    """
    span = round((settings["window_s"] + settings["horizon_s"]) * rate_hz)
    rows = []
    for index, start_s in enumerate(window_starts(len(block["t"]), rate_hz, settings)):
        first = round(start_s * rate_hz)
        part = {name: block[name][first:first + span] for name in CHECK_COLUMNS}
        finite = float(np.mean(np.isfinite(part["x"]) & np.isfinite(part["y"])))
        measured = heading_shares(part)["measured"]
        rows.append({"index": index, "first": first, "burn_in_stop": first + round(settings["burn_in_s"] * rate_hz),
                     "window_stop": first + round(settings["window_s"] * rate_hz), "stop": first + len(part["x"]),
                     "position_finite": finite, "heading_measured": measured, "trips_complete": complete_trips(part),
                     "trips_partial": len(np.unique(part["trip"][part["trip"] < 0])),
                     "ok": bool(finite == 1.0 and measured >= settings["min_heading_measured"])})
    return rows
