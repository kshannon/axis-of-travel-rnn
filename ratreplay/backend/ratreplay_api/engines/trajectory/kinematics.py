"""
Motion from the positions: the smoothed pixel speed and direction the registration reads, and speed, direction and turn rate in metres from Savitzky-Golay derivatives.
"""

import numpy as np
from scipy.signal import savgol_filter

from .cuts import runs_of


def smoothed(steps, rules):
    """
    A per-step series as a per-frame series, the first frame repeating the second, averaged over speed_smooth_frames frames.
    """
    kernel = np.ones(rules["speed_smooth_frames"]) / rules["speed_smooth_frames"]
    return np.convolve(np.concatenate([steps[:1], steps]), kernel, mode="same")


def pixel_motion(frames, rules):
    """
    The smoothed speed in px/s and the direction of the smoothed velocity in camera coordinates (y down), from the mashup positions.
    """
    dt, dx, dy = np.diff(frames["t"]), np.diff(frames["mashup_x"]), np.diff(frames["mashup_y"])
    return smoothed(np.hypot(dx, dy) / dt, rules), np.arctan2(smoothed(dy / dt, rules), smoothed(dx / dt, rules))


def smooth_window(rate_hz, rules):
    """
    smooth_window_s as an odd number of samples at the rate.
    """
    return round(rules["smooth_window_s"] * rate_hz) // 2 * 2 + 1


def derivative(values, rate_hz, rules):
    """
    The first derivative per second of the Savitzky-Golay fit over smooth_window samples of order smooth_order.
    """
    return savgol_filter(values, smooth_window(rate_hz, rules), rules["smooth_order"], deriv=1, delta=1 / rate_hz)


def stretches(mask, breaks):
    """
    The (first, stop) index pairs of every stretch where the mask is true, split where a break starts a new one.
    """
    found = []
    for first, stop in runs_of(mask):
        edges = [first, *(np.flatnonzero(breaks[first + 1:stop]) + first + 1).tolist(), stop]
        found += list(zip(edges[:-1], edges[1:]))
    return found


def kinematics(x, y, heading, breaks, rate_hz, rules):
    """
    Speed in m/s, the direction of motion and the turn rate in rad/s per frame, NaN where the position or heading is missing or its stretch, split at the breaks, is shorter than the window.
    """
    window = smooth_window(rate_hz, rules)
    speed, motion, turn_rate = (np.full(len(x), np.nan) for _ in range(3))
    for first, stop in stretches(np.isfinite(x) & np.isfinite(y), breaks):
        if stop - first >= window:
            dx, dy = derivative(x[first:stop], rate_hz, rules), derivative(y[first:stop], rate_hz, rules)
            speed[first:stop], motion[first:stop] = np.hypot(dx, dy), np.arctan2(dy, dx)
    for first, stop in stretches(np.isfinite(heading), breaks):
        if stop - first >= window:
            turn_rate[first:stop] = derivative(np.unwrap(heading[first:stop]), rate_hz, rules)
    return speed, motion, turn_rate


def stops(speed, frame, rate_hz, rules):
    """
    The (first, last) frame pairs of every stretch where the speed stays under running_floor_m_per_s for over pause_min_s, a display quantity of the whole session, distinct from the pause phase the labels give inside runs and from the still frames that gate the held fill.
    """
    slow = np.nan_to_num(speed, nan=np.inf) < rules["running_floor_m_per_s"]
    return [(int(frame[first]), int(frame[stop - 1])) for first, stop in runs_of(slow) if stop - first > rules["pause_min_s"] * rate_hz]
