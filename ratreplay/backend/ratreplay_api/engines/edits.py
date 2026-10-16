"""
The review edits: applying them to a session's automatic blocks and the review file's content.
"""

from process_lab_data.__main__ import KEPT_STATUSES

# These are the old tool's functions and move here, with their tests, when src/ratreplay is removed.
from ratreplay.data import BLOCK_KEYS, STATUSES, cuts_of, flagged_runs, renumbered, replayed, review_of

from . import cuts

__all__ = ["BLOCK_KEYS", "KEPT_STATUSES", "STATUSES", "context", "preview", "review_of"]


def context(frames, session, epochs, runs):
    """
    What the edits read of a session: its automatic blocks, the stretches a block may move within, its runs, epochs and rate.
    """
    return {"session_id": session["session_id"], "rate_hz": session["rate_hz"], "epochs": epochs, "runs": runs,
            "blocks": cuts.automatic_blocks(frames, session, epochs),
            "stretches": cuts.stretches(frames, epochs, session["max_gap"], session["rate_hz"])}


def preview(session, edits):
    """
    What the edits make: the blocks renumbered and cut to the review file's block keys, the cuts and flagged runs they leave, and the edits skipped as no longer applying.
    """
    blocks, skipped = replayed(session["blocks"], edits, session)
    return {"blocks": [{key: b[key] for key in BLOCK_KEYS} for b in renumbered(blocks)], "cuts": cuts_of(edits),
            "flagged_runs": flagged_runs(edits), "skipped": skipped}
