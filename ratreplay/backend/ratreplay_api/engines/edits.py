"""
The review edits: applying them to a session's automatic blocks, and the review file's content.
"""

# These rules are copied from src/ratreplay/data.py, which keeps its own copy until the old tool is deleted.

import itertools

from process_lab_data import select
from process_lab_data.__main__ import KEPT_STATUSES

from . import cuts

# The review file's block keys and statuses, and the edits that change the block list, applied in order. ANCHORS names the
# field of an edit that reaches a block by its frame. A moved edge snaps to a run start or end within SNAP_S seconds. The
# file records the processor's rules named in RULE_NAMES.
BLOCK_KEYS = ("block_id", "epoch", "environment", "frame_start", "frame_end", "status", "note")
STATUSES = ("auto", "confirmed", "edited", "dropped")
REMOVED = "dropped"
BLOCK_OPS = ("accept", "confirm", "move", "split", "drop", "new", "cut")
ANCHORS = {"confirm": "frame", "move": "at", "split": "frame", "drop": "frame"}
RULE_NAMES = ("GAP_LIGHTS", "JUMP_PX", "PAUSE_MARGIN_SEC", "MIN_BLOCK_S", "HEADING_FILL_SEC", "RUNNING_FLOOR_M_PER_S")
SNAP_S = 1.0

# Why an edit is refused, and what a cut writes on the blocks it removes.
NO_BLOCK = "no block holds frame {}"
CROSSES_MESSAGE = "a new block must lie between two cuts: no pause, gap or epoch bound inside it"
SHORT_MESSAGE = f"a new block must last {select.MIN_BLOCK_S:g} s or more"
OVERLAPS_MESSAGE = "a new block cannot overlap a block that is kept, remove that block first"
RESTORES_MESSAGE = "a removed block cannot come back over a block that is kept, remove that block first"
TOO_SHORT_MESSAGE = f"a kept block must last {select.MIN_BLOCK_S:g} s or more, remove it instead"
CUT_REASON = "tracking artifact"
SHORT_NOTE = f"under {select.MIN_BLOCK_S:g} s after a cut"
INSIDE_NOTE = "inside a cut"


def context(frames, session, epochs, runs):
    """
    What the edits read of a session: its automatic blocks, the stretches a block may move within, its runs, epochs and rate.
    """
    return {"session_id": session["session_id"], "rate_hz": session["rate_hz"], "epochs": epochs, "runs": runs,
            "blocks": cuts.automatic_blocks(frames, session, epochs),
            "stretches": cuts.stretches(frames, epochs, session["max_gap"], session["rate_hz"])}


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
    status = "edited" if block["status"] == REMOVED else REMOVED
    return [{**b, "status": status} if b is block else b for b in blocks]


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
            result.append({**b, "status": REMOVED, "note": INSIDE_NOTE})
            continue
        pieces = []
        if first > b["frame_start"]:
            pieces.append({**b, "frame_end": first - 1, "status": "edited"})
        if last < b["frame_end"]:
            pieces.append({**b, "frame_start": last + 1, "status": "edited"})
        for piece in pieces:
            if not select.long_enough((piece["frame_start"], piece["frame_end"]), session["rate_hz"]):
                piece.update(status=REMOVED, note=SHORT_NOTE)
        result.extend(pieces)
    return result


EDITS = {"accept": accept, "confirm": confirm, "move": move, "split": split, "drop": drop, "new": new, "cut": cut}


def too_short(blocks, rate_hz):
    """
    Whether a block that is not removed lasts under MIN_BLOCK_S, which a split or a move can leave behind.
    """
    return any(b["status"] != REMOVED and b["frame_end"] - b["frame_start"] + 1 < select.MIN_BLOCK_S * rate_hz for b in blocks)


def crowded(blocks):
    """
    Whether two of the blocks that are not removed share a frame.
    """
    standing = sorted((b for b in blocks if b["status"] != REMOVED), key=lambda b: b["frame_start"])
    return any(before["frame_end"] >= after["frame_start"] for before, after in zip(standing, standing[1:]))


def new_refusal(blocks, edit, session):
    """
    Why a new block over the edit's range is refused, or None when it lies in one stretch, lasts long enough and is clear of the blocks kept.
    """
    first, last = edit["frame_start"], edit["frame_end"]
    stretch = holding(session["stretches"], first)
    if stretch is None or last > stretch["frame_end"]:
        return CROSSES_MESSAGE
    if not select.long_enough((first, last), session["rate_hz"]):
        return SHORT_MESSAGE
    if any(b["status"] != REMOVED and b["frame_start"] <= last and first <= b["frame_end"] for b in blocks):
        return OVERLAPS_MESSAGE
    return None


def refusal(blocks, edit, session):
    """
    Why the edit cannot be applied to these blocks, or None: no block holds the frame it anchors to, a new block does not fit, the edit would bring a removed block back over a block that is kept, or it would leave a kept block under MIN_BLOCK_S.
    """
    if edit["op"] == "new":
        return new_refusal(blocks, edit, session)
    anchor = ANCHORS.get(edit["op"])
    if anchor and holding(blocks, edit[anchor]) is None:
        return NO_BLOCK.format(edit[anchor])
    result = EDITS[edit["op"]](blocks, edit, session)
    if crowded(result):
        return RESTORES_MESSAGE
    return TOO_SHORT_MESSAGE if too_short(result, session["rate_hz"]) else None


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


def apply_edits(blocks, edits, session):
    """
    The automatic blocks with the block edits applied in order, renumbered, and the edits refused each with its reason. An edit reaches the first block holding its frame, the removed ones last. The blocks stay in the order they were made, a new one last, so two that start on one frame are numbered as the old tool numbers them.
    """
    blocks = [{**b, "status": "auto", "note": "", "rank": i} for i, b in enumerate(blocks)]
    ranks = itertools.count(len(blocks))
    skipped = []
    for edit in edits:
        if edit["op"] not in BLOCK_OPS:
            continue
        reached = sorted(blocks, key=lambda b: b["status"] == REMOVED)
        reason = refusal(reached, edit, session)
        if reason:
            skipped.append({**edit, "reason": reason})
        else:
            made = EDITS[edit["op"]](reached, edit, session)
            blocks = sorted((b if "rank" in b else {**b, "rank": next(ranks)} for b in made), key=lambda b: b["rank"])
    return renumbered(blocks), skipped


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


def preview(session, edits):
    """
    What the edits make: the blocks cut to the review file's block keys, the cuts and flagged runs they leave, and the edits skipped as no longer applying, each with its reason.
    """
    blocks, skipped = apply_edits(session["blocks"], edits, session)
    return {"blocks": [{key: b[key] for key in BLOCK_KEYS} for b in blocks], "cuts": cuts_of(edits),
            "flagged_runs": flagged_runs(edits), "skipped": skipped}


def review_of(session, edits, notes, stamp, reviewed_by, reviewed_at):
    """
    The review file's content: the blocks, cuts, flagged runs, notes and edits, who reviewed and when, the converter manifest's timestamp, the rules.
    """
    made = preview(session, edits)
    return {"session_id": session["session_id"], "reviewed_by": reviewed_by, "reviewed_at": reviewed_at,
            "converter_manifest_timestamp": stamp, "rules": rules(), "blocks": made["blocks"], "cuts": made["cuts"],
            "flagged_runs": made["flagged_runs"], "notes": notes, "edits": edits}
