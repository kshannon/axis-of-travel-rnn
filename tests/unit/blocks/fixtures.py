"""
A synthetic transformed folder for the block tests: six sessions, two with frames, and a session read back as the engine takes it.
"""

import json

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from axis_of_travel_rnn.blocks import RULES
from axis_of_travel_rnn.blocks.geometry import geometries

# S1 and S6 are the sessions the funnel keeps: S2 to S4 have no frames and S5 has no baseline arena or track epoch.
S1, S2, S3 = "NS14_rec1_20150101_001", "NS14_rec2_20150102_001", "NS15_rec3_20150103_001"
S4, S5, S6 = "JL1_rec4_20140704_001", "NS15_rec5_20150105_001", "NS16_rec6_20150106_001"
RATE_HZ, MAX_GAP = 60, 30
STAMP = "2026-10-13T10:00:00+00:00"

SESSIONS = {
    "session_id": [S1, S2, S3, S4, S5, S6],
    "subject_id": ["NS14", "NS14", "NS15", "JL1", "NS15", "NS16"],
    "group": ["NS14Data", "NS14Data", "NS15Data", "JL1HPCData", "NS15Data", "NS16Data"],
    "date": ["2015-01-01", "2015-01-02", "2015-01-03", "2014-07-04", "2015-01-05", "2015-01-06"],
    "protocol": ["standard", "rotation", "standard", "standard", "infusion", "standard"],
    "rate_hz": [RATE_HZ] * 6,
    "max_gap": [MAX_GAP] * 6,
}

# 5400 contiguous frames per session with frames. S1's arena holds a lab filled stretch, its track loses the back light
# for 2 s. S6's track holds a pause at frame 2701. The position circles slowly, no jumps.
N_FRAMES = 5400
FRAMES = {S1: {"pauses": (), "filled": ((700, 729),), "back_lost": ((2800, 2919),)},
          S6: {"pauses": (2701,), "filled": (), "back_lost": ()}}
CIRCLE_PX, CIRCLE_FRAMES = 100.0, 600

EPOCHS = {
    "session_id": [S1, S1, S2, S2, S2, S3, S3, S4, S4, S5, S6, S6, S6],
    "epoch": ["arena", "track", "arena", "track", "variant", "arena", "track", "arena", "track", "track",
              "arena", "track", "variant"],
    "environment": ["open_arena", "triple_t", "open_arena", "triple_t", "triple_t_rot45", "open_arena", "triple_t",
                    "open_arena", "triple_t", "triple_t", "open_arena", "triple_t", "triple_t"],
    "condition": ["baseline", "baseline", "baseline", "baseline", "rot45", "baseline", "baseline", "baseline",
                  "baseline", "musc_bilateral", "rot45", "baseline", "baseline"],
    "frame_start": [1, 1801, 1, 1801, 3601, 1, 1801, 1, 1801, 1, 1, 1801, 4501],
    "frame_end": [1800, 3600, 1800, 3600, 5400, 1800, 3600, 1800, 3600, 1800, 1800, 4500, 5400],
    "duration_s": [30.0] * 11 + [45.0, 15.0],
}

RUNS = {
    "session_id": [S1, S1, S1, S1, S3, S6],
    "run": [1, 2, 3, 4, 1, 1],
    "epoch": ["track", "track", "track", None, "track", "track"],
    "path_id": [1, 9, 2, 3, 1, 4],
    "frame_start": [2200, 2400, 2600, 4000, 1810, 3100],
    "frame_end": [2300, 2500, 2700, 4040, 1850, 3200],
    "clean": [True, False, True, True, True, True],
    "duplicate_of": [None, None, None, None, None, None],
}

ANNOTATIONS = {
    "session_id": [S1, S3],
    "reward_rule": ["all_but_repeats", "visit_all"],
    "exclude": [False, True],
    "notes": ["", "camera moved"],
}


def spans_mask(spans):
    """
    True on the frames of each (first, last) span.
    """
    mask = np.zeros(N_FRAMES, bool)
    for first, last in spans:
        mask[first - 1:last] = True
    return mask


def frames_table(session_id, pauses, filled, back_lost):
    """
    A frames table (tables.md 2.4): t jumps a minute at each pause frame, both lights are lab filled over each filled span, the back light alone is lost over each back_lost span.
    """
    frame = np.arange(1, N_FRAMES + 1)
    t = (frame - 1) / RATE_HZ
    for pause in pauses:
        t[frame >= pause] += 60.0
    lab_filled, lost = spans_mask(filled), spans_mask(back_lost)
    angle = 2 * np.pi * frame / CIRCLE_FRAMES
    x, y = 300.0 + CIRCLE_PX * np.cos(angle), 200.0 + CIRCLE_PX * np.sin(angle)
    epoch = np.full(N_FRAMES, None, object)
    for row in zip(EPOCHS["session_id"], EPOCHS["epoch"], EPOCHS["frame_start"], EPOCHS["frame_end"]):
        if row[0] == session_id:
            epoch[row[2] - 1:row[3]] = row[1]
    return pa.table({
        "session_id": [session_id] * N_FRAMES, "frame": frame, "t": t,
        "front_x": x, "front_y": y, "back_x": np.where(lost, np.nan, x - 10), "back_y": np.where(lost, np.nan, y),
        "head_dir": np.where(lost, np.nan, 0.0),
        "filled_front": lab_filled, "filled_back": lab_filled,
        "unfilled_front": np.zeros(N_FRAMES, bool), "unfilled_back": lost, "painted_label": np.full(N_FRAMES, 99),
        "avg_x": np.where(lost, np.nan, x - 5), "avg_y": np.where(lost, np.nan, y),
        "mashup_x": np.where(lost, x, x - 5), "mashup_y": y, "epoch": pa.array(epoch, pa.string()),
    })


def write_transformed(root):
    """
    Write the converter's tables, manifest and the frames of the sessions that have them into the folder.
    """
    (root / "frames").mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"run": {"timestamp": STAMP}}))
    for name, columns in (("sessions", SESSIONS), ("epochs", EPOCHS), ("runs", RUNS), ("annotations", ANNOTATIONS)):
        pacsv.write_csv(pa.table(columns), root / f"{name}.csv")
    for session_id, cuts in FRAMES.items():
        pq.write_table(frames_table(session_id, **cuts), root / "frames" / f"{session_id}.parquet")


def session(root, sid):
    """
    One session of the folder as the engine takes it: its row, epochs, runs, frames as writable numpy arrays and the manifest stamp.
    """
    rows = {name: pacsv.read_csv(root / f"{name}.csv").to_pylist() for name in ("sessions", "epochs", "runs")}
    table = pq.read_table(root / "frames" / f"{sid}.parquet")
    return {"session": next(s for s in rows["sessions"] if s["session_id"] == sid),
            "epochs": [e for e in rows["epochs"] if e["session_id"] == sid], "runs": [r for r in rows["runs"] if r["session_id"] == sid],
            "arrays": {name: table.column(name).to_numpy().copy() for name in table.column_names}, "stamp": STAMP}


def tables(root):
    """
    The sessions, epochs, runs and annotations tables of the folder as row dicts and the ids of the sessions with frames.
    """
    found = {name: pacsv.read_csv(root / f"{name}.csv").to_pylist() for name in ("sessions", "epochs", "runs", "annotations")}
    return {**found, "frames": sorted(path.stem for path in (root / "frames").glob("*.parquet"))}


def loaded(root, sid):
    """
    The session as the engine takes it and the geometry by name of the environments of its epochs of the default rules' kinds.
    """
    found = session(root, sid)
    return found, geometries(found["epochs"], RULES)
