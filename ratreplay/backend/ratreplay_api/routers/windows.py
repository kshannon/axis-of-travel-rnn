"""
The window settings file.
"""

from fastapi import APIRouter, Depends

from ..managers import windows
from ..schemas import SettingsBody
from .deps import registry_path, settings_path

router = APIRouter(prefix="/api/windows/settings")


@router.get("")
def get_settings(path=Depends(settings_path)):
    """
    The saved window settings or the defaults.
    """
    return windows.get(path)


@router.put("")
def put_settings(body: SettingsBody, path=Depends(settings_path), sources=Depends(registry_path)):
    """
    Write the settings file with the totals over the named source's blocks and return it with whether it replaced one.
    """
    return windows.put(path, sources, body.source, body.settings.model_dump())
