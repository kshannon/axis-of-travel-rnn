"""
The labels of a block's frames: run, path_id and clean from the lab's runs, then phase and trip from the runs, the speed and the block's kind.
"""

import numpy as np

from .cuts import runs_of

# The output vocabulary. A frame's phase is outbound or return inside a run by its path, pause over a slow stretch inside
# a run, forage in the arena, and dwell everywhere else on the track (at a reward site, or between runs, before the first
# run or after the last). A block's kind is the kind of its epoch. The dtypes are those of the block parquet's label columns.
PHASES = ("outbound", "dwell", "return", "pause", "forage")
OUTBOUND, DWELL, RETURN, PAUSE, FORAGE = PHASES
ARENA = "arena"
KINDS = ("track", ARENA)
PHASE_DTYPE = "U8"
DTYPES = {"run": np.int32, "path_id": np.int16, "clean": bool, "trip": np.int32}

# A trip is an outbound run, the dwell at the goal, the return and the dwell at the start, so it runs from one outbound
# start to the next, or to the block end. A trip is complete when its outbound run and its return run (the first return
# starting before the next outbound) both lie inside the block. Any other trip (the frames before the first outbound
# start, a trip whose return the block end cuts or that has no return run) is partial and carries a negative number.
# A run marked duplicate_of is skipped, and runs are painted in start order so where two overlap the later one owns the
# shared frames.


def runs_in(frame, runs):
    """
    The runs touching the block's frames, duplicates skipped, in start order.
    """
    first, last = frame[0], frame[-1]
    inside = [r for r in runs if r["duplicate_of"] is None and r["frame_start"] <= last and r["frame_end"] >= first]
    return sorted(inside, key=lambda r: r["frame_start"])


def painted(frame, runs, key):
    """
    One run field per frame, 0 outside any run, a later run overwriting an earlier one where they overlap.
    """
    values = np.zeros(len(frame), DTYPES[key])
    for r in runs:
        values[(frame >= r["frame_start"]) & (frame <= r["frame_end"])] = r[key]
    return values


def pauses(run, speed, rate_hz, rules):
    """
    True on every frame of a stretch inside one run with speed under running_floor_m_per_s for over pause_min_s.
    """
    paused, slow = np.zeros(len(run), bool), speed < rules["running_floor_m_per_s"]
    for number in np.unique(run[run > 0]):
        for first, stop in runs_of(slow & (run == number)):
            if stop - first > rules["pause_min_s"] * rate_hz:
                paused[first:stop] = True
    return paused


def phases(run, path_id, paused, forage, rules):
    """
    The phase per frame: outbound or return inside a run by its path, pause over a slow stretch inside a run, forage in the arena, dwell elsewhere.
    """
    phase = np.full(len(run), DWELL, PHASE_DTYPE)
    phase[(run > 0) & np.isin(path_id, rules["outbound_paths"])] = OUTBOUND
    phase[(run > 0) & np.isin(path_id, rules["return_paths"])] = RETURN
    phase[paused] = PAUSE
    phase[forage] = FORAGE
    return phase


def returned(start, next_start, runs, last, rules):
    """
    Whether the trip opening at this outbound start has a return run starting before the next outbound start and ending by the block's last frame.
    """
    return any(r["path_id"] in rules["return_paths"] and start < r["frame_start"] < next_start and r["frame_end"] <= last for r in runs)


def trips(frame, runs, forage, rules):
    """
    The trip per frame, counted through the block from each outbound start to the next, negative unless its outbound and return runs both lie inside the block, 0 in the arena.
    """
    starts = [r["frame_start"] for r in runs if r["path_id"] in rules["outbound_paths"] and r["frame_start"] >= frame[0]]
    leading = int(not starts or starts[0] > frame[0])
    number = np.searchsorted(starts, frame, side="right") + leading
    complete = [False] * leading + [returned(start, next_start, runs, frame[-1], rules) for start, next_start in zip(starts, starts[1:] + [np.inf])]
    trip = np.where(np.array(complete)[number - 1], number, -number).astype(DTYPES["trip"])
    trip[forage] = 0
    return trip


def label_frames(frame, speed, kind, runs, rate_hz, rules):
    """
    The labels over the block's frames, their speed in m/s and the block's kind, as a dict of arrays in the block parquet's order: phase, trip, run, path_id and clean.
    """
    forage = np.full(len(frame), kind == ARENA)
    inside = runs_in(frame, runs)
    run, path_id = painted(frame, inside, "run"), painted(frame, inside, "path_id")
    return {"phase": phases(run, path_id, pauses(run, speed, rate_hz, rules), forage, rules), "trip": trips(frame, inside, forage, rules),
            "run": run, "path_id": path_id, "clean": painted(frame, inside, "clean")}
