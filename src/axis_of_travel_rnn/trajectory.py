"""
The trajectory schema and the one versioned derivation of speed and turn rate, shared by the lab data processor and the synthetic generator.
"""

import numpy as np
from scipy.signal import savgol_filter

# Speed and turn rate are the first derivative of a Savitzky-Golay fit (Savitzky and Golay 1964) of order SMOOTH_ORDER
# over a window of SMOOTH_WINDOW_S, an odd number of samples at the data's rate. KINEMATICS_VERSION names this
# derivation in every manifest, so a block made under another one is told apart.
KINEMATICS_VERSION = 1
SMOOTH_WINDOW_S = 0.15
SMOOTH_ORDER = 2

# One row per frame of a block, real or synthetic (docs/process_lab_data/spec.md Outputs): time in seconds, position in
# metres, heading in radians (0 along +x, counterclockwise), speed in m/s, turn rate in rad/s, how many LEDs the
# position came from, how the heading was filled, which LEDs the lab interpolated, then the labels.
COLUMNS = {
    "t": "float64", "x": "float64", "y": "float64", "heading": "float64", "speed": "float64", "turn_rate": "float64",
    "n_lights": "int8", "heading_filled": "bool", "heading_held": "bool", "filled_front": "bool", "filled_back": "bool",
    "phase": "U8", "trip": "int32", "run": "int32", "path_id": "int16", "clean": "bool",
}
PHASES = ("outbound", "dwell", "return", "pause", "forage")


def smooth_window(rate_hz):
    """
    SMOOTH_WINDOW_S as an odd number of samples at the rate.
    """
    return round(SMOOTH_WINDOW_S * rate_hz) // 2 * 2 + 1


def derivative(values, rate_hz):
    """
    The first derivative per sample of the Savitzky-Golay fit over smooth_window(rate_hz) samples of order SMOOTH_ORDER.
    """
    return savgol_filter(values, smooth_window(rate_hz), SMOOTH_ORDER, deriv=1, delta=1 / rate_hz)


def finite_stretches(values):
    """
    The (first, stop) index pairs of every stretch of finite values.
    """
    edges = np.flatnonzero(np.diff(np.concatenate(([False], np.isfinite(values), [False])).astype(np.int8)))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


def kinematics(t, x, y, heading, rate_hz):
    """
    Speed in m/s and turn rate in rad/s per frame: the Savitzky-Golay first derivative of x and y, their norm the speed, and of the heading unwrapped over each finite stretch, NaN where the heading is NaN or its stretch is shorter than the window.
    """
    speed = np.hypot(derivative(x, rate_hz), derivative(y, rate_hz))
    turn_rate = np.full(len(heading), np.nan)
    for first, stop in finite_stretches(heading):
        if stop - first >= smooth_window(rate_hz):
            turn_rate[first:stop] = derivative(np.unwrap(heading[first:stop]), rate_hz)
    return speed, turn_rate
