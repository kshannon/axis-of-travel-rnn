"""
Timestamps as the files and the API write them: ISO 8601 in UTC to the second.
"""

from datetime import datetime, timezone


def iso_now():
    """
    The current time.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso_of(seconds):
    """
    A file's modification time in seconds since the epoch.
    """
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="seconds")
