"""
The review edits: the legality rules of the block edits and the blocks, cuts and flagged runs they make, while assembling the review file (stamps, reviewed_by, notes) is ReviewManager's workflow and not the engine's.
"""

from .cuts import INITIAL_NOTE, INITIAL_STATUS

# The block keys the engine returns, the statuses (a block starts AUTO, a confirm toggles it with CONFIRMED), the edit that
# changes no block, and the field of an edit that reaches a block by its frame. A block with nothing to say carries INITIAL_NOTE.
BLOCK_KEYS = ("block_id", "epoch", "environment", "frame_start", "frame_end", "status", "note")
AUTO, CONFIRMED, EDITED, REMOVED = INITIAL_STATUS, "confirmed", "edited", "dropped"
TOGGLED = {AUTO: CONFIRMED, CONFIRMED: AUTO}
FLAG = "flag"
ANCHORS = {"confirm": "frame", "move": "at", "split": "frame", "drop": "frame"}

# Why an edit is refused, and what a cut writes on the blocks it removes. The seconds are the min_block_s rule.
UNKNOWN_MESSAGE = "{} is not an edit op"
NO_BLOCK = "no block holds frame {}"
UNCUT_MESSAGE = "frame {} is in no epoch the rules cut, the rules cut blocks only from {} under {}"
CROSSES_MESSAGE = "a new block must lie between two cuts: no pause, gap or epoch bound inside it"
SHORT_MESSAGE = "a new block must last {:g} s or more"
OVERLAPS_MESSAGE = "a new block cannot overlap a block that is kept, remove that block first"
RESTORES_MESSAGE = "a removed block cannot come back over a block that is kept, remove that block first"
TOO_SHORT_MESSAGE = "a kept block must last {:g} s or more, reject it or cut the range out with marks instead"
CUT_REASON = "tracking artifact"
SHORT_NOTE = "under {:g} s after a cut"
INSIDE_NOTE = "inside a cut"


def reaching(blocks, frame):
    """
    The block an edit anchored at the lab frame reaches: the first one holding it that is kept, else the first removed one, or None.
    """
    # List order is the old tool's rank order (a split or cut piece replaces its parent in place, a new block goes last),
    # so no sort is needed here and none may be added later.
    held = [b for b in blocks if b["frame_start"] <= frame <= b["frame_end"]]
    return min(held, key=lambda b: b["status"] == REMOVED, default=None)


def stretch_of(session, frame):
    """
    The stretch holding the lab frame, or None.
    """
    return next((s for s in session["stretches"] if s["frame_start"] <= frame <= s["frame_end"]), None)


def uncut_reason(session, frame):
    """
    Why no block can lie at the lab frame, it being in none of the epochs the rules cut, or None when it is in one.
    """
    if any(e["frame_start"] <= frame <= e["frame_end"] for e in session["epochs"]):
        return None
    rules = session["rules"]
    return UNCUT_MESSAGE.format(frame, " and ".join(rules["epochs"]), rules["condition"])


def snapped(frame, epoch, session):
    """
    The lab frame moved to the nearest start or end of a run of the epoch when one lies within snap_s, else itself.
    """
    reach = session["rules"]["snap_s"] * session["rate_hz"]
    edges = [r[key] for r in session["runs"] if r["epoch"] == epoch for key in ("frame_start", "frame_end")]
    near = [edge for edge in edges if abs(edge - frame) <= reach]
    return min(near, key=lambda edge: abs(edge - frame)) if near else frame


def long_enough(first, last, session):
    """
    Whether the frame range lasts at least min_block_s.
    """
    return last - first + 1 >= session["rules"]["min_block_s"] * session["rate_hz"]


def accept(blocks, edit, session):
    """
    The automatic blocks confirmed as drawn, the edited and dropped ones kept.
    """
    return [{**b, "status": CONFIRMED} if b["status"] == AUTO else b for b in blocks]


def confirm(blocks, edit, session):
    """
    The block holding the edit's frame confirmed as it stands when it is auto, or back to auto when it was confirmed, so the glyph toggles.
    """
    block = reaching(blocks, edit["frame"])
    return [{**b, "status": TOGGLED.get(b["status"], b["status"])} if b is block else b for b in blocks]


def move(blocks, edit, session):
    """
    The block holding the edit's at frame with its start or end moved to the edit's frame, snapped, inside its stretch and clear of neighbours.
    """
    block = reaching(blocks, edit["at"])
    target = snapped(edit["frame"], block["epoch"], session)
    stretch = stretch_of(session, block["frame_start"])
    others = [b for b in blocks if b is not block and b["epoch"] == block["epoch"]]
    if edit["edge"] == "start":
        floor = max([b["frame_end"] + 1 for b in others if b["frame_end"] < block["frame_start"]] + [stretch["frame_start"]])
        moved = {**block, "frame_start": min(max(target, floor), block["frame_end"])}
    else:
        ceiling = min([b["frame_start"] - 1 for b in others if b["frame_start"] > block["frame_end"]] + [stretch["frame_end"]])
        moved = {**block, "frame_end": max(min(target, ceiling), block["frame_start"])}
    return [{**moved, "status": EDITED} if b is block else b for b in blocks]


def split(blocks, edit, session):
    """
    The block holding the edit's frame split in two there, the frame starting the second piece.
    """
    block = reaching(blocks, edit["frame"])
    if edit["frame"] == block["frame_start"]:
        return blocks
    pieces = [{**block, "frame_end": edit["frame"] - 1, "status": EDITED}, {**block, "frame_start": edit["frame"], "status": EDITED}]
    return [piece for b in blocks for piece in (pieces if b is block else [b])]


def drop(blocks, edit, session):
    """
    The block holding the edit's frame dropped, or taken back as edited when it was dropped already.
    """
    block = reaching(blocks, edit["frame"])
    status = EDITED if block["status"] == REMOVED else REMOVED
    return [{**b, "status": status} if b is block else b for b in blocks]


def new(blocks, edit, session):
    """
    A block over the edit's range added as edited, in the epoch of the stretch holding it.
    """
    epoch = stretch_of(session, edit["frame_start"])["epoch"]
    environment = next(e["environment"] for e in session["epochs"] if e["epoch"] == epoch)
    return blocks + [{"epoch": epoch, "environment": environment, "frame_start": edit["frame_start"], "frame_end": edit["frame_end"],
                      "status": EDITED, "note": INITIAL_NOTE}]


def cut(blocks, edit, session):
    """
    The edit's range removed from every block it touches, a block inside it dropped, a piece left under min_block_s dropped with its note.
    """
    first, last = edit["frame_start"], edit["frame_end"]
    result = []
    for b in blocks:
        if last < b["frame_start"] or first > b["frame_end"]:
            result.append(b)
        elif first <= b["frame_start"] and last >= b["frame_end"]:
            result.append({**b, "status": REMOVED, "note": INSIDE_NOTE})
        else:
            pieces = []
            if first > b["frame_start"]:
                pieces.append({**b, "frame_end": first - 1, "status": EDITED})
            if last < b["frame_end"]:
                pieces.append({**b, "frame_start": last + 1, "status": EDITED})
            for piece in pieces:
                if not long_enough(piece["frame_start"], piece["frame_end"], session):
                    piece.update(status=REMOVED, note=SHORT_NOTE.format(session["rules"]["min_block_s"]))
            result.extend(pieces)
    return result


EDITS = {"accept": accept, "confirm": confirm, "move": move, "split": split, "drop": drop, "new": new, "cut": cut}


def crowded(blocks):
    """
    Whether two of the blocks that are not removed share a frame.
    """
    standing = sorted((b for b in blocks if b["status"] != REMOVED), key=lambda b: b["frame_start"])
    return any(before["frame_end"] >= after["frame_start"] for before, after in zip(standing, standing[1:]))


def new_refusal(blocks, edit, session):
    """
    Why a new block over the edit's range is refused, or None when it starts in an epoch the rules cut, lies in one stretch, lasts long enough and is clear of the blocks kept.
    """
    first, last = edit["frame_start"], edit["frame_end"]
    # Its first frame in an epoch the rules do not cut is the reason, before the cuts: no stretch is there to lie between.
    uncut = uncut_reason(session, first)
    if uncut:
        return uncut
    stretch = stretch_of(session, first)
    if stretch is None or last > stretch["frame_end"]:
        return CROSSES_MESSAGE
    if not long_enough(first, last, session):
        return SHORT_MESSAGE.format(session["rules"]["min_block_s"])
    if any(b["status"] != REMOVED and b["frame_start"] <= last and first <= b["frame_end"] for b in blocks):
        return OVERLAPS_MESSAGE
    return None


def refusal(blocks, edit, session):
    """
    Why the edit is illegal on these blocks, or None: its op is unknown, no block holds the frame it anchors to, a new block does not fit (it starts outside the epochs the rules cut, crosses a cut, is short or overlaps a kept block), it would bring a removed block back over a kept one, or it would leave a kept block under min_block_s.
    """
    op = edit["op"]
    if op not in EDITS:
        return UNKNOWN_MESSAGE.format(op)
    if op == "new":
        return new_refusal(blocks, edit, session)
    if op in ANCHORS and reaching(blocks, edit[ANCHORS[op]]) is None:
        return NO_BLOCK.format(edit[ANCHORS[op]])
    result = EDITS[op](blocks, edit, session)
    if crowded(result):
        return RESTORES_MESSAGE
    kept_short = any(b["status"] != REMOVED and not long_enough(b["frame_start"], b["frame_end"], session) for b in result)
    return TOO_SHORT_MESSAGE.format(session["rules"]["min_block_s"]) if kept_short else None


def renumbered(blocks, session):
    """
    The blocks in frame order, named as the processor names them, session, epoch and a two digit index per epoch, with the review file's block keys.
    """
    counts, result = {}, []
    for b in sorted(blocks, key=lambda b: b["frame_start"]):
        counts[b["epoch"]] = counts.get(b["epoch"], 0) + 1
        named = {**b, "block_id": f"{session['session_id']}_{b['epoch']}_{counts[b['epoch']]:02d}"}
        result.append({key: named[key] for key in BLOCK_KEYS})
    return result


def cuts_of(edits):
    """
    The ranges the cut edits removed, each with its reason.
    """
    return [{"frame_start": e["frame_start"], "frame_end": e["frame_end"], "reason": CUT_REASON} for e in edits if e["op"] == "cut"]


def flagged_runs(edits):
    """
    The runs flagged an odd number of times, so flagging again takes the flag back.
    """
    flagged = set()
    for e in edits:
        if e["op"] == FLAG:
            flagged ^= {e["run"]}
    return sorted(flagged)


def apply_edits(blocks, edits, session):
    """
    The blocks the whole edit list makes from the initial blocks, renumbered, with the refusals (index, op, reason), the ranges cut and the runs flagged.
    """
    # Always start from the initial blocks with the whole list: drop and confirm toggle, so applying a saved review's
    # edits to its saved blocks would undo them.
    refusals = []
    for i, edit in enumerate(edits):
        if edit["op"] == FLAG:
            continue
        reason = refusal(blocks, edit, session)
        if reason:
            refusals.append({"index": i, "op": edit["op"], "reason": reason})
        else:
            blocks = EDITS[edit["op"]](blocks, edit, session)
    return {"blocks": renumbered(blocks, session), "refusals": refusals, "cuts": cuts_of(edits), "flagged_runs": flagged_runs(edits)}
