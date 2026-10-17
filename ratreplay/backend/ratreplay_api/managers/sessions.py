"""
The sessions of the transformed folder: the index rows, and one session for the replay.
"""

from ..engines import cuts, edits, heading, occupancy
from ..stores import review, transformed

# The keys of an epoch and of a run the browser gets.
EPOCH_KEYS = ("epoch", "environment", "condition", "frame_start", "frame_end", "duration_s")
RUN_KEYS = ("run", "epoch", "path_id", "clean", "frame_start", "frame_end")

# The automatic block count of a session, counted from its frames once per version of the frames file and kept for the
# life of the process, since counting reads every session's frames.
AUTOMATIC_COUNTS = {}


def picked(row, keys):
    """
    The row with only these keys.
    """
    return {key: row[key] for key in keys}


def automatic_count(root, session, epochs):
    """
    The number of automatic blocks of the session, none when the converter wrote no frames file for it.
    """
    path = transformed.frames_path(root, session["session_id"])
    if not path.is_file():
        return None
    key = (path, path.stat().st_mtime_ns)
    if key not in AUTOMATIC_COUNTS:
        AUTOMATIC_COUNTS[key] = len(cuts.automatic_blocks(transformed.read_frames(root, session["session_id"]), session, epochs))
    return AUTOMATIC_COUNTS[key]


def review_facts(saved, rate_hz):
    """
    What the index shows of a review: when and by whom, the blocks kept and their seconds per epoch kind, the notes.
    """
    saved = saved or {}
    kept = [b for b in saved.get("blocks", []) if b["status"] in edits.KEPT_STATUSES]
    return {"reviewed": bool(saved), "reviewed_at": saved.get("reviewed_at"), "reviewed_by": saved.get("reviewed_by"),
            "n_confirmed": len(kept), "notes": saved.get("notes", ""),
            "confirmed_s": {kind: sum((b["frame_end"] - b["frame_start"] + 1) / rate_hz for b in kept if b["epoch"] == kind)
                            for kind in cuts.EPOCH_KINDS}}


def index(root, processed_root):
    """
    Every session with an arena or track epoch, the dataset's sessions first, then unreviewed, then the oldest review first.
    """
    tables = transformed.read_tables(root)
    dataset = cuts.in_dataset(tables)
    rows = []
    for session in tables["sessions"]:
        session_id = session["session_id"]
        epochs = [e for e in tables["epochs"] if e["session_id"] == session_id]
        if not any(e["epoch"] in cuts.EPOCH_KINDS for e in epochs):
            continue
        runs = [r for r in tables["runs"] if r["session_id"] == session_id]
        rows.append({**session, "date": str(session["date"]), "epochs": [picked(e, EPOCH_KEYS) for e in epochs],
                     "n_runs": len(runs), "n_clean_runs": sum(1 for r in runs if r["clean"]), "in_dataset": session_id in dataset,
                     "n_automatic": automatic_count(root, session, epochs),
                     **review_facts(review.read(processed_root, session_id), session["rate_hz"])})
    return sorted(rows, key=lambda s: (not s["in_dataset"], s["reviewed"], s["reviewed_at"] or ""))


def header(root, session_id):
    """
    One session's facts: its epochs and runs, the epochs that are cut into blocks, what cut it, the heading fills, the LED offset, the occupancy per epoch and the automatic blocks.
    """
    found = transformed.read_session(root, session_id)
    session, epochs, frames = found["session"], found["epochs"], found["frames"]
    rate_hz, max_gap = session["rate_hz"], session["max_gap"]
    track = heading.track(frames, epochs, rate_hz)
    return {"session_id": session_id, "subject_id": session["subject_id"], "date": str(session["date"]), "protocol": session["protocol"],
            "group": session["group"], "rate_hz": rate_hz, "max_gap": max_gap, "n_frames": len(frames["t"]),
            "epochs": [picked(e, EPOCH_KEYS) for e in epochs], "block_epochs": [e["epoch"] for e in cuts.selected(epochs)],
            "runs": [picked(r, RUN_KEYS) for r in found["runs"]], "cuts": cuts.cut_points(frames, epochs, max_gap, rate_hz),
            "heading_lost": track["spans"]["lost"], "heading_filled": track["spans"]["filled"], "heading_held": track["spans"]["held"],
            "led_offset": track["led_offset"], "occupancy": occupancy.occupancy(frames, epochs),
            "blocks": cuts.automatic_blocks(frames, session, epochs)}


def arrays(root, session_id):
    """
    One session's arrays over every frame: time, the mashup light's position in pixels, the corrected and filled heading, the speed in px/s, the direction of motion and the number of lights.
    """
    found = transformed.read_session(root, session_id)
    frames = found["frames"]
    track = heading.track(frames, found["epochs"], found["session"]["rate_hz"])
    return {"t": frames["t"], "x": frames["mashup_x"], "y": frames["mashup_y"], "heading": track["heading"], "speed": track["speed"],
            "motion": track["motion"], "n_lights": (2 - frames["unfilled_front"] - frames["unfilled_back"]).astype("int8")}
