"""
The lab's variables as tables and rows: frames, epochs, events, runs and the session row, as pure functions.
"""

from dataclasses import replace

import numpy as np
import pyarrow as pa

from .readers import COLUMNS, DVT_COLUMNS

# The lab's event labels: path n from 1 to MAX_PATH starts a run and n + END_OFFSET ends it, the sign is clean (+)
# or dirty (-); INDECISION and REWARD mark those moments, any other label is other.
MAX_PATH = 98
END_OFFSET = 100
INDECISION = 0
REWARD = 777

# timeStamps holds a start and end frame per epoch: arena and track, plus the variant when the file has a variant tag.
STAMPS_PLAIN = 4
STAMPS_VARIANT = 6
# The stamps status from build_epochs: none, a wrong count, a stamp not a whole frame in the tracking, stamps out of
# order, usable, or usable with a count the file's tag does not match.
STAMPS_ABSENT = "absent"
STAMPS_BAD_COUNT = "count"
STAMPS_BAD_RANGE = "range"
STAMPS_BAD_ORDER = "order"
STAMPS_OK = "ok"
STAMPS_BAD_TAG = "tag"

# A step in t over this many seconds is a pause; the camera's frame time is subtracted from it, not sampleRate.
PAUSE_STEP_S = 0.1
FRAME_S = 1 / 60

# The values a column may hold (tables.md 2.8), the ones the functions use by name first.
ARENA = "open_arena"
TRACK = "triple_t"
KIND_START = "start"
KIND_END = "end"
KIND_INDECISION = "indecision"
KIND_REWARD = "reward"
KIND_OTHER = "other"
UNKNOWN_PROTOCOL = "other"
EPOCH_NAMES = ("arena", "track", "variant")
ENVIRONMENTS = (ARENA, TRACK, "triple_t_rot45", "triple_t_rot90")
KINDS = (KIND_START, KIND_END, KIND_INDECISION, KIND_REWARD, KIND_OTHER)
PROTOCOLS = ("standard", "rotation", "infusion", "dark", UNKNOWN_PROTOCOL)
VOCABULARIES = {"epoch": EPOCH_NAMES, "environment": ENVIRONMENTS, "kind": KINDS, "protocol": PROTOCOLS}

# The condition of an epoch the tag does not change, and the file tag that is no variant tag.
BASELINE = "baseline"
NO_TAG = "tt"
# Lowercase file tag to what it gives the file's epochs and its session row (tables.md 2.8); None is a file with no
# variant tag.
TAGS = {
    None: {"environment": None, "condition": BASELINE, "whole_file": False, "protocol": "standard"},
    NO_TAG: {"environment": None, "condition": BASELINE, "whole_file": False, "protocol": "standard"},
    "plus45": {"environment": "triple_t_rot45", "condition": "rot45", "whole_file": False, "protocol": "rotation"},
    "plus45turn": {"environment": "triple_t_rot45", "condition": "rot45", "whole_file": False, "protocol": "rotation"},
    "plusquarter": {"environment": "triple_t_rot90", "condition": "rot90", "whole_file": False, "protocol": "rotation"},
    "plusquarterturn": {"environment": "triple_t_rot90", "condition": "rot90", "whole_file": False,
                        "protocol": "rotation"},
    "bilatmusc": {"environment": TRACK, "condition": "musc_bilateral", "whole_file": True, "protocol": "infusion"},
    "leftmusc": {"environment": TRACK, "condition": "musc_left", "whole_file": True, "protocol": "infusion"},
    "bilatacsf": {"environment": TRACK, "condition": "acsf_bilateral", "whole_file": True, "protocol": "infusion"},
    "leftacsf": {"environment": TRACK, "condition": "acsf_left", "whole_file": True, "protocol": "infusion"},
    "dark": {"environment": TRACK, "condition": "dark", "whole_file": True, "protocol": "dark"},
}

# The frames columns that hold a position, each blanked where the lab left its light or lights unfilled.
POSITIONS = ("front_x", "front_y", "back_x", "back_y", "avg_x", "avg_y", "mashup_x", "mashup_y")

# The output tables (tables.md 2.1 to 2.5).
SESSIONS = pa.schema([
    pa.field("session_id", pa.string(), nullable=False),
    pa.field("subject_id", pa.string(), nullable=False),
    pa.field("group", pa.string(), nullable=False),
    pa.field("date", pa.date32(), nullable=False),
    pa.field("protocol", pa.string(), nullable=False),
    pa.field("dvt_file", pa.string(), nullable=False),
    pa.field("rmaps_file", pa.string(), nullable=False),
    pa.field("rate_hz", pa.int64(), nullable=False),
    pa.field("max_gap", pa.int64(), nullable=False),
    pa.field("n_frames", pa.int64(), nullable=False),
    pa.field("n_pauses", pa.int64(), nullable=False),
    pa.field("paused_s", pa.float64(), nullable=False),
    pa.field("unfilled_front", pa.float64(), nullable=False),
    pa.field("unfilled_back", pa.float64(), nullable=False),
    pa.field("n_events", pa.int64(), nullable=False),
    pa.field("n_runs", pa.int64(), nullable=False),
])
EPOCHS = pa.schema([
    pa.field("session_id", pa.string(), nullable=False),
    pa.field("epoch", pa.string(), nullable=False),
    pa.field("environment", pa.string(), nullable=False),
    pa.field("condition", pa.string(), nullable=False),
    pa.field("frame_start", pa.int64(), nullable=False),
    pa.field("frame_end", pa.int64(), nullable=False),
    pa.field("t_start", pa.float64(), nullable=False),
    pa.field("t_end", pa.float64(), nullable=False),
    pa.field("duration_s", pa.float64(), nullable=False),
])
RUNS = pa.schema([
    pa.field("session_id", pa.string(), nullable=False),
    pa.field("run", pa.int64(), nullable=False),
    pa.field("epoch", pa.string()),
    pa.field("path_id", pa.int64(), nullable=False),
    pa.field("frame_start", pa.int64(), nullable=False),
    pa.field("frame_end", pa.int64(), nullable=False),
    pa.field("t_start", pa.float64()),
    pa.field("t_end", pa.float64()),
    pa.field("duration_s", pa.float64(), nullable=False),
    pa.field("clean", pa.bool_(), nullable=False),
    pa.field("duplicate_of", pa.int64()),
    pa.field("overlap_frames", pa.int64(), nullable=False),
    pa.field("spans_pause", pa.bool_(), nullable=False),
])
EVENTS = pa.schema([
    pa.field("session_id", pa.string(), nullable=False),
    pa.field("event", pa.int64(), nullable=False),
    pa.field("frame", pa.int64(), nullable=False),
    pa.field("t", pa.float64(), nullable=False),
    pa.field("label", pa.int64(), nullable=False),
    pa.field("kind", pa.string(), nullable=False),
    pa.field("run", pa.int64()),
])
FRAMES = pa.schema([
    pa.field("session_id", pa.string(), nullable=False),
    pa.field("frame", pa.int64(), nullable=False),
    pa.field("t", pa.float64(), nullable=False),
    pa.field("front_x", pa.float64(), nullable=False),
    pa.field("front_y", pa.float64(), nullable=False),
    pa.field("back_x", pa.float64(), nullable=False),
    pa.field("back_y", pa.float64(), nullable=False),
    pa.field("head_dir", pa.float64(), nullable=False),
    pa.field("filled_front", pa.bool_(), nullable=False),
    pa.field("filled_back", pa.bool_(), nullable=False),
    pa.field("unfilled_front", pa.bool_(), nullable=False),
    pa.field("unfilled_back", pa.bool_(), nullable=False),
    pa.field("painted_label", pa.int64()),
    pa.field("avg_x", pa.float64(), nullable=False),
    pa.field("avg_y", pa.float64(), nullable=False),
    pa.field("mashup_x", pa.float64(), nullable=False),
    pa.field("mashup_y", pa.float64(), nullable=False),
    pa.field("epoch", pa.string()),
])
TABLES = {"sessions": SESSIONS, "epochs": EPOCHS, "runs": RUNS, "events": EVENTS, "frames": FRAMES}
KEYS = {
    "sessions": ("session_id",),
    "epochs": ("session_id", "epoch"),
    "runs": ("session_id", "run"),
    "events": ("session_id", "event"),
    "frames": ("session_id", "frame"),
}
# the CSV tables in the order they are written
CSV_TABLES = {name: TABLES[name] for name in ("epochs", "runs", "events", "sessions")}


def table(name, data):
    """
    The named table from a list of row dicts or a dict of columns, refusing anything the table does not allow.
    """
    schema = TABLES[name]
    names = set(schema.names)
    rows = [data] if isinstance(data, dict) else data
    for row in rows:
        if set(row) != names:
            raise ValueError(f"columns differ from the schema: unknown {sorted(set(row) - names)}, "
                             f"missing {sorted(names - set(row))}")
    if isinstance(data, dict):
        columns = {name: data[name] for name in schema.names}
    else:
        columns = {name: [row[name] for row in data] for name in schema.names}
    result = pa.Table.from_pydict(columns, schema=schema)
    for field in schema:
        column = result.column(field.name)
        if not field.nullable and column.null_count > 0:
            raise ValueError(f"{field.name}: {column.null_count} nulls in a column that allows none")
        if field.name in VOCABULARIES:
            unknown = set(column.to_pylist()) - set(VOCABULARIES[field.name]) - {None}
            if unknown:
                raise ValueError(f"{field.name}: values outside the vocabulary {sorted(unknown)}")
    return result


def _kind(label):
    """
    The event kind of a lab label.
    """
    if 1 <= abs(label) <= MAX_PATH:
        return KIND_START
    if END_OFFSET + 1 <= abs(label) <= END_OFFSET + MAX_PATH:
        return KIND_END
    if label == INDECISION:
        return KIND_INDECISION
    if label == REWARD:
        return KIND_REWARD
    return KIND_OTHER


def _tag_info(tag_raw):
    """
    What a file tag gives its epochs, from the tag lookup, or the unknown tag kept verbatim as the condition.
    """
    key = tag_raw.lower() if tag_raw else None
    fallback = {"environment": TRACK, "condition": tag_raw, "whole_file": False, "protocol": UNKNOWN_PROTOCOL}
    return TAGS.get(key) or fallback


def pauses(t):
    """
    The pauses as (frame, seconds): the first frame after a step in t over the pause step, and the step minus a frame.
    """
    steps = np.diff(t)
    return [(int(i) + 2, float(steps[i] - FRAME_S)) for i in np.flatnonzero(steps > PAUSE_STEP_S)]


def build_epochs(session_id, tag_raw, stamps, t, n, rate):
    """
    The epoch rows from timeStamps (none unless usable) and the stamps status.
    """
    if stamps is None:
        return [], STAMPS_ABSENT
    if len(stamps) not in (STAMPS_PLAIN, STAMPS_VARIANT):
        return [], STAMPS_BAD_COUNT
    if not np.all(np.isfinite(stamps)) or np.any(stamps != np.round(stamps)):
        return [], STAMPS_BAD_RANGE
    marks = [int(x) for x in stamps]
    if any(b <= a for a, b in zip(marks, marks[1:])):
        return [], STAMPS_BAD_ORDER
    if marks[0] < 1 or marks[-1] > n:
        return [], STAMPS_BAD_RANGE
    info = _tag_info(tag_raw)
    ordinary = info["condition"] if info["whole_file"] else BASELINE
    variant = (info["environment"] or TRACK, info["condition"])
    settings = [(ARENA, ordinary), (TRACK, ordinary), variant]
    has_variant_tag = (tag_raw or NO_TAG).lower() != NO_TAG
    status = STAMPS_OK if (len(marks) == STAMPS_VARIANT) == has_variant_tag else STAMPS_BAD_TAG
    rows = []
    for k in range(len(marks) // 2):
        start, end = marks[2 * k], marks[2 * k + 1]
        rows.append({
            "session_id": session_id,
            "epoch": EPOCH_NAMES[k],
            "environment": settings[k][0],
            "condition": settings[k][1],
            "frame_start": start,
            "frame_end": end,
            "t_start": float(t[start - 1]),
            "t_end": float(t[end - 1]),
            "duration_s": (end - start + 1) / rate,
        })
    return rows, status


def build_frames(session_id, trk, painted, epochs):
    """
    The frames table: NaN where the lab left a light unfilled, epoch by inclusive range, painted label or null.
    """
    dvt = trk["processedDVT"]
    n = len(dvt)
    cols = DVT_COLUMNS
    unfilled = np.asarray(trk["samplesUnfilled"], dtype=bool)
    filled = np.asarray(trk["samplesFilled"], dtype=bool)
    gone = {
        "front": unfilled[:, 0],
        "back": unfilled[:, 1],
        "avg": unfilled[:, 0] | unfilled[:, 1],
        "mashup": unfilled[:, 0] & unfilled[:, 1],
    }
    data = {
        "session_id": [session_id] * n,
        "frame": dvt[:, cols["frame"]].astype(np.int64),
        "t": dvt[:, cols["t"]],
        "head_dir": trk["HDRadians"],
        "filled_front": filled[:, 0],
        "filled_back": filled[:, 1],
        "unfilled_front": unfilled[:, 0],
        "unfilled_back": unfilled[:, 1],
        "painted_label": [None] * n if painted is None else painted.astype(np.int64),
    }
    for name in POSITIONS:
        values = dvt[:, cols[name]].copy()
        values[gone[name.split("_")[0]]] = np.nan
        data[name] = values
    epoch = [None] * n
    for e in epochs:
        epoch[e["frame_start"] - 1:e["frame_end"]] = [e["epoch"]] * (e["frame_end"] - e["frame_start"] + 1)
    data["epoch"] = epoch
    return table("frames", data)


def pair_events(events):
    """
    The (start, end) event index pairs in click order, 0-based.
    """
    frames = events[:, 0].tolist()
    labels = events[:, 2].astype(np.int64).tolist()
    taking = [i for i in range(len(labels)) if frames[i] != 0 and _kind(labels[i]) in (KIND_START, KIND_END)]
    pairs = []
    for i, j in zip(taking, taking[1:]):
        if _kind(labels[i]) == KIND_START and labels[j] == labels[i] + (END_OFFSET if labels[i] > 0 else -END_OFFSET):
            pairs.append((i, j))
    return pairs


def build_runs(session_id, pairs, events, t, n, epochs, pauses, rate):
    """
    The run rows numbered by start frame then click order, and the run number of each paired event index.
    """
    spans = [(int(events[s, 0]), int(events[e, 0]), int(events[s, 2]), s, e) for s, e in pairs]
    spans.sort(key=lambda span: (span[0], span[3]))
    rows, run_by_event = [], {}
    for i, (start, end, label, s, e) in enumerate(spans):
        duplicate_of = None
        for j, (start0, end0, label0, _, _) in enumerate(spans[:i]):
            shared = max(0, min(end, end0) - max(start, start0) + 1)
            shorter = min(end - start, end0 - start0) + 1
            if label0 == label and shared > 0 and 2 * shared >= shorter:
                duplicate_of = j + 1
                break
        rows.append({
            "session_id": session_id,
            "run": i + 1,
            "epoch": next((x["epoch"] for x in epochs if x["frame_start"] <= start <= x["frame_end"]), None),
            "path_id": abs(label),
            "frame_start": start,
            "frame_end": end,
            "t_start": float(t[start - 1]) if 1 <= start <= n else None,
            "t_end": float(t[end - 1]) if 1 <= end <= n else None,
            "duration_s": (end - start + 1) / rate,
            "clean": label > 0,
            "duplicate_of": duplicate_of,
            "overlap_frames": max(0, spans[i - 1][1] - start + 1) if i else 0,
            "spans_pause": any(start < p <= end for p, _ in pauses),
        })
        run_by_event[s] = run_by_event[e] = i + 1
    return rows, run_by_event


def session_row(session, trk, rows, pauses):
    """
    The sessions.csv row: file facts, counts, the unfilled fractions and the protocol from the file's tag.
    """
    unfilled = trk["samplesUnfilled"]
    return {
        "session_id": session.session_id,
        "subject_id": session.subject_id,
        "group": session.group,
        "date": session.date,
        "protocol": _tag_info(session.tag_raw)["protocol"],
        "dvt_file": session.dvt_path.name,
        "rmaps_file": session.rmaps_path.name,
        "rate_hz": int(round(trk["sampleRate"])),
        "max_gap": int(round(trk["maxGap"])),
        "n_frames": len(trk["processedDVT"]),
        "n_pauses": len(pauses),
        "paused_s": float(sum(seconds for _, seconds in pauses)),
        "unfilled_front": float(unfilled[:, 0].mean()),
        "unfilled_back": float(unfilled[:, 1].mean()),
        "n_events": len(rows["events"]),
        "n_runs": len(rows["runs"]),
    }


def convert(record):
    """
    The record with its read dicts as the frames table, the rows of each CSV table and the facts the checks use.
    """
    session, trk, ana = record.session, record.trk, record.ana
    dvt = trk["processedDVT"]
    n = len(dvt)
    t = dvt[:, DVT_COLUMNS["t"]]
    rate = int(round(trk["sampleRate"]))
    found = pauses(t)
    epochs, status = build_epochs(session.session_id, session.tag_raw, ana.get("timeStamps"), t, n, rate)
    events = ana.get("spiral_events", np.empty((0, COLUMNS["spiral_events"])))
    pairs = pair_events(events)
    runs, run_by_event = build_runs(session.session_id, pairs, events, t, n, epochs, found, rate)
    pixel = record.aligned_pixel()
    rows = {
        "epochs": epochs,
        "runs": runs,
        "events": [
            {
                "session_id": session.session_id,
                "event": i + 1,
                "frame": int(frame),
                "t": float(time),
                "label": int(label),
                "kind": _kind(int(label)),
                "run": run_by_event.get(i),
            }
            for i, (frame, time, label) in enumerate(events)
        ],
    }
    rows["sessions"] = [session_row(session, trk, rows, found)]
    frames = build_frames(session.session_id, trk, None if pixel is None else pixel[:, -1], epochs)
    facts = {"tag": session.tag_raw, "stamps": status, "pauses": found, "frame_rows": frames.num_rows}
    return replace(record, frames=frames, rows=rows, facts=facts)
