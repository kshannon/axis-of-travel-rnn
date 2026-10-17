"""
The training window settings over the processed blocks: how many windows a block yields and the checks of each, its heading and trip shares, the verdict on each block, the totals, and the settings file the training pipeline reads.
"""

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from process_lab_data.labels import RETURN_PATHS
from process_lab_data.select import runs_of
from proj_helpers.paths import repo_root

from .trajectory import KINDS

# A training window is WINDOW_S of a block followed by HORIZON_S of future position to predict, the first BURN_IN_S of
# it warming the network up, taken every STRIDE_S from the block start, at TRAIN_RATE_HZ after resampling. A block is
# trouble when no window fits, when under MIN_HEADING_MEASURED of its frames carry a measured heading (the share an HD
# arm needs), or when a track block holds fewer than MIN_COMPLETE_TRIPS complete trips (the stubs at a block's edges are always partial). These are the defaults the settings dict carries
# under DEFAULTS. The settings the training pipeline reads, and nothing else, live in CONFIG in the repository.
WINDOW_S = 40.0
STRIDE_S = 10.0
BURN_IN_S = 1.0
HORIZON_S = 0.5
TRAIN_RATE_HZ = 20
MIN_HEADING_MEASURED = 0.8
MIN_COMPLETE_TRIPS = 1
DEFAULTS = {"window_s": WINDOW_S, "stride_s": STRIDE_S, "burn_in_s": BURN_IN_S, "horizon_s": HORIZON_S,
            "train_rate_hz": TRAIN_RATE_HZ, "min_heading_measured": MIN_HEADING_MEASURED,
            "min_complete_trips": MIN_COMPLETE_TRIPS}
CONFIG = repo_root() / "configs" / "datasets" / "lab_blocks.yaml"

# Window counts are computed in seconds, so a block exactly as long as one window plus the horizon yields one window
# through float rounding, within this tolerance.
TOLERANCE_S = 1e-9

# The block columns a window's checks read over its range.
CHECK_COLUMNS = ("x", "y", "heading", "heading_filled", "heading_held")

# The verdict reasons, in the order the rules are checked.
NO_WINDOW = "no window fits"
HEADING_UNDER = "measured heading {:.0%} under {:.0%}"
TRIPS_UNDER = "{} complete trips under {}"


def rate_of(row):
    """
    The block's whole frame rate in Hz from its csv row, rounded because duration_s is n_frames over an integer rate and the division does not always come back exact.
    """
    return round(row["n_frames"] / row["duration_s"])


def window_count(n_frames, rate_hz, settings):
    """
    How many windows of window_s plus horizon_s fit in the block every stride_s, 0 when not even one does.
    """
    usable = n_frames / rate_hz - settings["window_s"] - settings["horizon_s"]
    if usable < -TOLERANCE_S:
        return 0
    return math.floor((usable + TOLERANCE_S) / settings["stride_s"]) + 1


def window_starts(n_frames, rate_hz, settings):
    """
    The start time in seconds from the block start of each window window_count gives.
    """
    return np.arange(window_count(n_frames, rate_hz, settings)) * settings["stride_s"]


def heading_shares(block):
    """
    The share of the block's frames with a measured heading (finite, neither filled nor held), a filled one and a held one.
    """
    n = len(block["heading"])
    measured = np.isfinite(block["heading"]) & ~block["heading_filled"] & ~block["heading_held"]
    return {"measured": float(measured.sum() / n), "filled": float(block["heading_filled"].sum() / n),
            "held": float(block["heading_held"].sum() / n)}


def trip_shares(block):
    """
    The share of the block's trips that are complete (a positive trip number) and partial (a negative one), both 0 with no trip.
    """
    numbers = np.unique(block["trip"][block["trip"] != 0])
    if len(numbers) == 0:
        return {"complete": 0.0, "partial": 0.0}
    return {"complete": float((numbers > 0).sum() / len(numbers)), "partial": float((numbers < 0).sum() / len(numbers))}


def complete_trips(block):
    """
    The number of complete trips in the block, the distinct positive trip numbers.
    """
    return int(len(np.unique(block["trip"][block["trip"] > 0])))


def trip_extents(block):
    """
    The trips of the block as (complete, first, last) frame indices: a complete trip from its outbound start to the end of its return run, any other trip over all of its frames.
    """
    extents = []
    for number in np.unique(block["trip"][block["trip"] != 0]):
        frames = np.flatnonzero(block["trip"] == number)
        first, last = int(frames[0]), int(frames[-1])
        if number > 0:
            returning = np.isin(block["path_id"][first:last + 1], RETURN_PATHS)
            last = first + runs_of(returning)[0][1] - 1
        extents.append((bool(number > 0), first, last))
    return extents


def trips_in(extents, first, stop):
    """
    The trips touching the frames from first to stop (exclusive) as (complete, partial) counts. A trip is complete when its outbound start and its return end both lie inside, partial when the range cuts it or the block did.
    """
    inside = [complete and start >= first and end < stop for complete, start, end in extents if start < stop and end >= first]
    return sum(inside), len(inside) - sum(inside)


def window_rows(block, row, settings):
    """
    Every window the settings give in the block: its frame ranges (indices into the block, stops exclusive) for the whole, the burn-in and the window without its horizon, and its checks over the window plus its horizon. A window is ok when its position is finite throughout and its measured heading share reaches the settings' minimum.
    """
    rate_hz = rate_of(row)
    span = round((settings["window_s"] + settings["horizon_s"]) * rate_hz)
    extents = trip_extents(block)
    rows = []
    for index, start_s in enumerate(window_starts(row["n_frames"], rate_hz, settings)):
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


def verdict(row, block, settings):
    """
    Whether the block is fit for training at the settings and, when not, the first rule it breaks: no window fits, too little measured heading, too few complete trips on the track.
    """
    if window_count(row["n_frames"], row["n_frames"] / row["duration_s"], settings) == 0:
        return False, NO_WINDOW
    measured = heading_shares(block)["measured"]
    if measured < settings["min_heading_measured"]:
        return False, HEADING_UNDER.format(measured, settings["min_heading_measured"])
    complete = complete_trips(block)
    if row["kind"] == "track" and complete < settings["min_complete_trips"]:
        return False, TRIPS_UNDER.format(complete, settings["min_complete_trips"])
    return True, None


def totals(rows, blocks, settings):
    """
    The blocks ok and trouble among the rows, the windows the ok ones yield and their hours, blocks by block_id.
    """
    ok = [row for row in rows if verdict(row, blocks[row["block_id"]], settings)[0]]
    return {"blocks_ok": len(ok), "blocks_trouble": len(rows) - len(ok),
            "windows": sum(window_count(row["n_frames"], row["n_frames"] / row["duration_s"], settings) for row in ok),
            "hours_ok": sum(row["duration_s"] for row in ok) / 3600}


def summarize(rows, blocks, settings):
    """
    The totals per kind and overall, blocks by block_id.
    """
    per_kind = {kind: totals([row for row in rows if row["kind"] == kind], blocks, settings) for kind in KINDS}
    return {**per_kind, "overall": totals(rows, blocks, settings)}


def write_settings(settings, manifest, summary, path):
    """
    Write the settings file: the settings, the processed manifest's timestamp and rules, the summary and when it was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"settings": dict(settings), "processed_manifest_timestamp": manifest["run"]["timestamp"],
                                    "rules": manifest["run"]["rules"], "totals": summary,
                                    "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, sort_keys=False))


def read_settings(path):
    """
    The settings file as a dict.
    """
    return yaml.safe_load(Path(path).read_text())
