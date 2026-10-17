"""
A session's review: read it, save it, preview the blocks of some edits.
"""

from fastapi import APIRouter, Depends

from ..managers import review
from ..schemas import EditsBody, ReviewBody
from .deps import data_sources

router = APIRouter(prefix="/api/sessions/{session_id}/review")


@router.get("")
def get_review(session_id: str, sources=Depends(data_sources)):
    """
    The saved review, or null.
    """
    return review.get(sources, session_id)


@router.put("")
def put_review(session_id: str, body: ReviewBody, sources=Depends(data_sources)):
    """
    Apply the edits, write the review whole and return it with the file and whether it replaced one.
    """
    return review.save(sources, session_id, [edit.model_dump() for edit in body.edits], body.notes)


@router.post("/preview")
def preview_review(session_id: str, body: EditsBody, sources=Depends(data_sources)):
    """
    The blocks, cuts and flagged runs the edits make and the edits skipped, nothing written.
    """
    return review.preview(sources, session_id, [edit.model_dump() for edit in body.edits])
