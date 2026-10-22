"""
Heading: the LED offset from the direction of motion, the frames where the rat is still, the gaps filled along the shortest arc or held while it is still, and the spans lost, filled and held, each with its reason.
"""

import numpy as np

from .cuts import inside, pauses, runs_of
from .frame import led_distance_px
from .kinematics import pixel_motion, smoothed

# The keys of the spans, and the reason each span carries: why a gap was left missing, or how it was filled.
SPAN_KEYS = ("lost", "filled", "held")
LOST, FILLED, HELD = SPAN_KEYS
OVER_LIMIT = "over the fill limit of {limit:g} s"
HAS_PAUSE = "contains a pause"
AT_START = "touches the start of the recording"
AT_END = "touches the end of the recording"
NO_SIDE = "no measured heading on either side"
ARC = "along the shortest arc"
STILL = "the rat was still"


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


def unfillable(first, stop, length, pause):
    """
    Why the gap from index first to stop cannot be filled whatever the rat does, none when it can: it touches an end of the recording or holds a pause.
    """
    if first == 0 and stop == length:
        return NO_SIDE
    if first == 0:
        return AT_START
    if stop == length:
        return AT_END
    return HAS_PAUSE if pause[first:stop + 1].any() else None


def fill(heading, t, still_frames, rate_hz, rules):
    """
    The heading with its NaN gaps free of pauses filled, up to heading_fill_s along the shortest arc and longer ones by the last heading while the rat is still throughout, and for every gap its (first, stop) indices, span key and reason.
    """
    filled, found = heading.copy(), []
    pause = pauses(t, rules)
    longest = round(rules["heading_fill_s"] * rate_hz)
    for first, stop in runs_of(np.isnan(heading)):
        reason = unfillable(first, stop, len(heading), pause)
        if reason:
            found.append((first, stop, LOST, reason))
            continue
        start = heading[first - 1]
        if stop - first > longest:
            if still_frames[first:stop].all():
                filled[first:stop] = start
                found.append((first, stop, HELD, STILL))
            else:
                found.append((first, stop, LOST, OVER_LIMIT.format(limit=rules["heading_fill_s"])))
            continue
        turn = (heading[stop] - start + np.pi) % (2 * np.pi) - np.pi
        fraction = np.arange(1, stop - first + 1) / (stop - first + 1)
        filled[first:stop] = (start + turn * fraction + np.pi) % (2 * np.pi) - np.pi
        found.append((first, stop, FILLED, ARC))
    return filled, found


def fill_spans(frame, found, rate_hz):
    """
    The spans of the gaps fill found, by key lost, filled and held: each the first and last lab frame, the seconds and the reason.
    """
    spans = {key: [] for key in SPAN_KEYS}
    for first, stop, key, reason in found:
        spans[key].append({"first": int(frame[first]), "last": int(frame[stop - 1]), "seconds": float((stop - first) / rate_hz), "reason": reason})
    return spans
