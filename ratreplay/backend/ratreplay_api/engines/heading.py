"""
A session's speed, direction of motion and heading from its frames: the processor's own offset, still frames and fills.
"""

import numpy as np

from process_lab_data import frame, select


def track(frames, epochs, rate_hz):
    """
    Speed in px/s and the direction of motion per frame, the heading filled and corrected by the LED offset, the offset and its concentration, and the spans of heading lost, interpolated and held.
    """
    speed, motion = frame.motion(frames)
    offset, concentration, _ = frame.led_offset(frames)
    filled, kind = select.fill_heading(frames["head_dir"], frames["t"], frame.still(frames, epochs), rate_hz)
    spans = {"lost": select.spans(frames["frame"], np.isnan(filled)),
             "filled": select.spans(frames["frame"], kind == select.INTERPOLATED),
             "held": select.spans(frames["frame"], kind == select.HELD)}
    return {"speed": speed, "motion": motion, "heading": frame.wrapped(filled - offset),
            "led_offset": {"rad": offset, "r": concentration}, "spans": spans}
