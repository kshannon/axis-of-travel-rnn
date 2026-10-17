"""
The processed dataset's blocks: the index with verdicts, one block's facts and its arrays.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .. import arrow
from ..managers import blocks
from ..schemas import WindowSettings
from .deps import data_sources

router = APIRouter(prefix="/api/blocks")


@router.get("")
def block_index(settings: Annotated[WindowSettings, Query()], sources=Depends(data_sources)):
    """
    Every block with its verdict at the window settings in the query, and the totals.
    """
    return blocks.index(sources, settings.model_dump())


@router.get("/{block_id}")
def block_header(block_id: str, settings: Annotated[WindowSettings, Query()], sources=Depends(data_sources)):
    """
    A block's environment geometry, runs, trips, phases, verdict and windows at the settings as json.
    """
    return blocks.header(sources, block_id, settings.model_dump())


@router.get("/{block_id}/arrays", response_class=arrow.ArrowResponse)
def block_arrays(block_id: str, sources=Depends(data_sources)):
    """
    A block's arrays over its frames as an Arrow IPC stream.
    """
    return arrow.ArrowResponse(arrow.encode(blocks.arrays(sources, block_id)))
