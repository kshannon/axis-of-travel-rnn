"""
The RatReplay data format: the files, columns and types a folder must have to be read. The sources manager checks it and GET /api/format serves it.
"""

from axis_of_travel_rnn import trajectory
from axis_of_travel_rnn.windows import DEFAULTS
from process_lab_data import output

from .engines import edits

VERSION = 1

# The transformed folder (docs/transform_lab_data/tables.md 2.1 to 2.4 and 2.6): every column with its type. A folder
# is read when it has the columns the tool reads, REQUIRED below, the others are the converter's and optional here.
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
FRAMES_REQUIRED = ("frame", "t", "front_x", "front_y", "back_x", "back_y", "head_dir", "unfilled_front", "unfilled_back",
                   "mashup_x", "mashup_y")
MANIFEST = "manifest.json"
TRANSFORMED_MANIFEST_KEYS = ("run.timestamp",)

# The processed folder (docs/process_lab_data/spec.md Outputs), from the processor's own schemas: one blocks csv and one
# parquet per block under each kind's folder, and the manifest the window settings file takes its rules from.
BLOCKS_CSV = {field.name: str(field.type) for field in output.BLOCKS_CSV_SCHEMA}
BLOCK_PARQUET = {field.name: str(field.type) for field in output.BLOCK_SCHEMA}
PROCESSED_MANIFEST_KEYS = ("run.timestamp", "run.rules")

# The review file, one per session under the processed folder's review folder, and the fields each edit carries.
REVIEW_KEYS = ("session_id", "reviewed_by", "reviewed_at", "converter_manifest_timestamp", "rules", "blocks", "cuts",
               "flagged_runs", "notes", "edits")
EDIT_FIELDS = {"accept": (), "confirm": ("frame",), "move": ("frame", "edge", "at"), "split": ("frame",), "drop": ("frame",),
               "new": ("frame_start", "frame_end"), "cut": ("frame_start", "frame_end"), "flag": ("run",)}


def columns_of(columns, required):
    """
    The columns as the format lists them, name and type and whether the tool needs it.
    """
    return [{"name": name, "type": kind, "required": name in required} for name, kind in columns.items()]


def build():
    """
    The contract as json: the transformed, processed and review formats and the window settings the blocks are tested at.
    """
    transformed = [{"path": name, "optional": name in OPTIONAL_TABLES, "columns": columns_of(*TABLES[name])} for name in TABLES]
    transformed.append({"path": f"{FRAMES_DIR}/<session_id>.parquet", "optional": False, "columns": columns_of(FRAMES, FRAMES_REQUIRED)})
    transformed.append({"path": MANIFEST, "optional": False, "keys": list(TRANSFORMED_MANIFEST_KEYS)})
    processed = [{"path": f"<kind>/{trajectory.BLOCKS_CSV}", "optional": False, "columns": columns_of(BLOCKS_CSV, tuple(BLOCKS_CSV))},
                 {"path": f"<kind>/{trajectory.BLOCKS_DIR}/<block_id>.parquet", "optional": False,
                  "columns": columns_of(BLOCK_PARQUET, tuple(BLOCK_PARQUET))},
                 {"path": trajectory.MANIFEST, "optional": False, "keys": list(PROCESSED_MANIFEST_KEYS)}]
    return {
        "version": VERSION,
        "transformed": {"files": transformed},
        "processed": {"kinds": list(trajectory.KINDS), "files": processed},
        "review": {"path": "review/<session_id>.json", "keys": list(REVIEW_KEYS), "block_keys": list(edits.BLOCK_KEYS),
                   "statuses": list(edits.STATUSES), "edits": {op: list(fields) for op, fields in EDIT_FIELDS.items()}},
        "window_settings": DEFAULTS,
    }
