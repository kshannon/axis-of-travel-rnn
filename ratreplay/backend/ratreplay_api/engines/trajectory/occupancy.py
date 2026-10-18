"""
Where a session spent its frames: a count grid per epoch kind over the room, in metres.
"""

import numpy as np

from .cuts import inside

# Bins per axis of the grid, which spans the largest room of the session's environments so the epochs share one frame.
BINS = 80


def occupancy(frames, epochs, x, y, environment):
    """
    The room position counts per epoch kind on one grid: the x and y extent, by kind the counts row by row from the lowest y, and how many positions fell outside the grid.
    """
    room = np.max([environment[e["environment"]]["room"] for e in epochs], axis=0)
    extent = [[0.0, float(room[0])], [0.0, float(room[1])]]
    present = np.isfinite(x) & np.isfinite(y)
    counts, outside = {}, 0
    for epoch in epochs:
        here = present & inside(frames, epoch)
        grid, _, _ = np.histogram2d(x[here], y[here], bins=BINS, range=extent)
        counts[epoch["epoch"]] = grid.T.astype(int).ravel().tolist()
        outside += int(here.sum() - grid.sum())
    return {"bins": BINS, "x": extent[0], "y": extent[1], "counts": counts, "outside": outside}
