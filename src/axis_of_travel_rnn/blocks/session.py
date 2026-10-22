"""
One session: the processor's sequence of cutting, heading fills and registration, then kinematics in metres, stops and the initial blocks.
"""

import numpy as np

from . import cuts, frame, heading, kinematics, room

# What a session that cannot be registered says, and the processor's session warnings: track scale estimates that
# disagree (the sign of an outer corridor peak the occupancy did not find) and a kind's LED separation out of range.
NO_TRACK = "session {sid} has no track epoch under condition {condition}, registration needs one"
AXES_WARNING = "{sid} track scale x and y differ by {percent:.0f} percent, over {allowed:g}: an outer corridor peak missed?"
SEPARATION_WARNING = "{sid} {kind} LED separation {cm:.1f} cm outside {low:g} to {high:g}"


def warnings_of(sid, registration, rules):
    """
    The warnings one session alone can give: the track's two scale estimates lying apart by over axis_agree of their mean, and each kind's LED separation outside led_separation_m.
    """
    track, found = registration[frame.TRACK], []
    apart = abs(track["scale_x_px_per_m"] - track["scale_y_px_per_m"]) / track["scale_px_per_m"]
    if apart > rules["axis_agree"]:
        found.append(AXES_WARNING.format(sid=sid, percent=100 * apart, allowed=100 * rules["axis_agree"]))
    low, high = rules["led_separation_m"]
    for kind in rules["epochs"]:
        if kind in registration and not low <= registration[kind]["led_separation_m"] <= high:
            found.append(SEPARATION_WARNING.format(sid=sid, kind=kind, cm=100 * registration[kind]["led_separation_m"], low=100 * low, high=100 * high))
    return found


def build(arrays, environment, rules):
    """
    The session dict from a session's arrays as io.session gives them, the geometry of each epoch's environment by name and the rules.
    """
    row, frames, runs = arrays["session"], arrays["arrays"], arrays["runs"]
    rate_hz, max_gap, t = row["rate_hz"], row["max_gap"], frames["t"]
    epochs = cuts.selected(arrays["epochs"], rules)
    if not any(e["epoch"] == frame.TRACK for e in epochs):
        raise ValueError(NO_TRACK.format(sid=row["session_id"], condition=rules["condition"]))
    filled, fills = heading.fill(frames["head_dir"], t, heading.still(frames, epochs, rules), rate_hz, rules)
    offset, concentration, n_running = heading.led_offset(frames, rules)
    registration = frame.parameters(frames, epochs, runs, environment, rules)
    rotation = registration[frame.TRACK]["rotation_rad"]
    x, y = room.to_metres(frames, epochs, registration)
    breaks = cuts.pauses(t, rules) | np.concatenate(([False], np.diff(cuts.epoch_index(frames, epochs)) != 0))
    speed, motion, turn_rate = kinematics.kinematics(x, y, room.heading_to_room(frames["head_dir"], offset, rotation), breaks, rate_hz, rules)
    x_smooth, y_smooth = kinematics.smooth_position(x, y, breaks, rate_hz, rules)
    pieces, margins = zip(*[cuts.cut_epoch(frames, e, max_gap, rate_hz, rules) for e in epochs])
    return {
        "rules": dict(rules), "session_id": row["session_id"], "rate_hz": rate_hz, "n_frames": len(t), "epochs": epochs, "runs": runs,
        "frame": {"led_offset_rad": offset, "led_offset_r": concentration, "led_offset_n": n_running, **registration},
        "warnings": warnings_of(row["session_id"], registration, rules),
        "kinematics": {"t": t, "x": x, "y": y, "x_smooth": x_smooth, "y_smooth": y_smooth, "heading": room.heading_to_room(filled, offset, rotation),
                       "speed": speed, "turn_rate": turn_rate, "motion": motion,
                       "n_lights": (2 - frames["unfilled_front"] - frames["unfilled_back"]).astype(np.int8)},
        "heading_spans": heading.fill_spans(frames["frame"], fills, rate_hz),
        "cut_points": cuts.cut_points(frames, epochs, max_gap, rules),
        "margins": [m for found in margins for m in found],
        "stretches": cuts.stretch_rows(epochs, pieces),
        "initial_blocks": cuts.initial_blocks(row["session_id"], epochs, pieces, rate_hz, rules),
        "stops": kinematics.stops(speed, frames["frame"], rate_hz, rules),
    }
