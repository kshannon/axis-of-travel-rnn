"""
The sessions of the transformed folder: the index, one session's facts and its arrays.
"""

from fastapi import APIRouter, Depends

from .. import arrow
from ..managers import sessions
from .deps import processed_root, transformed_root

router = APIRouter(prefix="/api/sessions")


@router.get("")
def session_index(root=Depends(transformed_root), reviews=Depends(processed_root)):
    """
    One row per session, with the facts of its review under the processed folder.
    """
    return sessions.index(root, reviews)


@router.get("/{session_id}")
def session_header(session_id: str, root=Depends(transformed_root)):
    """
    A session's epochs, runs, cut points, heading fills, LED offset, occupancy and automatic blocks as json.
    """
    return sessions.header(root, session_id)


@router.get("/{session_id}/arrays", response_class=arrow.ArrowResponse)
def session_arrays(session_id: str, root=Depends(transformed_root)):
    """
    A session's arrays over every frame as an Arrow IPC stream.
    """
    return arrow.ArrowResponse(arrow.encode(sessions.arrays(root, session_id)))
