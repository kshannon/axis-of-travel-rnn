"""
The window settings the training pipeline reads: the saved file or the defaults, and saving the settings with the totals they give over a processed dataset.
"""

from ..engines import windows
from ..stores import processed
from ..stores import settings as settings_file


def get(sources):
    """
    The settings in force, the saved ones or the project's defaults, with the saved file's content when there is one.
    """
    saved = settings_file.read(sources)
    return {"settings": saved["settings"] if saved else windows.DEFAULTS, "saved": saved, "path": str(settings_file.path_of(sources))}


def put(sources, settings):
    """
    Write the settings file with the processed manifest's facts and the totals over the processed folder's blocks at the settings, replacing the earlier one. Returns what get does and whether it replaced one.
    """
    rows, shares = processed.blocks_with_shares(sources)
    replaced = settings_file.write(sources, settings, processed.read_manifest(sources), windows.summarize(rows, shares, settings))
    return {**get(sources), "overwrote": replaced}
