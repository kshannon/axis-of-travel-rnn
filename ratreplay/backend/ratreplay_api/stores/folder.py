"""
Facts about a data folder as a whole.
"""

from ..clock import iso_of


def exists(sources, kind):
    """
    Whether the folder the config names for the kind exists.
    """
    return sources.root(kind).is_dir()


def modified(sources, kind):
    """
    When the newest file under the kind's folder was last written, none for a folder without files.
    """
    times = [path.stat().st_mtime for path in sources.root(kind).rglob("*") if path.is_file()]
    return iso_of(max(times)) if times else None
