"""
The labels on a scripted track block of two and a half trips and on an arena block.
"""

import numpy as np

from process_lab_data import labels

from .conftest import RATE_HZ

# A track block over frames 1001 to 2000 at 0.4 m/s. Run 1 (outbound) starts before the block, so the block opens in a
# partial trip. Run 2 (return) holds a 71 frame stop, a pause, and a 21 frame one, too short. Run 3 (outbound) opens
# trip 2 and overlaps run 4 (return) by three frames, which the later run owns. Run 5 (outbound) opens the last trip,
# complete since run 6 (return) ends inside the block, the dwell after it running to the block end. Run 7 duplicates
# run 3 and run 8 lies beyond the block. A stop of 80 frames between runs 2 and 3 is a dwell, not a pause. A block ending
# at CUT_END, inside run 6, cuts that trip, one ending on run 6's last frame completes it. A stop inside run 2 of
# PAUSE_MIN_S exactly, 60 frames, is not a pause, one frame more is.
BLOCK = (1001, 2000)
CUT_END = 1930
RETURN_END = 1950
STOP_START, BOUNDARY_FRAMES = 1200, 60
SPEED_M_S = 0.4
STOPS = ((1200, 1270), (1280, 1300), (1320, 1399))
RUNS = [
    {"run": 1, "path_id": 1, "frame_start": 900, "frame_end": 1100, "clean": True, "duplicate_of": None},
    {"run": 2, "path_id": 9, "frame_start": 1150, "frame_end": 1300, "clean": False, "duplicate_of": None},
    {"run": 3, "path_id": 2, "frame_start": 1400, "frame_end": 1552, "clean": True, "duplicate_of": None},
    {"run": 4, "path_id": 10, "frame_start": 1550, "frame_end": 1650, "clean": True, "duplicate_of": None},
    {"run": 5, "path_id": 3, "frame_start": 1700, "frame_end": 1800, "clean": True, "duplicate_of": None},
    {"run": 6, "path_id": 9, "frame_start": 1900, "frame_end": 1950, "clean": True, "duplicate_of": None},
    {"run": 7, "path_id": 2, "frame_start": 1400, "frame_end": 1552, "clean": True, "duplicate_of": 3},
    {"run": 8, "path_id": 1, "frame_start": 2100, "frame_end": 2200, "clean": True, "duplicate_of": None},
]
# first, last, run, path_id, clean, phase, trip over the block, written out.
EXPECTED = [
    (1001, 1100, 1, 1, True, "outbound", -1), (1101, 1149, 0, 0, False, "dwell", -1),
    (1150, 1199, 2, 9, False, "return", -1), (1200, 1270, 2, 9, False, "pause", -1),
    (1271, 1300, 2, 9, False, "return", -1), (1301, 1399, 0, 0, False, "dwell", -1),
    (1400, 1549, 3, 2, True, "outbound", 2), (1550, 1650, 4, 10, True, "return", 2),
    (1651, 1699, 0, 0, False, "dwell", 2),
    (1700, 1800, 5, 3, True, "outbound", 3), (1801, 1899, 0, 0, False, "dwell", 3),
    (1900, 1950, 6, 9, True, "return", 3), (1951, 2000, 0, 0, False, "dwell", 3),
]


def block_frames(first, last, epoch, stops=STOPS):
    """
    A block's frames with the scripted speed: SPEED_M_S everywhere but the stops.
    """
    frame = np.arange(first, last + 1)
    speed = np.full(len(frame), SPEED_M_S)
    for start, end in stops:
        speed[(frame >= start) & (frame <= end)] = 0.0
    return {"frame": frame, "epoch": np.full(len(frame), epoch, object), "speed": speed}


def expected(column):
    """
    One expected column over the block from the EXPECTED spans.
    """
    return np.concatenate([[row[column]] * (row[1] - row[0] + 1) for row in EXPECTED])


def test_a_track_block_gets_its_runs_phases_and_trips_with_the_block_edges_cutting_partial_trips():
    got = labels.label_frames(block_frames(*BLOCK, "track"), RUNS, RATE_HZ)
    for index, name in enumerate(("run", "path_id", "clean", "phase", "trip"), 2):
        assert np.array_equal(got[name], expected(index)), name
    assert got["run"].dtype == np.int32 and got["phase"].dtype.kind == "U" and got["trip"].dtype == np.int32


def test_an_arena_block_is_forage_throughout_with_no_run_and_no_trip():
    got = labels.label_frames(block_frames(1, 600, "arena"), RUNS, RATE_HZ)
    assert (got["phase"] == "forage").all() and not got["run"].any() and not got["trip"].any() and not got["clean"].any()


def test_a_block_opening_on_an_outbound_start_opens_a_complete_trip_and_a_block_end_inside_the_return_cuts_one():
    got = labels.label_frames(block_frames(1400, 2000, "track"), RUNS, RATE_HZ)
    assert got["trip"][0] == 1 and got["trip"][299] == 1 and got["trip"][300] == 2 and got["trip"][-1] == 2
    cut = labels.label_frames(block_frames(1400, CUT_END, "track"), RUNS, RATE_HZ)
    assert cut["trip"][299] == 1 and cut["trip"][300] == -2 and cut["trip"][-1] == -2 and cut["phase"][-1] == "return"
    assert labels.label_frames(block_frames(1400, RETURN_END, "track"), RUNS, RATE_HZ)["trip"][-1] == 2
    assert labels.label_frames(block_frames(1400, RETURN_END - 1, "track"), RUNS, RATE_HZ)["trip"][-1] == -2


def test_a_stop_inside_a_run_is_a_pause_only_when_longer_than_pause_min_s():
    frame = np.arange(BLOCK[0], BLOCK[1] + 1)
    for extra, paused in ((0, False), (1, True)):
        stop = (STOP_START, STOP_START + BOUNDARY_FRAMES - 1 + extra)
        phase = labels.label_frames(block_frames(*BLOCK, "track", (stop,)), RUNS, RATE_HZ)["phase"]
        assert np.array_equal(phase == "pause", paused & (frame >= stop[0]) & (frame <= stop[1]))
