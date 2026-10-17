"""
The review files, one json per session under the processed folder's review folder, written whole.
"""

import json

from process_lab_data.__main__ import REVIEW


def path_of(sources, session_id):
    """
    The session's review file.
    """
    return sources.processed_root() / REVIEW / f"{session_id}.json"


def read(sources, session_id):
    """
    The session's review, or None when it was not reviewed.
    """
    path = path_of(sources, session_id)
    return json.loads(path.read_text()) if path.is_file() else None


def write(sources, review):
    """
    Write the review as its session's file, replacing an earlier one, and return the path and whether one was replaced.
    """
    path = path_of(sources, review["session_id"])
    replaced = path.is_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, indent=1))
    return path, replaced


def list_ids(sources):
    """
    The ids of the reviewed sessions, sorted.
    """
    return sorted(path.stem for path in (sources.processed_root() / REVIEW).glob("*.json"))
