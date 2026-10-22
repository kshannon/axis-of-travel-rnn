"""
The conversion from the camera to the room: pixels to metres under an epoch's registration, and the camera heading to the room's.
"""

import numpy as np

from .cuts import inside

# The camera's y axis points down and the room's north is up, so every epoch is flipped.
FLIP = True


def wrapped(angle):
    """
    An angle in radians wrapped to the interval from minus pi to pi.
    """
    return (angle + np.pi) % (2 * np.pi) - np.pi


def rotated(x, y, angle):
    """
    The points rotated counterclockwise by the angle about the origin.
    """
    return x * np.cos(angle) - y * np.sin(angle), x * np.sin(angle) + y * np.cos(angle)


def to_room(x_px, y_px, scale, flip, rotation, offset):
    """
    Pixels to room metres: y negated when flip, divided by the scale, rotated counterclockwise by rotation, then shifted by offset.
    """
    x, y = rotated(x_px / scale, (-y_px if flip else y_px) / scale, rotation)
    return x + offset[0], y + offset[1]


def heading_to_room(head_dir, led_offset_rad, rotation_rad):
    """
    Camera heading to room heading: negated for the y flip, the LED offset taken off so 0 is the direction of travel on average, the rotation added, wrapped.
    """
    return wrapped(-(head_dir - led_offset_rad) + rotation_rad)


def to_metres(frames, epochs, found):
    """
    The mashup positions in room metres, each epoch under its kind's parameters and NaN outside the epochs.
    """
    x, y = np.full(len(frames["frame"]), np.nan), np.full(len(frames["frame"]), np.nan)
    for epoch in epochs:
        p, here = found[epoch["epoch"]], inside(frames, epoch)
        x[here], y[here] = to_room(frames["mashup_x"][here], frames["mashup_y"][here], p["scale_px_per_m"], p["flip"], p["rotation_rad"], p["offset_m"])
    return x, y
