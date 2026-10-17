"""
The window settings the training pipeline reads: the saved file or the defaults, and saving the settings with the totals they give over a processed dataset.
"""

from ..engines import windows
from ..stores import processed
from ..stores import settings as settings_file


def get(settings_path):
    """
    The settings in force, the saved ones or the project's defaults, with the saved file's content when there is one.
    """
    saved = settings_file.read(settings_path)
    return {"settings": saved["settings"] if saved else windows.DEFAULTS, "saved": saved, "path": str(settings_path)}


def put(settings_path, root, settings):
    """
    Write the settings file with the processed manifest's facts and the totals over the blocks under root at the settings, replacing the earlier one. Returns what get does and whether it replaced one.
    """
    rows, shares = processed.blocks_with_shares(root)
    replaced = settings_file.write(settings_path, settings, processed.read_manifest(root), windows.summarize(rows, shares, settings))
    return {**get(settings_path), "overwrote": replaced}
