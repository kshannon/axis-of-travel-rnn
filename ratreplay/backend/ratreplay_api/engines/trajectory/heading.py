"""
Heading: the LED offset from the direction of motion, the frames where the rat is still, the gaps filled along the shortest arc or held while it is still, and the spans lost, filled and held.
"""

import numpy as np

from .cuts import inside, pauses, runs_of, spans
from .frame import led_distance_px
from .kinematics import pixel_motion, smoothed

# How a frame's heading was filled, and the keys of the spans.
UNTOUCHED, INTERPOLATED, HELD = 0, 1, 2
SPAN_KEYS = ("lost", "filled", "held")


def led_offset(frames, rules):
    """
    The circular mean (rad) and concentration r of head_dir minus the motion direction over running frames in camera coordinates, and their count: the light bar's mounting angle.
    """
    speed, direction = pixel_motion(frames, rules)
    heading = frames["head_dir"]
    running = (speed > rules["running_px_per_s"]) & np.isfinite(heading) & np.isfinite(direction)
    z = np.exp(1j * (heading[running] - direction[running])).sum() / max(running.sum(), 1)
    return float(np.angle(z)), float(np.abs(z)), int(running.sum())


def steady_speed(frames, rules):
    """
    The mashup speed in px/s averaged over the steps that do not cross a light switch, where the mashup moves without the rat.
    """
    step = np.hypot(np.diff(frames["mashup_x"]), np.diff(frames["mashup_y"])) / np.diff(frames["t"])
    front, back = frames["unfilled_front"], frames["unfilled_back"]
    kept = ~((front[1:] != front[:-1]) | (back[1:] != back[:-1]))
    return smoothed(np.where(kept, step, 0.0), rules) / smoothed(kept.astype(float), rules)


def still(frames, epochs, rules):
    """
    True on a frame of one of the epochs whose steady speed is under running_floor_m_per_s at the epoch's nominal scale, its LED distance over the nominal LED separation.
    """
    speed = steady_speed(frames, rules)
    floor_px = np.full(len(speed), np.nan)
    for epoch in epochs:
        floor_px[inside(frames, epoch)] = rules["running_floor_m_per_s"] * led_distance_px(frames, epoch) / rules["nominal_led_separation_m"]
    return speed < floor_px


def fill(heading, t, still_frames, rate_hz, rules):
    """
    The heading with its NaN gaps free of pauses filled, up to heading_fill_s along the shortest arc and longer ones by the last heading while the rat is still throughout, and the kind of fill per frame.
    """
    filled, kind = heading.copy(), np.full(len(heading), UNTOUCHED, np.int8)
    pause = pauses(t, rules)
    longest = round(rules["heading_fill_s"] * rate_hz)
    for first, stop in runs_of(np.isnan(heading)):
        if first == 0 or stop == len(heading) or pause[first:stop + 1].any():
            continue
        start = heading[first - 1]
        if stop - first > longest:
            if still_frames[first:stop].all():
                filled[first:stop], kind[first:stop] = start, HELD
            continue
        turn = (heading[stop] - start + np.pi) % (2 * np.pi) - np.pi
        fraction = np.arange(1, stop - first + 1) / (stop - first + 1)
        filled[first:stop] = (start + turn * fraction + np.pi) % (2 * np.pi) - np.pi
        kind[first:stop] = INTERPOLATED
    return filled, kind


def fill_spans(frame, filled, kind):
    """
    The (first, last) frame pairs where the heading is still lost, was interpolated and was held.
    """
    masks = (np.isnan(filled), kind == INTERPOLATED, kind == HELD)
    return {key: spans(frame, mask) for key, mask in zip(SPAN_KEYS, masks)}
