"""
The processed dataset's blocks: the index with verdicts at the window settings, and one block in metres with its environment, runs, trips and windows.
"""

from pathlib import Path

from ..engines import environment, spans, windows
from ..errors import NotFound
from ..stores import processed

# The per frame columns of a block the browser gets, the lab frame number first.
ARRAY_COLUMNS = ("frame", "t", "x", "y", "heading", "speed", "n_lights")


def find(source, block_id):
    """
    The csv row of the block with this id.
    """
    processed.require_built(Path(source["processed_path"]))
    for row in processed.list_blocks(Path(source["processed_path"])):
        if row["block_id"] == block_id:
            return row
    raise NotFound(f"no block {block_id}")


def index(source, settings):
    """
    Every block's csv row with its measured heading share, the windows it yields and its verdict at the settings, and the totals per kind.
    """
    rows, shares = processed.blocks_with_shares(Path(source["processed_path"]))
    blocks = []
    for row in rows:
        ok, reason = windows.verdict(row, shares[row["block_id"]], settings)
        blocks.append({**{key: value for key, value in row.items() if key != "path"},
                       "heading_measured": windows.heading_shares(shares[row["block_id"]])["measured"],
                       "n_windows": windows.window_count(row["n_frames"], windows.rate_of(row), settings), "ok": ok, "reason": reason})
    return {"blocks": blocks, "totals": windows.summarize(rows, shares, settings), "settings": settings}


def header(source, block_id, settings):
    """
    One block's facts: its environment geometry, the spans of its runs, trips and phases, its heading fills and one light stretches, its verdict and its windows at the settings.
    """
    row = find(source, block_id)
    block = processed.load_block(row["path"])
    ok, reason = windows.verdict(row, block, settings)
    return {"block_id": block_id, "session_id": row["session_id"], "kind": row["kind"], "status": row["status"],
            "environment": row["environment"], "geometry": environment.geometry(row["environment"]),
            "n_frames": row["n_frames"], "duration_s": row["duration_s"], "rate_hz": windows.rate_of(row), "frame_start": int(block["frame"][0]),
            "runs": spans.run_spans(block), "trips": spans.trip_spans(block), "phases": spans.phase_spans(block),
            "heading_filled": spans.true_spans(block["heading_filled"]), "heading_held": spans.true_spans(block["heading_held"]),
            "one_light": spans.true_spans(block["n_lights"] == 1), "verdict": {"ok": ok, "reason": reason}, "settings": settings,
            "windows": windows.window_rows(block, row, settings)}


def arrays(source, block_id):
    """
    One block's arrays over its frames, in metres and radians.
    """
    block = processed.load_block(find(source, block_id)["path"])
    return {name: block[name] for name in ARRAY_COLUMNS}
