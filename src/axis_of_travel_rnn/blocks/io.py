"""
The block step's files: the transformed folder read as the engine takes it, the reviews read, and a built folder written a session at a time and read back.
"""

import json
from pathlib import Path

import pyarrow as pa

from . import tables

# The transformed folder (docs/transform_lab_data/tables.md 2.1 to 2.4 and 2.6): every column with its type. The tables are
# read with their types inferred, as the review tool read them, and these record the format, the required columns being
# the ones the engine reads.
SESSIONS = {
    "session_id": "string", "subject_id": "string", "group": "string", "date": "date32", "protocol": "string",
    "dvt_file": "string", "rmaps_file": "string", "rate_hz": "int64", "max_gap": "int64", "n_frames": "int64",
    "n_pauses": "int64", "paused_s": "double", "unfilled_front": "double", "unfilled_back": "double",
    "n_events": "int64", "n_runs": "int64",
}
EPOCHS = {
    "session_id": "string", "epoch": "string", "environment": "string", "condition": "string", "frame_start": "int64",
    "frame_end": "int64", "t_start": "double", "t_end": "double", "duration_s": "double",
}
RUNS = {
    "session_id": "string", "run": "int64", "epoch": "string", "path_id": "int64", "frame_start": "int64",
    "frame_end": "int64", "t_start": "double", "t_end": "double", "duration_s": "double", "clean": "bool",
    "duplicate_of": "int64", "overlap_frames": "int64", "spans_pause": "bool",
}
ANNOTATIONS = {"session_id": "string", "reward_rule": "string", "exclude": "bool", "notes": "string"}
FRAMES = {
    "session_id": "string", "frame": "int64", "t": "double", "front_x": "double", "front_y": "double",
    "back_x": "double", "back_y": "double", "head_dir": "double", "filled_front": "bool", "filled_back": "bool",
    "unfilled_front": "bool", "unfilled_back": "bool", "painted_label": "int64", "avg_x": "double",
    "avg_y": "double", "mashup_x": "double", "mashup_y": "double", "epoch": "string",
}

# File name to (columns, required columns). The annotations are made by hand and may be absent.
TABLES = {
    "sessions.csv": (SESSIONS, ("session_id", "subject_id", "group", "date", "protocol", "rate_hz", "max_gap")),
    "epochs.csv": (EPOCHS, ("session_id", "epoch", "environment", "condition", "frame_start", "frame_end", "duration_s")),
    "runs.csv": (RUNS, ("session_id", "run", "epoch", "path_id", "frame_start", "frame_end", "clean")),
    "annotations.csv": (ANNOTATIONS, ("session_id", "exclude")),
}
OPTIONAL_TABLES = ("annotations.csv",)
FRAMES_DIR = "frames"
FRAMES_REQUIRED = ("frame", "t", "front_x", "front_y", "back_x", "back_y", "head_dir", "filled_front", "filled_back",
                   "unfilled_front", "unfilled_back", "mashup_x", "mashup_y")
MANIFEST = "manifest.json"

# A built folder: one parquet per block named by its id, the blocks index, and per session what its build used. A block
# parquet holds the lab frame number first, so a row maps back to the converter's frames, then one row per frame of the
# trajectory. The blocks csv holds one wide row per block: the block and its session, where it lies, what it holds, how its
# heading was filled, how it was reviewed and the frame parameters and kinematics version it was built under. A file being
# written has the temporary suffix until it is renamed.
BLOCKS_CSV = "blocks.csv"
BLOCKS_DIR = "blocks"
METADATA_DIR = "metadata"
JSON, PARQUET, TEMP = ".json", ".parquet", ".tmp"
BLOCK_SCHEMA = pa.schema([
    ("frame", pa.int32()), ("t", pa.float64()), ("x", pa.float64()), ("y", pa.float64()), ("heading", pa.float64()),
    ("speed", pa.float64()), ("turn_rate", pa.float64()), ("n_lights", pa.int8()), ("heading_filled", pa.bool_()),
    ("heading_held", pa.bool_()), ("filled_front", pa.bool_()), ("filled_back", pa.bool_()), ("phase", pa.string()),
    ("trip", pa.int32()), ("run", pa.int32()), ("path_id", pa.int16()), ("clean", pa.bool_()),
])
BLOCKS_CSV_SCHEMA = pa.schema([
    ("block_id", pa.string()), ("session_id", pa.string()), ("subject_id", pa.string()), ("date", pa.string()),
    ("protocol", pa.string()), ("environment", pa.string()), ("epoch", pa.string()), ("kind", pa.string()),
    ("frame_start", pa.int64()), ("frame_end", pa.int64()), ("n_frames", pa.int64()), ("duration_s", pa.float64()), ("rate_hz", pa.int64()),
    ("n_runs", pa.int64()), ("n_clean_runs", pa.int64()), ("n_trips", pa.int64()), ("n_complete_trips", pa.int64()),
    ("heading_lost_s", pa.float64()), ("heading_filled_s", pa.float64()), ("heading_held_s", pa.float64()),
    ("status", pa.string()), ("reviewed_by", pa.string()),
    ("scale_px_per_m", pa.float64()), ("rotation_rad", pa.float64()), ("led_offset_rad", pa.float64()),
    ("kinematics_version", pa.int64()),
])

# What a build records per session: the rules and window settings, the review's stamp, the code, when, per block its window
# count and verdict, the registration, the warnings, the blocks not written, whether the person excluded the session and
# the start offset it was built with.
METADATA_KEYS = ("rules", "settings", "review_stamp", "code_version", "built_at", "windows", "frame", "warnings", "failed", "excluded",
                 "start_offset_m")

# The review file is the review tool's: the default a key takes when a file written before the key existed lacks it.
REVIEW_DEFAULTS = {"excluded": False, "excluded_by": None, "excluded_at": None, "start_offset_m": None}


def read_json(path):
    """
    The json file as data, none when it does not exist.
    """
    return json.loads(path.read_text()) if path.is_file() else None


def write_json(obj, path):
    """
    Write obj as sorted, indented json with a trailing newline, creating the parent folders.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def temp_of(path):
    """
    The temporary name a file is written under before it is renamed into place.
    """
    return path.with_name(path.name + TEMP)


def sessions(root):
    """
    The transformed folder's sessions, epochs, runs and annotations tables as row dicts (annotations empty when absent) and the ids of the sessions with frames.
    """
    root = Path(root)
    found = {}
    for name in TABLES:
        absent = name in OPTIONAL_TABLES and not (root / name).is_file()
        found[name.removesuffix(".csv")] = [] if absent else tables.read_csv(root / name)
    return {**found, "frames": sorted(path.stem for path in (root / FRAMES_DIR).glob(f"*{PARQUET}"))}


def stamp(root):
    """
    The converter run's timestamp from the transformed folder's manifest.
    """
    return read_json(Path(root) / MANIFEST)["run"]["timestamp"]


def session(root, sid):
    """
    One transformed session as the engine takes it: its row, epochs, runs, frames as numpy arrays and the converter run's timestamp, KeyError when it is not there.
    """
    found = sessions(root)
    row = next((s for s in found["sessions"] if s["session_id"] == sid), None)
    if row is None or sid not in found["frames"]:
        raise KeyError(f"no session {sid} with frames in {root}")
    return {"session": row, "epochs": [e for e in found["epochs"] if e["session_id"] == sid],
            "runs": [r for r in found["runs"] if r["session_id"] == sid],
            "arrays": tables.read_parquet(Path(root) / FRAMES_DIR / f"{sid}{PARQUET}"), "stamp": stamp(root)}


def reviews(root):
    """
    The ids of the sessions with a review file in the reviews folder, sorted.
    """
    return sorted(path.stem for path in Path(root).glob(f"*{JSON}"))


def review(root, sid):
    """
    The session's review from the reviews folder, none when there is none, with the default of every key an older file lacks.
    """
    found = read_json(Path(root) / f"{sid}{JSON}")
    return None if found is None else {**REVIEW_DEFAULTS, **found}


def blocks(root):
    """
    The rows of a built folder's blocks index, none when nothing was built.
    """
    path = Path(root) / BLOCKS_CSV
    return tables.read_csv(path, BLOCKS_CSV_SCHEMA) if path.is_file() else []


def block_path(root, block_id):
    """
    The parquet of a block in a built folder.
    """
    return Path(root) / BLOCKS_DIR / f"{block_id}{PARQUET}"


def block(root, block_id):
    """
    One built block, its index row and its arrays, KeyError when the index has no such block.
    """
    row = next((row for row in blocks(root) if row["block_id"] == block_id), None)
    if row is None:
        raise KeyError(f"no block {block_id} in {root}")
    return {"row": row, "arrays": tables.read_parquet(block_path(root, block_id))}


def metadata(root, sid):
    """
    What the session's build used, none when it was not built.
    """
    return read_json(Path(root) / METADATA_DIR / f"{sid}{JSON}")


def write_session(root, sid, built, meta):
    """
    Replace the session's blocks, index rows and metadata in a built folder whole: every file is written under a temporary name, then the session's old blocks go and the new files are renamed into place.
    """
    root = Path(root)
    before = blocks(root)
    rows = [row for row in before if row["session_id"] != sid] + [b["row"] for b in built]
    parquets = [block_path(root, b["row"]["block_id"]) for b in built]
    meta_path, index = root / METADATA_DIR / f"{sid}{JSON}", root / BLOCKS_CSV
    try:
        for b, target in zip(built, parquets):
            tables.write_parquet(b["arrays"], temp_of(target), BLOCK_SCHEMA)
        write_json(meta, temp_of(meta_path))
        tables.write_csv(sorted(rows, key=lambda row: row["session_id"]), temp_of(index), BLOCKS_CSV_SCHEMA)
    except Exception:
        for target in [*parquets, meta_path, index]:
            temp_of(target).unlink(missing_ok=True)
        raise
    for row in before:
        if row["session_id"] == sid:
            block_path(root, row["block_id"]).unlink(missing_ok=True)
    for target in [*parquets, meta_path, index]:
        temp_of(target).replace(target)
