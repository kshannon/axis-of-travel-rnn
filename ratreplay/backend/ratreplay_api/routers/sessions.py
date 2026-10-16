"""
The sessions of a transformed source: the index, one session's facts and its arrays.
"""

from fastapi import APIRouter, Depends, Response

from .. import arrow
from ..managers import sessions
from .deps import transformed_source

router = APIRouter(prefix="/api/sources/{sid}/sessions")


@router.get("")
def session_index(source=Depends(transformed_source)):
    """
    One row per session.
    """
    return sessions.index(source)


@router.get("/{session_id}")
def session_header(session_id: str, source=Depends(transformed_source)):
    """
    A session's epochs, runs, cut points, heading fills, LED offset, occupancy and automatic blocks as json.
    """
    return sessions.header(source, session_id)


@router.get("/{session_id}/arrays")
def session_arrays(session_id: str, source=Depends(transformed_source)):
    """
    A session's arrays over every frame as an Arrow IPC stream.
    """
    return Response(arrow.encode(sessions.arrays(source, session_id)), media_type=arrow.MEDIA_TYPE)
