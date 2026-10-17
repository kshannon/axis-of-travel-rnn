"""
The sessions of the transformed folder: the index, one session's facts and its arrays.
"""

from fastapi import APIRouter, Depends

from .. import arrow
from ..managers import sessions
from .deps import data_sources

router = APIRouter(prefix="/api/sessions")


@router.get("")
def session_index(sources=Depends(data_sources)):
    """
    One row per session, with the facts of its review under the processed folder.
    """
    return sessions.index(sources)


@router.get("/{session_id}")
def session_header(session_id: str, sources=Depends(data_sources)):
    """
    A session's epochs, runs, cut points, heading fills, LED offset, occupancy and automatic blocks as json.
    """
    return sessions.header(sources, session_id)


@router.get("/{session_id}/arrays", response_class=arrow.ArrowResponse)
def session_arrays(session_id: str, sources=Depends(data_sources)):
    """
    A session's arrays over every frame as an Arrow IPC stream.
    """
    return arrow.ArrowResponse(arrow.encode(sessions.arrays(sources, session_id)))
