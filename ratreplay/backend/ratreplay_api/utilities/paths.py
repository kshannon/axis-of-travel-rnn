"""
Facts about folders and path text, with no knowledge of which folders exist.
"""

from pathlib import Path

from .clock import iso_of


def newest_mtime(root):
    """
    When the newest file under the folder was last written, none for a folder without files.
    """
    times = [path.stat().st_mtime for path in root.rglob("*") if path.is_file()]
    return iso_of(max(times)) if times else None


def resolved(value):
    """
    The path a string names, with ~ expanded and links resolved.
    """
    return Path(str(value)).expanduser().resolve()
