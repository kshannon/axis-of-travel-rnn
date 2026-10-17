"""
The window settings file.
"""

from fastapi import APIRouter, Depends

from ..managers import windows
from ..schemas import SettingsBody
from .deps import data_sources

router = APIRouter(prefix="/api/windows/settings")


@router.get("")
def get_settings(sources=Depends(data_sources)):
    """
    The saved window settings or the defaults.
    """
    return windows.get(sources)


@router.put("")
def put_settings(body: SettingsBody, sources=Depends(data_sources)):
    """
    Write the settings file with the totals over the processed folder's blocks and return it with whether it replaced one.
    """
    return windows.put(sources, body.settings.model_dump())
