"""
The data folders the config names.
"""

from fastapi import APIRouter, Depends

from ..managers import sources
from .deps import config_path, reread_config

router = APIRouter(prefix="/api/sources")


@router.get("")
def get_sources(config=Depends(reread_config), file=Depends(config_path)):
    """
    The transformed and processed folders each with its status, counts and manifest, and the config file they come from. reload=true reads that file again first.
    """
    return sources.describe_all(config, file)
