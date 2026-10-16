"""
The review edits: applying them to a session's automatic blocks and the review file's content.
"""

import getpass
from datetime import datetime, timezone

from process_lab_data.__main__ import KEPT_STATUSES

# These are the old tool's functions and move here, with their tests, when src/ratreplay is removed.
from ratreplay.data import ANCHORS, BLOCK_KEYS, BLOCK_OPS, EDITS, STATUSES, applies, cuts_of, flagged_runs, refusal, renumbered, rules

from . import cuts

__all__ = ["BLOCK_KEYS", "KEPT_STATUSES", "STATUSES", "context", "preview", "review_of"]

REMOVED = "dropped"

NO_BLOCK = "no block holds frame {}"


def context(frames, session, epochs, runs):
    """
    What the edits read of a session: its automatic blocks, the stretches a block may move within, its runs, epochs and rate.
    """
    return {"session_id": session["session_id"], "rate_hz": session["rate_hz"], "epochs": epochs, "runs": runs,
            "blocks": cuts.automatic_blocks(frames, session, epochs),
            "stretches": cuts.stretches(frames, epochs, session["max_gap"], session["rate_hz"])}


def replayed(blocks, edits, session):
    """
    The old tool's replay, except that the removed blocks are listed after the others once each edit is made. An edit anchors to the first block holding its frame, so one anchored where a new block lies over a removed one reaches the new block.
    """
    blocks = [{**b, "status": "auto", "note": ""} for b in blocks]
    skipped = []
    for edit in edits:
        if edit["op"] not in BLOCK_OPS:
            continue
        if applies(blocks, edit, session):
            blocks = sorted(EDITS[edit["op"]](blocks, edit, session), key=lambda b: b["status"] == REMOVED)
        else:
            skipped.append(edit)
    return blocks, skipped


def reasons(session, edits, skipped):
    """
    The skipped edits, each with why it no longer applies to the blocks the edits before it made: the processor's refusal of a new block, else that no block holds the frame it anchors to.
    """
    result = []
    for edit in skipped:
        before, _ = replayed(session["blocks"], edits[:next(i for i, e in enumerate(edits) if e is edit)], session)
        reason = refusal(before, edit, session) if edit["op"] == "new" else NO_BLOCK.format(edit[ANCHORS[edit["op"]]])
        result.append({**edit, "reason": reason})
    return result


def preview(session, edits):
    """
    What the edits make: the blocks renumbered and cut to the review file's block keys, the cuts and flagged runs they leave, and the edits skipped as no longer applying, each with its reason.
    """
    blocks, skipped = replayed(session["blocks"], edits, session)
    return {"blocks": [{key: b[key] for key in BLOCK_KEYS} for b in renumbered(blocks)], "cuts": cuts_of(edits),
            "flagged_runs": flagged_runs(edits), "skipped": reasons(session, edits, skipped)}


def review_of(session, edits, notes, stamp):
    """
    The review file's content as the old tool writes it: the blocks, cuts, flagged runs, notes and edits, who reviewed and when, the converter manifest's timestamp, the rules.
    """
    return {"session_id": session["session_id"], "reviewed_by": getpass.getuser(),
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "converter_manifest_timestamp": stamp, "rules": rules(),
            "blocks": preview(session, edits)["blocks"],
            "cuts": cuts_of(edits), "flagged_runs": flagged_runs(edits), "notes": notes, "edits": edits}
