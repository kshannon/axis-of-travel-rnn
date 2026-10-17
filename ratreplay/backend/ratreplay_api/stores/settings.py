"""
The window settings file the training pipeline reads (configs/datasets/lab_blocks.yaml), written whole.
"""

from axis_of_travel_rnn import windows


def path_of(sources):
    """
    The settings file.
    """
    return sources.settings_path


def read(sources):
    """
    The settings file as a dict, or None when it was not written yet.
    """
    path = path_of(sources)
    return windows.read_settings(path) if path.is_file() else None


def write(sources, settings, manifest, totals):
    """
    Write the settings with the processed manifest's facts and the totals at the settings, and return whether a file was replaced.
    """
    path = path_of(sources)
    replaced = path.is_file()
    windows.write_settings(settings, manifest, totals, path)
    return replaced
