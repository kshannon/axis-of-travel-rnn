"""
The HTTP face of ReviewManager: the sessions index, a session for the replay, a preview of edits, saving blocks and rebuilding every session.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..schemas import EditsBody, ReviewBody, SettingsBody, WindowSettings
from ..utilities import arrow
from .deps import review_manager

router = APIRouter(prefix="/api")
SettingsQuery = Annotated[WindowSettings, Query()]


@router.get("/sessions")
def session_index(manager=Depends(review_manager)):
    """
    One row per session with an arena or track epoch, with the funnel and the facts of its review.
    """
    return manager.index()


@router.get("/sessions/{session_id}")
def session_header(session_id: str, settings: SettingsQuery, manager=Depends(review_manager)):
    """
    A session's facts, epochs, runs, cut points, spans, occupancy, review and blocks with their window counts at the settings in the query.
    """
    return manager.load(session_id, settings.model_dump())


@router.get("/sessions/{session_id}/arrays", response_class=arrow.ArrowResponse)
def session_arrays(session_id: str, manager=Depends(review_manager)):
    """
    A session's arrays over every frame, in metres, as an Arrow IPC stream.
    """
    return arrow.ArrowResponse(arrow.encode(manager.arrays(session_id)))


@router.post("/sessions/{session_id}/preview")
def preview_edits(session_id: str, body: EditsBody, manager=Depends(review_manager)):
    """
    The blocks the edits make with their window counts, the edits refused, the cuts and the flagged runs, nothing written.
    """
    return manager.preview(session_id, [edit.model_dump() for edit in body.edits], body.settings.model_dump())


@router.put("/sessions/{session_id}/blocks")
def save_blocks(session_id: str, body: ReviewBody, manager=Depends(review_manager)):
    """
    Apply the edits, write the review whole and build the session's blocks, returning the review, whether it replaced one and the build's outcome.
    """
    return manager.save_blocks(session_id, [edit.model_dump() for edit in body.edits], body.notes, body.settings.model_dump())


@router.post("/rebuild")
def rebuild_all(body: SettingsBody, manager=Depends(review_manager)):
    """
    Build the blocks of every reviewed session again at the settings, returning each session's outcome and the totals.
    """
    return manager.rebuild_all(body.settings.model_dump())
