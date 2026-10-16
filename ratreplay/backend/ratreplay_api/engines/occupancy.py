"""
Where a session spent its frames: a count grid per epoch.
"""

import numpy as np

from process_lab_data import select

# Bins per axis of the grid, which spans the whole session so the epochs share one frame.
BINS = 80


def occupancy(frames, epochs):
    """
    The mashup position counts per epoch on one grid over the session: the x and y extent and, by epoch name, the counts row by row from the lowest y.
    """
    x, y = frames["mashup_x"], frames["mashup_y"]
    present = np.isfinite(x) & np.isfinite(y)
    extent = [[float(x[present].min()), float(x[present].max())], [float(y[present].min()), float(y[present].max())]]
    counts = {}
    for epoch in epochs:
        inside = present & select.inside(frames, epoch)
        grid, _, _ = np.histogram2d(x[inside], y[inside], bins=BINS, range=extent)
        counts[epoch["epoch"]] = grid.T.astype(int).ravel().tolist()
    return {"bins": BINS, "x": extent[0], "y": extent[1], "counts": counts}
