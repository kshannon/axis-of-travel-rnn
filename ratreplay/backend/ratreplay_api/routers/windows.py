"""
The window settings file.
"""

from fastapi import APIRouter, Depends

from ..managers import windows
from ..schemas import SettingsBody
from .deps import processed_root, settings_path

router = APIRouter(prefix="/api/windows/settings")


@router.get("")
def get_settings(path=Depends(settings_path)):
    """
    The saved window settings or the defaults.
    """
    return windows.get(path)


@router.put("")
def put_settings(body: SettingsBody, path=Depends(settings_path), root=Depends(processed_root)):
    """
    Write the settings file with the totals over the processed folder's blocks and return it with whether it replaced one.
    """
    return windows.put(path, root, body.settings.model_dump())
