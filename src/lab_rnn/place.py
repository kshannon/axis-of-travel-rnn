"""
Place cells for the lab's rooms: centres drawn from where the rat went, Gaussian rates as RatInABox computes them.
"""

import numpy as np

from .config import OCCUPANCY_BIN


def draw_centres(pos, n, seed):
    """
    n centres (n, 2) in metres, the middles of n occupied OCCUPANCY_BIN bins of pos drawn without replacement.
    """
    occupied = np.unique(np.floor(pos / OCCUPANCY_BIN).astype(np.int64), axis=0)
    assert len(occupied) >= n, f"only {len(occupied)} occupied bins for {n} place centres"
    chosen = np.random.default_rng(seed).choice(len(occupied), size=n, replace=False)
    return (occupied[chosen] + 0.5) * OCCUPANCY_BIN


def rates(pos, centres, width):
    """
    The place cell rates (len(pos), len(centres)) float32: exp(-d^2 / (2 width^2)), d the Euclidean distance.
    """
    squared = ((pos[:, None, :] - centres[None, :, :]) ** 2).sum(axis=-1)
    return np.exp(-squared / (2 * width ** 2)).astype(np.float32)
