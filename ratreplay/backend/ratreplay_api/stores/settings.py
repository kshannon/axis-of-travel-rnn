"""
The window settings file the training pipeline reads (configs/datasets/lab_blocks.yaml), written whole.
"""

from pathlib import Path

from axis_of_travel_rnn import windows


def read(path):
    """
    The settings file as a dict, or None when it was not written yet.
    """
    return windows.read_settings(path) if Path(path).is_file() else None


def write(path, settings, manifest, totals):
    """
    Write the settings with the processed manifest's facts and the totals at the settings, and return whether a file was replaced.
    """
    replaced = Path(path).is_file()
    windows.write_settings(settings, manifest, totals, path)
    return replaced
