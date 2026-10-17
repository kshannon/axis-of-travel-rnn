"""
Where the processor cuts a session into blocks, from its frames: the project's cut logic named for the tool.
"""

from process_lab_data import select

# The epoch kinds the processor cuts into blocks, and what cut them, as its cut_points names it, merged over the epochs
# of the session.
EPOCH_KINDS = select.EPOCHS
CUT_KEYS = ("pauses", "jumps", "gaps", "margins")


def selected(epochs):
    """
    The epochs the processor cuts into blocks, the arena and track ones under its condition, so a block is never offered that it will not build.
    """
    return [e for e in epochs if e["epoch"] in EPOCH_KINDS and e["condition"] == select.CONDITION]


def in_dataset(tables):
    """
    The ids of the sessions that survive the processor's funnel with an epoch.
    """
    return {e["session_id"] for e in select.funnel(tables, None)[0]}


def automatic_blocks(frames, session, epochs):
    """
    The blocks the processor builds from the session without a review.
    """
    blocks, _ = select.blocks_in(frames, session, selected(epochs))
    return blocks


def stretches(frames, epochs, max_gap, rate_hz):
    """
    Every stretch cut_at draws in the epochs, short ones included, with its epoch: the range a block edge may move within.
    """
    return [{"epoch": e["epoch"], "frame_start": first, "frame_end": last}
            for e in selected(epochs) for first, last in select.cut_at(frames, e, max_gap, rate_hz)]


def cut_points(frames, epochs, max_gap, rate_hz):
    """
    The pause and jump frames, the gap spans and the margins trimmed in the epochs, merged.
    """
    merged = {key: [] for key in CUT_KEYS}
    for e in selected(epochs):
        for key, values in select.cut_points(frames, e, max_gap, rate_hz).items():
            merged[key] += values
    return merged
