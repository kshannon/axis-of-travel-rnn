"""
Data access for RatReplay: the sessions, one session's arrays, cut points, heading fill and automatic blocks, the edits that make the confirmed blocks, the review file.
"""

import getpass
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from process_lab_data import select
from process_lab_data.frame import still

# The converter's output (docs/transform_lab_data/tables.md 2): the tables, the frames folder and the manifest whose run
# timestamp the review file records. The position shown is the lab's mashup light, present whenever one light is. Floats
# are rounded to this many decimals on their way to the browser.
TABLES = ("sessions", "epochs", "runs")
FRAMES = select.FRAMES
MANIFEST = "manifest.json"
POSITION_COLUMNS = ("mashup_x", "mashup_y")
DECIMALS = 4

# Speed and direction of motion are the position difference over dt averaged over this many frames, the lab's window.
# The LED offset of a session is the circular mean of heading minus motion direction over frames faster than this, in
# px/s. The frames where the heading is held across a long gap are the processor's own still frames (frame.still, under
# select.RUNNING_FLOOR_M_PER_S at the epoch's LED scale). The occupancy background is a 2D histogram per epoch on a grid
# of this many bins per axis spanning the whole session, log scaled.
SPEED_SMOOTH_FRAMES = 6
RUNNING_SPEED = 20
OCCUPANCY_BINS = 80

# What cut the epochs, as the processor's cut_points names them, merged over the epochs of the session.
CUT_KEYS = ("pauses", "jumps", "gaps", "margins")

# The automatic block count per session id, counted from the session's frames the first time the sessions are listed
# or the session is opened, and kept for the life of the process. A save pops the saved session so the next listing
# counts it again. Nothing else reads every session's frames.
AUTOMATIC_COUNTS = {}

# The review folder under PROCESSED_LAB_DATA, one json per session, and the keys a block carries in it. A block's status
# is one of STATUSES, and a block is kept when its status is one of KEPT. The ops that change the block list are applied
# in order by apply_edits: a moved edge snaps to a run start or end within this many seconds and stays inside the stretch
# cut_at drew around the block, so a block never crosses an epoch bound, a pause or a tracking gap. A new block must lie
# in one such stretch, last MIN_BLOCK_S and stay clear of the blocks kept, else it is refused with the message that says
# why. A cut records this reason, and a piece a cut leaves too short, or inside the cut, is dropped with the note that
# says so. A saved review replays its edits against the automatic blocks of the day, so when the processor's rules
# change an edit can lose the block it anchors to, named by ANCHORS, or the room for its new block: such an edit is
# skipped and counted. The file records the rules it was saved under, the processor's constants named in RULE_NAMES.
REVIEW = "review"
SNAP_S = 1.0
BLOCK_KEYS = ("block_id", "epoch", "environment", "frame_start", "frame_end", "status", "note")
STATUSES = ("auto", "confirmed", "edited", "dropped")
KEPT = ("confirmed", "edited")
BLOCK_OPS = ("accept", "confirm", "move", "split", "drop", "new", "cut")
ANCHORS = {"confirm": "frame", "move": "at", "split": "frame", "drop": "frame"}
RULE_NAMES = ("GAP_LIGHTS", "JUMP_PX", "PAUSE_MARGIN_SEC", "MIN_BLOCK_S", "HEADING_FILL_SEC", "RUNNING_FLOOR_M_PER_S")

# The time since a save, in the sessions list, is the largest of these units that fits, "just now" under a minute.
SINCE_UNITS = (("d", 86400), ("h", 3600), ("min", 60))
JUST_NOW = "just now"
CROSSES_MESSAGE = "a new block must lie between two cuts: no pause, gap or epoch bound inside it"
SHORT_MESSAGE = f"a new block must last {select.MIN_BLOCK_S:g} s or more"
OVERLAPS_MESSAGE = "a new block cannot overlap a block that is kept, remove that block first"
CUT_REASON = "tracking artifact"
SHORT_NOTE = f"under {select.MIN_BLOCK_S:g} s after a cut"
INSIDE_NOTE = "inside a cut"


def read_tables(root):
    """
    The three tables as lists of row dicts.
    """
    return {name: select.read_csv(Path(root) / f"{name}.csv") for name in TABLES}


def manifest_timestamp(root):
    """
    The timestamp of the converter's run that wrote the folder.
    """
    return json.loads((Path(root) / MANIFEST).read_text())["run"]["timestamp"]


def review_path(processed, session_id):
    """
    The session's review file under the processed root.
    """
    return Path(processed) / REVIEW / f"{session_id}.json"


def read_review(processed, session_id):
    """
    The session's review, or None when it was not reviewed.
    """
    path = review_path(processed, session_id)
    return json.loads(path.read_text()) if path.is_file() else None


def write_review(processed, review):
    """
    Write the review as the session's file, overwriting, creating the folder on the first save.
    """
    path = review_path(processed, review["session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, indent=1))
    return path


def length_s(block, rate_hz):
    """
    A block's length in seconds.
    """
    return (block["frame_end"] - block["frame_start"] + 1) / rate_hz


def time_since(stamp, now):
    """
    An ISO timestamp as the time since, "3 h ago" style, just now under a minute.
    """
    elapsed = (now - datetime.fromisoformat(stamp)).total_seconds()
    for unit, size in SINCE_UNITS:
        if elapsed >= size:
            return f"{int(elapsed // size)} {unit} ago"
    return JUST_NOW


def review_facts(review, rate_hz):
    """
    What the sessions list shows of a review: when, by whom, the blocks kept and their seconds per epoch kind, the notes.
    """
    if review is None:
        return {"reviewed": False, "reviewed_at": None, "reviewed_by": None, "n_confirmed": 0,
                "confirmed_s": {epoch: 0.0 for epoch in select.EPOCHS}, "notes": ""}
    kept = [b for b in review["blocks"] if b["status"] in KEPT]
    return {"reviewed": True, "reviewed_at": review["reviewed_at"], "reviewed_by": review["reviewed_by"],
            "n_confirmed": len(kept),
            "confirmed_s": {epoch: sum(length_s(b, rate_hz) for b in kept if b["epoch"] == epoch) for epoch in select.EPOCHS},
            "notes": review["notes"]}


def automatic_count(transformed, row, epochs):
    """
    The session's automatic block count, read from its frames the first time and from AUTOMATIC_COUNTS after.
    """
    if row["session_id"] not in AUTOMATIC_COUNTS:
        blocks, _ = select.blocks_of(transformed, [e for e in epochs if e["epoch"] in select.EPOCHS], [row])
        AUTOMATIC_COUNTS[row["session_id"]] = len(blocks)
    return AUTOMATIC_COUNTS[row["session_id"]]


def list_sessions(transformed, processed):
    """
    Every session with an arena or track epoch, unreviewed first then the oldest review first, with its epochs, count and review.
    """
    tables = read_tables(transformed)
    sessions = []
    for row in tables["sessions"]:
        epochs = [e for e in tables["epochs"] if e["session_id"] == row["session_id"]]
        if not any(e["epoch"] in select.EPOCHS for e in epochs):
            continue
        review = read_review(processed, row["session_id"])
        sessions.append({**row, "date": str(row["date"]), "epochs": epochs,
                         "n_automatic": automatic_count(transformed, row, epochs), **review_facts(review, row["rate_hz"])})
    return sorted(sessions, key=lambda s: (s["reviewed"], s["reviewed_at"] or ""))


def floats(values):
    """
    A float array as a list rounded to DECIMALS with NaN as None, so it survives JSON.
    """
    return [None if value != value else value for value in np.round(values, DECIMALS).tolist()]


def wrapped(angle):
    """
    An angle in radians wrapped to the interval from minus pi to pi.
    """
    return (angle + np.pi) % (2 * np.pi) - np.pi


def smoothed(steps):
    """
    A per-step series as a per-frame series, the first frame repeating the second, averaged over SPEED_SMOOTH_FRAMES frames.
    """
    kernel = np.ones(SPEED_SMOOTH_FRAMES) / SPEED_SMOOTH_FRAMES
    return np.convolve(np.concatenate([steps[:1], steps]), kernel, mode="same")


def speed_from_positions(t, x, y):
    """
    The step length over dt, smoothed.
    """
    return smoothed(np.hypot(np.diff(x), np.diff(y)) / np.diff(t))


def motion_direction(t, x, y):
    """
    The direction of the smoothed velocity, atan2(dy, dx) in the data's own axes.
    """
    dt = np.diff(t)
    return np.arctan2(smoothed(np.diff(y) / dt), smoothed(np.diff(x) / dt))


def led_offset(heading, motion, speed):
    """
    The circular mean (rad) and concentration r of heading minus motion over running frames, the light bar's mounting angle, 0 when none runs.
    """
    running = (speed > RUNNING_SPEED) & np.isfinite(heading) & np.isfinite(motion)
    z = np.exp(1j * (heading[running] - motion[running])).sum() / max(running.sum(), 1)
    return {"rad": float(np.angle(z)), "r": float(np.abs(z))}


def occupancy(frame, x, y, epochs):
    """
    The log counts of the positions per epoch by name, on one grid spanning the session, as heatmap bin centres and z rows per y.
    """
    keep = np.isfinite(x) & np.isfinite(y)
    xedges = np.linspace(x[keep].min(), x[keep].max(), OCCUPANCY_BINS + 1)
    yedges = np.linspace(y[keep].min(), y[keep].max(), OCCUPANCY_BINS + 1)
    grids = {}
    for e in epochs:
        inside = keep & (frame >= e["frame_start"]) & (frame <= e["frame_end"])
        counts, _, _ = np.histogram2d(x[inside], y[inside], bins=[xedges, yedges])
        grids[e["epoch"]] = {"x": ((xedges[:-1] + xedges[1:]) / 2).tolist(), "y": ((yedges[:-1] + yedges[1:]) / 2).tolist(),
                             "z": np.log1p(counts).T.tolist()}
    return grids


def stretches_of(frames, epochs, max_gap, rate_hz):
    """
    Every stretch cut_at draws in the epochs, short ones included, with its epoch: the range a block edge may move within.
    """
    return [{"epoch": e["epoch"], "frame_start": first, "frame_end": last}
            for e in epochs for first, last in select.cut_at(frames, e, max_gap, rate_hz)]


def cut_points_of(frames, epochs, max_gap, rate_hz):
    """
    The processor's cut points of the epochs merged: the pause and jump frames, the gap spans and the margins trimmed.
    """
    merged = {key: [] for key in CUT_KEYS}
    for e in epochs:
        for key, values in select.cut_points(frames, e, max_gap, rate_hz).items():
            merged[key] += values
    return merged


def load_session(transformed, session_id):
    """
    One session for the browser: facts, arrays over every frame, epochs, runs, the cut points, the heading fills, occupancy, stretches and automatic blocks.
    """
    tables = read_tables(transformed)
    session = next(s for s in tables["sessions"] if s["session_id"] == session_id)
    epochs = [e for e in tables["epochs"] if e["session_id"] == session_id]
    runs = [r for r in tables["runs"] if r["session_id"] == session_id]
    frames = select.read_frames(transformed, session_id)
    rate_hz, max_gap = session["rate_hz"], session["max_gap"]
    frame, t, x, y, raw = frames["frame"], frames["t"], frames[POSITION_COLUMNS[0]], frames[POSITION_COLUMNS[1]], frames["head_dir"]
    speed, motion = speed_from_positions(t, x, y), motion_direction(t, x, y)
    offset = led_offset(raw, motion, speed)
    heading, kind = select.fill_heading(raw, t, still(frames, epochs), rate_hz)
    unfilled = frames["unfilled_front"].astype(int), frames["unfilled_back"].astype(int)
    selected = [e for e in epochs if e["epoch"] in select.EPOCHS]
    blocks, _ = select.blocks_of(transformed, selected, [session])
    AUTOMATIC_COUNTS[session_id] = len(blocks)
    return {
        "session_id": session_id, "subject_id": session["subject_id"], "date": str(session["date"]),
        "protocol": session["protocol"], "group": session["group"], "rate_hz": rate_hz, "max_gap": max_gap,
        "n_frames": len(t),
        "t": floats(t), "x": floats(x), "y": floats(y), "heading": floats(wrapped(heading - offset["rad"])),
        "speed": floats(speed), "n_lights": (2 - unfilled[0] - unfilled[1]).tolist(),
        "epochs": [{key: e[key] for key in ("epoch", "environment", "condition", "frame_start", "frame_end", "duration_s")}
                   for e in epochs],
        "runs": [{key: r[key] for key in ("run", "epoch", "path_id", "clean", "frame_start", "frame_end")} for r in runs],
        "cuts": cut_points_of(frames, selected, max_gap, rate_hz),
        "heading_lost": select.spans(frame, np.isnan(heading)), "heading_filled": select.spans(frame, kind == select.INTERPOLATED),
        "heading_held": select.spans(frame, kind == select.HELD),
        "led_offset": offset, "occupancy": occupancy(frame, x, y, epochs),
        "stretches": stretches_of(frames, selected, max_gap, rate_hz), "blocks": blocks,
    }


def overlap_s(spans, frame_start, frame_end, rate_hz):
    """
    The seconds of these (first, last) spans falling inside the frame range.
    """
    return sum(max(0, min(last, frame_end) - max(first, frame_start) + 1) for first, last in spans) / rate_hz


def heading_in(session, frame_start, frame_end):
    """
    The seconds of heading still lost after the fill and of heading filled inside the frame range.
    """
    rate_hz = session["rate_hz"]
    return {"heading_lost_s": overlap_s(session["heading_lost"], frame_start, frame_end, rate_hz),
            "heading_filled_s": overlap_s(session["heading_filled"], frame_start, frame_end, rate_hz)}


def windows_in(seconds, window_s, stride_s):
    """
    How many windows of window_s seconds a stretch of this many seconds yields at this stride, 0 when shorter than one window.
    """
    return 0 if seconds < window_s else int((seconds - window_s) // stride_s) + 1


def summary(session, blocks, window_s, stride_s):
    """
    The session's numbers: blocks per status, seconds kept and of arena and track, the windows the kept blocks yield, the cut and heading counts.
    """
    kept = [b for b in blocks if b["status"] != "dropped"]
    rate = session["rate_hz"]
    return {"statuses": {status: sum(1 for b in blocks if b["status"] == status) for status in STATUSES},
            "kept_s": sum(length_s(b, rate) for b in kept),
            "epoch_s": sum(e["duration_s"] for e in session["epochs"] if e["epoch"] in select.EPOCHS),
            "windows": sum(windows_in(length_s(b, rate), window_s, stride_s) for b in kept),
            "cuts": {key: len(values) for key, values in session["cuts"].items()},
            **heading_in(session, 1, session["n_frames"])}


def holding(blocks, frame):
    """
    The block holding the lab frame, or None.
    """
    return next((b for b in blocks if b["frame_start"] <= frame <= b["frame_end"]), None)


def snapped(frame, runs, epoch, rate_hz):
    """
    The lab frame moved to the nearest start or end of a run of the epoch when one lies within SNAP_S, else itself.
    """
    edges = [r[key] for r in runs if r["epoch"] == epoch for key in ("frame_start", "frame_end")]
    near = [edge for edge in edges if abs(edge - frame) <= SNAP_S * rate_hz]
    return min(near, key=lambda edge: abs(edge - frame)) if near else frame


def accept(blocks, edit, session):
    """
    The automatic blocks confirmed as drawn, the edited and dropped ones kept.
    """
    return [{**b, "status": "confirmed"} if b["status"] == "auto" else b for b in blocks]


def confirm(blocks, edit, session):
    """
    The block holding the edit's frame confirmed as it stands when it is auto, or back to auto when it was confirmed, so the glyph toggles.
    """
    block = holding(blocks, edit["frame"])
    toggled = {"auto": "confirmed", "confirmed": "auto"}
    return [{**b, "status": toggled.get(b["status"], b["status"])} if b is block else b for b in blocks]


def move(blocks, edit, session):
    """
    The block holding the edit's at frame with its start or end moved to the edit's frame, snapped, inside its stretch and clear of neighbours.
    """
    block = holding(blocks, edit["at"])
    target = snapped(edit["frame"], session["runs"], block["epoch"], session["rate_hz"])
    stretch = holding(session["stretches"], block["frame_start"])
    others = [b for b in blocks if b is not block and b["epoch"] == block["epoch"]]
    if edit["edge"] == "start":
        floor = max([b["frame_end"] + 1 for b in others if b["frame_end"] < block["frame_start"]] + [stretch["frame_start"]])
        moved = {**block, "frame_start": min(max(target, floor), block["frame_end"])}
    else:
        ceiling = min([b["frame_start"] - 1 for b in others if b["frame_start"] > block["frame_end"]] + [stretch["frame_end"]])
        moved = {**block, "frame_end": max(min(target, ceiling), block["frame_start"])}
    return [{**moved, "status": "edited"} if b is block else b for b in blocks]


def split(blocks, edit, session):
    """
    The block holding the edit's frame split in two there, the frame starting the second piece.
    """
    block = holding(blocks, edit["frame"])
    if edit["frame"] == block["frame_start"]:
        return blocks
    pieces = [{**block, "frame_end": edit["frame"] - 1, "status": "edited"},
              {**block, "frame_start": edit["frame"], "status": "edited"}]
    return [piece for b in blocks for piece in (pieces if b is block else [b])]


def drop(blocks, edit, session):
    """
    The block holding the edit's frame dropped, or taken back as edited when it was dropped already.
    """
    block = holding(blocks, edit["frame"])
    status = "edited" if block["status"] == "dropped" else "dropped"
    return [{**b, "status": status} if b is block else b for b in blocks]


def refusal(blocks, edit, session):
    """
    Why a new block over the edit's range is refused, or None when it lies in one stretch, lasts long enough and is clear of kept blocks.
    """
    first, last = edit["frame_start"], edit["frame_end"]
    stretch = holding(session["stretches"], first)
    if stretch is None or last > stretch["frame_end"]:
        return CROSSES_MESSAGE
    if not select.long_enough((first, last), session["rate_hz"]):
        return SHORT_MESSAGE
    if any(b["status"] != "dropped" and b["frame_start"] <= last and first <= b["frame_end"] for b in blocks):
        return OVERLAPS_MESSAGE
    return None


def new(blocks, edit, session):
    """
    A block over the edit's range added as edited, in the epoch of the stretch holding it.
    """
    epoch = holding(session["stretches"], edit["frame_start"])["epoch"]
    environment = next(e["environment"] for e in session["epochs"] if e["epoch"] == epoch)
    block = {"session_id": session["session_id"], "epoch": epoch, "environment": environment,
             "frame_start": edit["frame_start"], "frame_end": edit["frame_end"], "status": "edited", "note": ""}
    return blocks + [block]


def cut(blocks, edit, session):
    """
    The edit's range removed from every block it touches, a block inside it dropped, a piece left under MIN_BLOCK_S dropped with its note.
    """
    first, last = edit["frame_start"], edit["frame_end"]
    result = []
    for b in blocks:
        if last < b["frame_start"] or first > b["frame_end"]:
            result.append(b)
            continue
        if first <= b["frame_start"] and last >= b["frame_end"]:
            result.append({**b, "status": "dropped", "note": INSIDE_NOTE})
            continue
        pieces = []
        if first > b["frame_start"]:
            pieces.append({**b, "frame_end": first - 1, "status": "edited"})
        if last < b["frame_end"]:
            pieces.append({**b, "frame_start": last + 1, "status": "edited"})
        for piece in pieces:
            if not select.long_enough((piece["frame_start"], piece["frame_end"]), session["rate_hz"]):
                piece.update(status="dropped", note=SHORT_NOTE)
        result.extend(pieces)
    return result


def renumbered(blocks):
    """
    The blocks in frame order, named as the processor names them, session, epoch and a two digit index per epoch.
    """
    counts = {}
    result = []
    for b in sorted(blocks, key=lambda b: b["frame_start"]):
        counts[b["epoch"]] = counts.get(b["epoch"], 0) + 1
        result.append({**b, "block_id": f"{b['session_id']}_{b['epoch']}_{counts[b['epoch']]:02d}"})
    return result


EDITS = {"accept": accept, "confirm": confirm, "move": move, "split": split, "drop": drop, "new": new, "cut": cut}


def applies(blocks, edit, session):
    """
    Whether the edit still has a block at its anchor, or the room for its new block, against these blocks.
    """
    if edit["op"] in ANCHORS:
        return holding(blocks, edit[ANCHORS[edit["op"]]]) is not None
    if edit["op"] == "new":
        return refusal(blocks, edit, session) is None
    return True


def replayed(blocks, edits, session):
    """
    The automatic blocks, status auto, with the block edits applied in order against the session's runs, rate and stretches, and the edits skipped as no longer applying.
    """
    blocks = [{**b, "status": "auto", "note": ""} for b in blocks]
    skipped = []
    for edit in edits:
        if edit["op"] not in BLOCK_OPS:
            continue
        if applies(blocks, edit, session):
            blocks = EDITS[edit["op"]](blocks, edit, session)
        else:
            skipped.append(edit)
    return blocks, skipped


def apply_edits(blocks, edits, session):
    """
    The blocks after the edits that still apply, renumbered.
    """
    return renumbered(replayed(blocks, edits, session)[0])


def rules():
    """
    The processor's rule constants by name, as the review file records them.
    """
    return {name: getattr(select, name) for name in RULE_NAMES}


def cuts_of(edits):
    """
    The ranges the cut edits removed, each with its reason.
    """
    return [{"frame_start": e["frame_start"], "frame_end": e["frame_end"], "reason": CUT_REASON}
            for e in edits if e["op"] == "cut"]


def flagged_runs(edits):
    """
    The runs flagged an odd number of times, so flagging again takes the flag back.
    """
    flagged = set()
    for e in edits:
        if e["op"] == "flag":
            flagged ^= {e["run"]}
    return sorted(flagged)


def review_of(session, edits, notes, stamp):
    """
    The review file's content: the blocks, cuts, flagged runs, notes and edits, who reviewed and when, the converter manifest's timestamp, the rules.
    """
    blocks = apply_edits(session["blocks"], edits, session)
    return {"session_id": session["session_id"], "reviewed_by": getpass.getuser(),
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "converter_manifest_timestamp": stamp, "rules": rules(),
            "blocks": [{key: b[key] for key in BLOCK_KEYS} for b in blocks],
            "cuts": cuts_of(edits), "flagged_runs": flagged_runs(edits), "notes": notes, "edits": edits}
