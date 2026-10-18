"""
The converter's output folder (docs/transform_lab_data/tables.md 2): its format, its health, the tables and a session's frames. Read only.
"""

import json

from ..utilities import paths, tables
from ..utilities.errors import NotFound

# The transformed folder (docs/transform_lab_data/tables.md 2.1 to 2.4 and 2.6): every column with its type. A folder
# is read when it has the columns the tool reads, the required ones below, the others are the converter's and optional here.
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
TRANSFORMED_MANIFEST_KEYS = ("run.timestamp",)


def columns_of(columns, required):
    """
    The columns as the format lists them, name and type and whether the tool needs it.
    """
    return [{"name": name, "type": kind, "required": name in required} for name, kind in columns.items()]


def has_key(manifest, dotted):
    """
    Whether the manifest holds the key, "run.timestamp" meaning the timestamp inside run.
    """
    for part in dotted.split("."):
        manifest = manifest.get(part) if isinstance(manifest, dict) else None
    return manifest is not None


def column_problems(name, required, found):
    """
    The one problem of a file lacking required columns, none when it has them all.
    """
    missing = [column for column in required if column not in found]
    return [f"{name} lacks {', '.join(missing)}"] if missing else []


class TransformedAccess:
    """
    The transformed folder at root: its format, its health, the sessions and one session's frames.
    """

    def __init__(self, root):
        self.root = root

    def schema(self):
        """
        The files, columns and types the folder must have to be read, as json.
        """
        files = [{"path": name, "optional": name in OPTIONAL_TABLES, "columns": columns_of(*TABLES[name])} for name in TABLES]
        files.append({"path": f"{FRAMES_DIR}/<session_id>.parquet", "optional": False, "columns": columns_of(FRAMES, FRAMES_REQUIRED)})
        files.append({"path": MANIFEST, "optional": False, "keys": list(TRANSFORMED_MANIFEST_KEYS)})
        return {"files": files}

    def health(self):
        """
        The folder's root, whether it exists, how it breaks the format, and when whole its counts and manifest facts.
        """
        exists = self.root.is_dir()
        problems = self._problems() if exists else [f"{self.root} does not exist"]
        health = {"root": str(self.root), "exists": exists, "problems": problems, "counts": {}, "manifest": None}
        if problems:
            return health
        found = self.sessions()
        counts = {name: len(found[name]) for name in ("sessions", "epochs", "runs", "frames")}
        manifest = {"timestamp": self._manifest()["run"]["timestamp"], "modified": paths.newest_mtime(self.root)}
        return {**health, "counts": counts, "manifest": manifest}

    def sessions(self):
        """
        The sessions, epochs, runs and annotations tables as row dicts (annotations empty when absent) and the ids of the sessions with frames.
        """
        found = {}
        for name in TABLES:
            absent = name in OPTIONAL_TABLES and not (self.root / name).is_file()
            found[name.removesuffix(".csv")] = [] if absent else tables.read_csv(self.root / name)
        return {**found, "frames": self._frame_ids()}

    def session(self, sid):
        """
        One session: its row, epochs, runs, frames as numpy arrays and the converter run's timestamp, or NotFound.
        """
        found = self.sessions()
        row = next((s for s in found["sessions"] if s["session_id"] == sid), None)
        if row is None:
            raise NotFound(f"no session {sid}")
        if sid not in found["frames"]:
            raise NotFound(f"session {sid} has no frames file")
        return {"session": row,
                "epochs": [e for e in found["epochs"] if e["session_id"] == sid],
                "runs": [r for r in found["runs"] if r["session_id"] == sid],
                "arrays": tables.read_parquet(self._frames_path(sid)),
                "stamp": self._manifest()["run"]["timestamp"]}

    def _manifest(self):
        """
        The converter's manifest as a dict.
        """
        return json.loads((self.root / MANIFEST).read_text())

    def _frames_path(self, sid):
        """
        The path of a session's frames file.
        """
        return self.root / FRAMES_DIR / f"{sid}.parquet"

    def _frame_ids(self):
        """
        The ids of the sessions that have a frames file, sorted.
        """
        return sorted(path.stem for path in (self.root / FRAMES_DIR).glob("*.parquet"))

    def _problems(self):
        """
        How the folder breaks its format: the tables, the manifest and the first frames file are checked.
        """
        problems = []
        for name, (_, required) in TABLES.items():
            if (self.root / name).is_file():
                problems += column_problems(name, required, tables.csv_columns(self.root / name))
            elif name not in OPTIONAL_TABLES:
                problems.append(f"missing {name}")
        problems += self._manifest_problems()
        ids = self._frame_ids()
        if ids:
            first = self._frames_path(ids[0])
            problems += column_problems(str(first.relative_to(self.root)), FRAMES_REQUIRED, tables.parquet_columns(first))
        else:
            problems.append(f"{FRAMES_DIR}/ holds no parquet files")
        return problems

    def _manifest_problems(self):
        """
        What is wrong with the manifest file: missing, not json, or lacking a key.
        """
        if not (self.root / MANIFEST).is_file():
            return [f"missing {MANIFEST}"]
        try:
            manifest = self._manifest()
        except ValueError:
            return [f"{MANIFEST} is not valid json"]
        return [f"{MANIFEST} lacks {key}" for key in TRANSFORMED_MANIFEST_KEYS if not has_key(manifest, key)]
