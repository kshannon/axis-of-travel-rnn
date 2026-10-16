"""
The attached sources, a json list of entries in a file outside the repository. Attaching is idempotent, detaching forgets the entry and never touches the data.
"""

import hashlib
import json
from pathlib import Path

from .clock import iso_now
from .errors import NotFound

ID_LENGTH = 8


def source_id(path):
    """
    A short hash of the resolved path.
    """
    return hashlib.sha256(str(path).encode()).hexdigest()[:ID_LENGTH]


def read_all(registry_path):
    """
    Every entry, none when the file does not exist yet.
    """
    registry_path = Path(registry_path)
    return json.loads(registry_path.read_text()) if registry_path.is_file() else []


def write_all(registry_path, entries):
    """
    Write the entries whole, creating the folder on the first attach.
    """
    registry_path = Path(registry_path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(entries, indent=1))


def get(registry_path, sid):
    """
    The entry with this id.
    """
    for entry in read_all(registry_path):
        if entry["id"] == sid:
            return entry
    raise NotFound(f"no source {sid}")


def attach(registry_path, kind, path, processed_path):
    """
    Record the source and return its entry, or the entry already recorded for the same path.
    """
    path = Path(path).expanduser().resolve()
    entries = read_all(registry_path)
    found = next((e for e in entries if e["id"] == source_id(path)), None)
    if found:
        return found
    entry = {"id": source_id(path), "kind": kind, "path": str(path),
             "processed_path": str(Path(processed_path).expanduser().resolve()), "attached_at": iso_now()}
    write_all(registry_path, entries + [entry])
    return entry


def detach(registry_path, sid):
    """
    Forget the entry with this id.
    """
    get(registry_path, sid)
    write_all(registry_path, [e for e in read_all(registry_path) if e["id"] != sid])
