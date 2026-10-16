"""
The labels per frame of a block: run, path_id and clean from the lab's clicks, then phase and trip (spec Runs, trips and phase labels).
"""

import numpy as np

from axis_of_travel_rnn.trajectory import COLUMNS

from .select import RUNNING_FLOOR_M_PER_S

# The lab's path ids: 1 to 4 run from the start to a goal, 9 and 10 return along the perimeter. A frame of a run is
# outbound or return by its path. Inside a run, a stretch of speed under select.RUNNING_FLOOR_M_PER_S (the paper's
# floor, the one the held heading fill uses too) for over PAUSE_MIN_S is a pause. Every other track frame is a dwell:
# the rat is at a reward site or between runs, before the first run of the block or after its last one as much as
# between two, and the trip number says which trip it belongs to. Every arena frame is forage. A run marked
# duplicate_of is skipped, and runs are painted in start order so where two overlap the later one owns the shared
# frames (tables.md 3.1).
OUTBOUND_PATHS = (1, 2, 3, 4)
RETURN_PATHS = (9, 10)
PAUSE_MIN_S = 1.0
ARENA = "arena"

# A trip is an outbound run, the dwell at the goal, the return and the dwell at the start, so it runs from one outbound
# start to the next, or to the block end. Trips are counted through the block. A trip is complete when its outbound run
# and its return run (the first return starting before the next outbound) both lie inside the block, the dwell after
# the return included when present. Any other trip (the frames before the first outbound start, a trip whose return
# the block end cuts or that has no return run) is partial and carries a negative number.


def runs_of(mask):
    """
    The (first, stop) index pairs of every stretch where the mask is true.
    """
    edges = np.flatnonzero(np.diff(np.concatenate(([False], mask, [False])).astype(np.int8)))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


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
    values = np.zeros(len(frame), COLUMNS[key])
    for r in runs:
        values[(frame >= r["frame_start"]) & (frame <= r["frame_end"])] = r[key]
    return values


def pauses(run, speed, rate_hz):
    """
    True on every frame of a stretch inside one run with speed under RUNNING_FLOOR_M_PER_S for over PAUSE_MIN_S.
    """
    paused, slow = np.zeros(len(run), bool), speed < RUNNING_FLOOR_M_PER_S
    for number in np.unique(run[run > 0]):
        for first, stop in runs_of(slow & (run == number)):
            if stop - first > PAUSE_MIN_S * rate_hz:
                paused[first:stop] = True
    return paused


def phases(run, path_id, paused, forage):
    """
    The phase per frame: outbound or return inside a run by its path, pause over a slow stretch inside a run, forage in the arena, dwell elsewhere.
    """
    phase = np.full(len(run), "dwell", COLUMNS["phase"])
    phase[(run > 0) & np.isin(path_id, OUTBOUND_PATHS)] = "outbound"
    phase[(run > 0) & np.isin(path_id, RETURN_PATHS)] = "return"
    phase[paused] = "pause"
    phase[forage] = "forage"
    return phase


def returned(start, next_start, runs, last):
    """
    Whether the trip opening at this outbound start has a return run starting before the next outbound start and ending by the block's last frame.
    """
    return any(r["path_id"] in RETURN_PATHS and start < r["frame_start"] < next_start and r["frame_end"] <= last for r in runs)


def trips(frame, runs, forage):
    """
    The trip per frame, counted through the block from each outbound start to the next, negative unless its outbound and return runs both lie inside the block, 0 in the arena.
    """
    starts = [r["frame_start"] for r in runs if r["path_id"] in OUTBOUND_PATHS and r["frame_start"] >= frame[0]]
    leading = int(not starts or starts[0] > frame[0])
    number = np.searchsorted(starts, frame, side="right") + leading
    complete = [False] * leading + [returned(start, next_start, runs, frame[-1]) for start, next_start in zip(starts, starts[1:] + [np.inf])]
    trip = np.where(np.array(complete)[number - 1], number, -number).astype(COLUMNS["trip"])
    trip[forage] = 0
    return trip


def label_frames(block_frames, runs_of_session, rate_hz):
    """
    The labels over the block's frames (frame, epoch and speed in m/s) as a dict of arrays: run, path_id, clean, phase and trip.
    """
    frame, forage = block_frames["frame"], block_frames["epoch"] == ARENA
    runs = runs_in(frame, runs_of_session)
    run, path_id = painted(frame, runs, "run"), painted(frame, runs, "path_id")
    paused = pauses(run, block_frames["speed"], rate_hz)
    return {"run": run, "path_id": path_id, "clean": painted(frame, runs, "clean"),
            "phase": phases(run, path_id, paused, forage), "trip": trips(frame, runs, forage)}
