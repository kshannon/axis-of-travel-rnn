"""
The Blocks tab's data: the processed dataset's blocks through the core package's loader, each read once, their verdicts and totals at the window settings, the settings file, one block for the browser and the environment drawn under it.
"""

from pathlib import Path

import numpy as np

from axis_of_travel_rnn import trajectory, windows
from environments import load_environment

from .data import floats

# The columns the window logic reads for its heading and trip shares, kept in memory per block id with the parquet's
# modification time, so every block is read once and read again only when the processor rewrote it.
SHARE_COLUMNS = ("heading", "heading_filled", "heading_held", "trip")
CACHE = {}

# The environment config drawn under a block in the room frame: the walls and the centerline of a track as thin lines,
# the reward sites as circles named on hover, the boundary of an arena as a closed line. Generic over the EnvSpec, so a
# config with none of one part draws nothing for it.
WALL_LINE = {"color": "#6b7280", "width": 1.5}
CENTERLINE = {"color": "#9ca3af", "width": 1, "dash": "dot"}
BOUNDARY_LINE = {"color": "#6b7280", "width": 1.5}
SITE_MARKER = {"size": 12, "color": "white", "line": {"color": "#111827", "width": 1.5}}


def built(processed):
    """
    Whether the processor has written its manifest under the processed root.
    """
    return (Path(processed) / trajectory.MANIFEST).is_file()


def shares_of(path):
    """
    The share columns of the block parquet, read once and kept in CACHE until the file's modification time changes.
    """
    stamp = path.stat().st_mtime_ns
    if path.stem not in CACHE or CACHE[path.stem][0] != stamp:
        block = trajectory.load_block(path)
        CACHE[path.stem] = (stamp, {name: block[name] for name in SHARE_COLUMNS})
    return CACHE[path.stem][1]


def load_all(processed):
    """
    The blocks csv rows of every kind and the share columns of every block by block id.
    """
    rows = trajectory.list_blocks(processed)
    return rows, {row["block_id"]: shares_of(row["path"]) for row in rows}


def summary(processed, settings):
    """
    The totals per kind and overall over every built block at the settings.
    """
    rows, shares = load_all(processed)
    return windows.summarize(rows, shares, settings)


def save(processed, settings):
    """
    Write the settings file at windows.CONFIG with the processed manifest's facts and the totals at the settings, and return its path.
    """
    windows.write_settings(settings, trajectory.read_manifest(processed), summary(processed, settings), windows.CONFIG)
    return windows.CONFIG


def rate_of(row):
    """
    The block's whole frame rate in Hz from its csv row, rounded because duration_s is n_frames over the session's integer rate and the division does not always come back exact.
    """
    return round(row["n_frames"] / row["duration_s"])


def spans(values):
    """
    The (value, first, last) index triples of every run of equal values.
    """
    values = np.asarray(values)
    edges = np.flatnonzero(values[1:] != values[:-1]) + 1
    starts, stops = np.concatenate(([0], edges)), np.concatenate((edges, [len(values)]))
    return [(values[first].item(), int(first), int(stop - 1)) for first, stop in zip(starts, stops)]


def true_spans(mask):
    """
    The [first, last] index pairs of every stretch of True.
    """
    return [[first, last] for value, first, last in spans(mask) if value]


def run_spans(block):
    """
    One span per run of the block with its path id and clean flag.
    """
    return [{"run": run, "path_id": int(block["path_id"][first]), "clean": bool(block["clean"][first]), "first": first, "last": last}
            for run, first, last in spans(block["run"]) if run != 0]


def trip_spans(block):
    """
    One span per trip of the block, numbered as the processor numbers them, partial when the number is negative.
    """
    return [{"trip": abs(trip), "partial": trip < 0, "first": first, "last": last} for trip, first, last in spans(block["trip"]) if trip != 0]


def polyline(segments, line):
    """
    One line trace of many segments, the segments parted by None, no hover.
    """
    return {"type": "scatter", "mode": "lines", "x": [v for a, b in segments for v in (a[0], b[0], None)],
            "y": [v for a, b in segments for v in (a[1], b[1], None)], "line": line, "connectgaps": False, "hoverinfo": "skip"}


def environment_traces(spec):
    """
    The environment under a block: the walls, the centerline, the boundary closed on itself and the reward sites, those the spec has.
    """
    traces = []
    if spec.walls:
        traces.append(polyline(spec.walls, WALL_LINE))
    if spec.centerline:
        traces.append(polyline([(s["p0"], s["p1"]) for s in spec.centerline], CENTERLINE))
    if spec.boundary:
        ring = spec.boundary + spec.boundary[:1]
        traces.append({"type": "scatter", "mode": "lines", "x": [p[0] for p in ring], "y": [p[1] for p in ring], "line": BOUNDARY_LINE,
                       "hoverinfo": "skip"})
    if spec.reward_sites:
        traces.append({"type": "scatter", "mode": "markers", "x": [p[0] for p in spec.reward_sites.values()],
                       "y": [p[1] for p in spec.reward_sites.values()], "marker": SITE_MARKER, "hovertext": list(spec.reward_sites),
                       "hovertemplate": "%{hovertext}<extra></extra>"})
    return traces


def payload(row):
    """
    What the browser needs to replay the block: its facts, the arrays per frame, the runs, trips and phases as spans, the heading fills and one-LED stretches, the environment traces and the room.
    """
    block, spec = trajectory.load_block(row["path"]), load_environment(row["environment"])
    return {"block_id": row["block_id"], "session_id": row["session_id"], "kind": row["kind"], "status": row["status"],
            "environment": row["environment"], "n_frames": row["n_frames"], "duration_s": row["duration_s"], "rate_hz": rate_of(row),
            "frame_start": int(block[trajectory.FRAME_COLUMN][0]),
            "t": floats(block["t"]), "x": floats(block["x"]), "y": floats(block["y"]), "heading": floats(block["heading"]),
            "speed": floats(block["speed"]), "n_lights": block["n_lights"].tolist(),
            "runs": run_spans(block), "trips": trip_spans(block),
            "phases": [{"phase": phase, "first": first, "last": last} for phase, first, last in spans(block["phase"])],
            "heading_filled": true_spans(block["heading_filled"]), "heading_held": true_spans(block["heading_held"]),
            "one_light": true_spans(block["n_lights"] == 1),
            "environment_traces": environment_traces(spec), "room": list(spec.room)}


def payload_of(processed, block_id):
    """
    The payload of the built block with this id.
    """
    return payload(next(row for row in trajectory.list_blocks(processed) if row["block_id"] == block_id))


def shares_for(processed, block):
    """
    The share columns of a block the browser holds, from CACHE.
    """
    return shares_of(trajectory.block_path(processed, block["kind"], block["block_id"]))
