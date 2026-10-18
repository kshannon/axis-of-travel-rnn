"""
The blocks of a session: the kept blocks of its review or its initial blocks, each cut from the session's arrays with kinematics of its own, labelled and given the row the blocks index holds.
"""

import numpy as np

from . import kinematics, labels, room, session
from .frame import TRACK

# The review statuses that are built, the others are dropped, the lab frame's type in a block parquet, and the problems
# a block can have (the processor's per block checks that apply and windows do not cover), each with its count.
KEPT_STATUSES = ("confirmed", "edited")
FRAME_DTYPE = np.int32
POSITION_PROBLEM = "position not finite on {} frames"
STEP_PROBLEM = "t steps irregular, {} frames off the rate"


def block_slice(frame, block):
    """
    The index slice of the block's frames in the session's contiguous frames.
    """
    first = int(np.searchsorted(frame, block["frame_start"]))
    return slice(first, first + block["frame_end"] - block["frame_start"] + 1)


def in_spans(frame, spans):
    """
    True on the frames inside any of the (first, last) frame pairs.
    """
    mask = np.zeros(len(frame), bool)
    for first, last in spans:
        mask |= (frame >= first) & (frame <= last)
    return mask


def block_columns(found, frames, at, kind, runs):
    """
    The block's arrays over its slice, in the block parquet's order: t from the block start, position and filled heading in the room, speed and turn rate from the block alone and the measured heading, the lights, the fills and the labels.
    """
    rate_hz, rules, registration = found["rate_hz"], found["rules"], found["frame"]
    frame, kin, rotation = frames["frame"][at], found["kinematics"], registration[kind]["rotation_rad"]
    x, y = kin["x"][at], kin["y"][at]
    measured = room.heading_to_room(frames["head_dir"][at], registration["led_offset_rad"], rotation)
    speed, _, turn_rate = kinematics.kinematics(x, y, measured, np.zeros(len(frame), bool), rate_hz, rules)
    # The session holds the filled heading under the track's rotation, so it is turned by what the block's kind adds to it.
    heading = room.wrapped(kin["heading"][at] + rotation - registration[TRACK]["rotation_rad"])
    return {"frame": frame.astype(FRAME_DTYPE), "t": frames["t"][at] - frames["t"][at.start], "x": x, "y": y, "heading": heading,
            "speed": speed, "turn_rate": turn_rate, "n_lights": kin["n_lights"][at],
            "heading_filled": in_spans(frame, found["heading_spans"]["filled"]), "heading_held": in_spans(frame, found["heading_spans"]["held"]),
            "filled_front": frames["filled_front"][at], "filled_back": frames["filled_back"][at],
            **labels.label_frames(frame, speed, kind, runs, rate_hz, rules)}


def block_problems(columns, rate_hz, rules):
    """
    How the block breaks the processor's per block checks, as strings with their counts and none when it is fine: frames whose position is NaN, and steps in t off one frame by over t_step_tolerance_s.
    """
    missing = int((np.isnan(columns["x"]) | np.isnan(columns["y"])).sum())
    irregular = int((np.abs(np.diff(columns["t"]) - 1 / rate_hz) > rules["t_step_tolerance_s"]).sum())
    return ([POSITION_PROBLEM.format(missing)] if missing else []) + ([STEP_PROBLEM.format(irregular)] if irregular else [])


def block_row(block, columns, found, session_row, reviewed_by):
    """
    The block's row of the blocks index: the block and its session, where it lies, its runs and trips, the seconds of heading lost, filled and held, its status and reviewer, and the registration and kinematics version it was built under.
    """
    rate_hz, p, run, trip = found["rate_hz"], found["frame"][block["epoch"]], columns["run"], columns["trip"]
    n_frames = len(columns["frame"])
    return {"block_id": block["block_id"], "session_id": session_row["session_id"], "subject_id": session_row["subject_id"],
            "date": str(session_row["date"]), "protocol": session_row["protocol"], "environment": block["environment"],
            "epoch": block["epoch"], "kind": block["epoch"], "frame_start": block["frame_start"], "frame_end": block["frame_end"],
            "n_frames": n_frames, "duration_s": n_frames / rate_hz,
            "n_runs": len(np.unique(run[run > 0])), "n_clean_runs": len(np.unique(run[(run > 0) & columns["clean"]])),
            "n_trips": len(np.unique(np.abs(trip[trip != 0]))), "n_complete_trips": len(np.unique(trip[trip > 0])),
            "heading_lost_s": float(np.isnan(columns["heading"]).sum() / rate_hz), "heading_filled_s": float(columns["heading_filled"].sum() / rate_hz),
            "heading_held_s": float(columns["heading_held"].sum() / rate_hz), "status": block["status"], "reviewed_by": reviewed_by,
            "scale_px_per_m": p["scale_px_per_m"], "rotation_rad": p["rotation_rad"], "led_offset_rad": found["frame"]["led_offset_rad"],
            "kinematics_version": found["rules"]["kinematics_version"]}


def blocks(arrays, review, environment, rules):
    """
    The labelled blocks of a session as a dict, blocks (a list of row, arrays and problems, ready for ProcessedAccess.write_blocks, which ignores the problems), frame (the registration the blocks were built under) and warnings (the session's), from the review's confirmed and edited blocks or from the initial blocks when there is no review.
    """
    found = session.build(arrays, environment, rules)
    frames, session_row = arrays["arrays"], arrays["session"]
    flagged = set() if review is None else set(review["flagged_runs"])
    runs = [r for r in found["runs"] if r["run"] not in flagged]
    kept = found["initial_blocks"] if review is None else [b for b in review["blocks"] if b["status"] in KEPT_STATUSES]
    reviewed_by = None if review is None else review["reviewed_by"]
    built = []
    for block in kept:
        columns = block_columns(found, frames, block_slice(frames["frame"], block), block["epoch"], runs)
        built.append({"row": block_row(block, columns, found, session_row, reviewed_by), "arrays": columns,
                      "problems": block_problems(columns, found["rate_hz"], rules)})
    return {"blocks": built, "frame": found["frame"], "warnings": found["warnings"]}
