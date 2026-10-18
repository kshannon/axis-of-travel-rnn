"""
The converter's output folder (docs/transform_lab_data/tables.md 2): the tables, a session's frames, the manifest.
"""

import json

import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from process_lab_data import select

from ..utilities.errors import NotFound

MANIFEST = "manifest.json"


def read_tables(sources):
    """
    The sessions, epochs, runs and annotations tables as lists of row dicts, annotations and verdicts empty when absent.
    """
    return select.read_tables(sources.transformed_root())


def has_file(sources, name):
    """
    Whether the folder holds the file.
    """
    return (sources.transformed_root() / name).is_file()


def csv_columns(sources, name):
    """
    The column names of a csv file, read from its header.
    """
    return pacsv.open_csv(sources.transformed_root() / name).schema.names


def frame_ids(sources):
    """
    The ids of the sessions that have a frames file, sorted.
    """
    return sorted(path.stem for path in (sources.transformed_root() / select.FRAMES).glob("*.parquet"))


def frames_path(sources, session_id):
    """
    The path of a session's frames file.
    """
    return sources.transformed_root() / select.FRAMES / f"{session_id}.parquet"


def frames_columns(sources, session_id):
    """
    The column names of a session's frames file, read from its footer.
    """
    return pq.read_schema(frames_path(sources, session_id)).names


def frames_stamp(sources, session_id):
    """
    What identifies this version of a session's frames file, its path and modification time, none when it has no frames file.
    """
    path = frames_path(sources, session_id)
    return (path, path.stat().st_mtime_ns) if path.is_file() else None


def read_frames(sources, session_id):
    """
    A session's frames as a dict of numpy arrays.
    """
    return select.read_frames(sources.transformed_root(), session_id)


def read_session(sources, session_id):
    """
    One session: its row, its epochs and runs and its frames, or NotFound when the table has no such session or no frames file.
    """
    tables = read_tables(sources)
    session = next((s for s in tables["sessions"] if s["session_id"] == session_id), None)
    if session is None:
        raise NotFound(f"no session {session_id}")
    if not frames_path(sources, session_id).is_file():
        raise NotFound(f"session {session_id} has no frames file")
    return {"session": session,
            "epochs": [e for e in tables["epochs"] if e["session_id"] == session_id],
            "runs": [r for r in tables["runs"] if r["session_id"] == session_id],
            "frames": read_frames(sources, session_id)}


def manifest(sources):
    """
    The converter's manifest as a dict.
    """
    return json.loads((sources.transformed_root() / MANIFEST).read_text())
