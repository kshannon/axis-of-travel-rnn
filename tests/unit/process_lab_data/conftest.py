"""
Fixtures for the processor tests: a transformed lab data root of small synthetic tables, a config.
"""

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest

import proj_helpers.paths

# Six sessions across protocols and groups. S1 and S6 survive the session funnel: S2 and S5 by protocol, S4 by
# group, S3 by the annotations exclusion.
S1, S2, S3 = "NS14_rec1_20150101_001", "NS14_rec2_20150102_001", "NS15_rec3_20150103_001"
S4, S5, S6 = "JL1_rec4_20140704_001", "NS15_rec5_20150105_001", "NS16_rec6_20150106_001"
RATE_HZ, MAX_GAP = 60, 30

SESSIONS = {
    "session_id": [S1, S2, S3, S4, S5, S6],
    "subject_id": ["NS14", "NS14", "NS15", "JL1", "NS15", "NS16"],
    "group": ["NS14Data", "NS14Data", "NS15Data", "JL1HPCData", "NS15Data", "NS16Data"],
    "protocol": ["standard", "rotation", "standard", "standard", "infusion", "standard"],
    "rate_hz": [RATE_HZ] * 6,
    "max_gap": [MAX_GAP] * 6,
}

# Frames for the two surviving sessions, 1400 contiguous frames each: S1's track holds an unfilled stretch of exactly
# max_gap frames, which stays inside its block, and S6's track holds a pause that cuts it into two short halves.
N_FRAMES = 1400
FRAMES = {S1: {"pauses": (), "unfilled": ((700, 729),)}, S6: {"pauses": (901,), "unfilled": ()}}

# S6's arena carries a condition the lab's files never give a standard session, to exercise the condition step.
EPOCHS = {
    "session_id": [S1, S1, S2, S2, S2, S3, S3, S4, S4, S5, S6, S6, S6],
    "epoch": ["arena", "track", "arena", "track", "variant", "arena", "track", "arena", "track", "track",
              "arena", "track", "variant"],
    "environment": ["open_arena", "triple_t", "open_arena", "triple_t", "triple_t_rot45", "open_arena", "triple_t",
                    "open_arena", "triple_t", "triple_t", "open_arena", "triple_t", "triple_t"],
    "condition": ["baseline", "baseline", "baseline", "baseline", "rot45", "baseline", "baseline", "baseline",
                  "baseline", "musc_bilateral", "rot45", "baseline", "baseline"],
    "frame_start": [1, 601, 1, 601, 1201, 1, 601, 1, 601, 1, 1, 601, 1201],
    "frame_end": [600, 1200, 600, 1200, 1800, 600, 1200, 600, 1200, 600, 600, 1200, 1800],
    "duration_s": [10.0] * 13,
}

# S1 has three track runs, one dirty, and one run no epoch holds. S3's run is dropped with its session.
RUNS = {
    "session_id": [S1, S1, S1, S1, S3, S6],
    "run": [1, 2, 3, 4, 1, 1],
    "epoch": ["track", "track", "track", None, "track", "track"],
    "path_id": [1, 2, 1, 3, 1, 9],
    "frame_start": [610, 700, 800, 1300, 610, 610],
    "frame_end": [650, 740, 840, 1340, 650, 650],
    "clean": [True, False, True, True, True, True],
    "duplicate_of": [None, None, None, None, None, None],
}

ANNOTATIONS = {
    "session_id": [S1, S3],
    "reward_rule": ["all_but_repeats", "visit_all"],
    "exclude": [False, True],
    "notes": ["", "camera moved"],
}


def frames_table(session_id, pauses, unfilled):
    """
    A frames table (tables.md 2.4): t jumps a minute at each pause frame, both lights are unfilled over each (first, last).
    """
    frame = np.arange(1, N_FRAMES + 1)
    t = (frame - 1) / RATE_HZ
    for pause in pauses:
        t[frame >= pause] += 60.0
    lost = np.zeros(N_FRAMES, bool)
    for first, last in unfilled:
        lost[first - 1:last] = True
    x, y = np.where(lost, np.nan, 300.0 + frame % 50), np.where(lost, np.nan, 200.0 + frame % 30)
    epoch = np.full(N_FRAMES, None, object)
    for row in zip(EPOCHS["session_id"], EPOCHS["epoch"], EPOCHS["frame_start"], EPOCHS["frame_end"]):
        if row[0] == session_id:
            epoch[row[2] - 1:row[3]] = row[1]
    return pa.table({
        "session_id": [session_id] * N_FRAMES, "frame": frame, "t": t,
        "front_x": x, "front_y": y, "back_x": x - 10, "back_y": y, "head_dir": np.where(lost, np.nan, 0.0),
        "filled_front": np.zeros(N_FRAMES, bool), "filled_back": np.zeros(N_FRAMES, bool),
        "unfilled_front": lost, "unfilled_back": lost, "painted_label": np.full(N_FRAMES, 99),
        "avg_x": x - 5, "avg_y": y, "mashup_x": x - 5, "mashup_y": y, "epoch": pa.array(epoch, pa.string()),
    })


@pytest.fixture(autouse=True)
def no_local_config(monkeypatch):
    """
    Make reading configs/local.yaml an error, so every test passes its own config.
    """
    def refuse(*args, **kwargs):
        raise AssertionError("a test read configs/local.yaml, pass config instead")
    monkeypatch.setattr(proj_helpers.paths, "local_config", refuse)


@pytest.fixture
def transformed(tmp_path):
    """
    A transformed lab data root: the three tables, annotations.csv and the frames of the surviving sessions.
    """
    root = tmp_path / "transformed"
    (root / "frames").mkdir(parents=True)
    for name, columns in (("sessions", SESSIONS), ("epochs", EPOCHS), ("runs", RUNS), ("annotations", ANNOTATIONS)):
        pacsv.write_csv(pa.table(columns), root / f"{name}.csv")
    for session_id, cuts in FRAMES.items():
        pq.write_table(frames_table(session_id, **cuts), root / "frames" / f"{session_id}.parquet")
    return root


@pytest.fixture
def config(tmp_path, transformed):
    """
    Both processor keys, the transformed root and an output root next to it under tmp_path.
    """
    return {"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(tmp_path / "processed")}
