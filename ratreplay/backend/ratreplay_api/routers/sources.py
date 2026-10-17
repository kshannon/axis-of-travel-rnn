"""
The data folders the config names.
"""

from fastapi import APIRouter, Depends

from ..managers import sources
from .deps import reread_sources

router = APIRouter(prefix="/api/sources")


@router.get("")
def get_sources(data=Depends(reread_sources)):
    """
    The transformed and processed folders each with its status, counts and manifest, and the config file they come from. reload=true reads that file again first.
    """
    return sources.status(data)
