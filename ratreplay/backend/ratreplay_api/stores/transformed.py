"""
The converter's output folder (docs/transform_lab_data/tables.md 2): the tables, a session's frames, the manifest.
"""

import json
from pathlib import Path

import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from process_lab_data import select

from ..errors import NotFound

MANIFEST = "manifest.json"


def read_tables(root):
    """
    The sessions, epochs, runs and annotations tables as lists of row dicts, annotations and verdicts empty when absent.
    """
    return select.read_tables(root)


def has_file(root, name):
    """
    Whether the folder holds the file.
    """
    return (Path(root) / name).is_file()


def csv_columns(root, name):
    """
    The column names of a csv file, read from its header.
    """
    return pacsv.open_csv(Path(root) / name).schema.names


def frame_ids(root):
    """
    The ids of the sessions that have a frames file, sorted.
    """
    return sorted(path.stem for path in (Path(root) / select.FRAMES).glob("*.parquet"))


def frames_columns(root, session_id):
    """
    The column names of a session's frames file, read from its footer.
    """
    return pq.read_schema(Path(root) / select.FRAMES / f"{session_id}.parquet").names


def frames_path(root, session_id):
    """
    The path of a session's frames file.
    """
    return Path(root) / select.FRAMES / f"{session_id}.parquet"


def read_frames(root, session_id):
    """
    A session's frames as a dict of numpy arrays.
    """
    return select.read_frames(root, session_id)


def read_session(root, session_id):
    """
    One session: its row, its epochs and runs and its frames, or NotFound when the table has no such session or no frames file.
    """
    tables = read_tables(root)
    session = next((s for s in tables["sessions"] if s["session_id"] == session_id), None)
    if session is None:
        raise NotFound(f"no session {session_id}")
    if not frames_path(root, session_id).is_file():
        raise NotFound(f"session {session_id} has no frames file")
    return {"session": session,
            "epochs": [e for e in tables["epochs"] if e["session_id"] == session_id],
            "runs": [r for r in tables["runs"] if r["session_id"] == session_id],
            "frames": read_frames(root, session_id)}


def manifest(root):
    """
    The converter's manifest as a dict.
    """
    return json.loads((Path(root) / MANIFEST).read_text())
