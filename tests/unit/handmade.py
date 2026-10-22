"""
Hand made blocks for the library's tests: a block's row and arrays as the built folder gives them, never real data.
"""

import numpy as np

from axis_of_travel_rnn.blocks import RULES
from axis_of_travel_rnn.blocks.geometry import geometry

LAB_RATE_HZ = 60
TRAINING_RATE_HZ = 20
RUN_SPEED = 0.3  # m/s along a corridor


def block(x, y, heading, rate_hz=LAB_RATE_HZ, kind="track", block_id="S1_track_01", session_id="S1", date="2026-01-01",
          run=None):
    """
    A block of these positions and headings with every column of the built parquet, one outbound run in one partial trip on the track, a speed of 0.2 m/s.
    """
    n = len(x)
    arrays = {
        "frame": np.arange(1, n + 1, dtype=np.int32), "t": np.arange(n) / rate_hz, "x": np.asarray(x, float),
        "y": np.asarray(y, float), "heading": np.asarray(heading, float), "speed": np.full(n, 0.2),
        "turn_rate": np.zeros(n), "n_lights": np.full(n, 2, np.int8), "heading_filled": np.zeros(n, bool),
        "heading_held": np.zeros(n, bool), "filled_front": np.zeros(n, bool), "filled_back": np.zeros(n, bool),
        "phase": np.full(n, "outbound" if kind == "track" else "forage", "U8"), "trip": np.full(n, -1 if kind == "track" else 0, np.int32),
        "run": np.ones(n, np.int32) if run is None else np.asarray(run, np.int32),
        "path_id": np.ones(n, np.int16), "clean": np.ones(n, bool),
    }
    row = {"block_id": block_id, "session_id": session_id, "date": date, "environment": "triple_t" if kind == "track" else "open_arena",
           "kind": kind, "epoch": kind, "n_frames": n, "rate_hz": rate_hz, "duration_s": n / rate_hz}
    return {"row": row, "arrays": arrays, "rules": RULES, "start_offset_m": None}


def wandering(n, seed, rate_hz=LAB_RATE_HZ, **keys):
    """
    A block of a smooth random walk in the room with a heading of its own, at rate_hz.
    """
    rng = np.random.default_rng(seed)
    x = 0.9 + 0.3 * np.sin(np.cumsum(rng.normal(0.0, 0.02, n)))
    y = 0.9 + 0.3 * np.cos(np.cumsum(rng.normal(0.0, 0.03, n)))
    heading = np.angle(np.exp(1j * np.cumsum(rng.normal(0.0, 0.1, n))))
    return block(x, y, heading, rate_hz, **keys)


def corridor_travel(plan, rate_hz=TRAINING_RATE_HZ):
    """
    A track block running each (segment name, forward) of the plan along the triple-T's centre line, and the direction of each frame (0 E, 1 W, 2 N, 3 S).
    """
    found = geometry("triple_t")
    segments = {s["name"]: s for s in found["centerline"]}
    xy, run, direction, segment = [], [], [], []
    for number, (name, forward) in enumerate(plan, start=1):
        p0, p1 = np.array(segments[name]["p0"]), np.array(segments[name]["p1"])
        start, stop = (p0, p1) if forward else (p1, p0)
        n = int(np.linalg.norm(p1 - p0) / RUN_SPEED * rate_hz)
        xy.append(start + np.linspace(0.0, 1.0, n)[:, None] * (stop - start))
        axis = int(segments[name]["axis_deg"] == 90)
        run += [number] * n
        direction += [2 * axis + int((stop - start)[axis] < 0)] * n
        segment += [name] * n
    xy = np.concatenate(xy)
    made = block(xy[:, 0], xy[:, 1], np.zeros(len(xy)), rate_hz, run=run)
    made["arrays"]["speed"][:] = RUN_SPEED
    return made, np.array(direction), np.array(segment)
