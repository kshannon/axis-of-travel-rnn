"""
Facts about a data folder as a whole.
"""

from pathlib import Path

from ..clock import iso_of


def exists(root):
    """
    Whether the folder exists.
    """
    return Path(root).is_dir()


def modified(root):
    """
    When the newest file under the folder was last written, none for a folder without files.
    """
    times = [path.stat().st_mtime for path in Path(root).rglob("*") if path.is_file()]
    return iso_of(max(times)) if times else None
