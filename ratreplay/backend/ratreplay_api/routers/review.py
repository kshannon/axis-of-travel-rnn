"""
A session's review: read it, save it, preview the blocks of some edits.
"""

from fastapi import APIRouter, Depends

from ..managers import review
from ..schemas import EditsBody, ReviewBody
from .deps import transformed_source

router = APIRouter(prefix="/api/sources/{sid}/sessions/{session_id}/review")


@router.get("")
def get_review(session_id: str, source=Depends(transformed_source)):
    """
    The saved review, or null.
    """
    return review.get(source, session_id)


@router.put("")
def put_review(session_id: str, body: ReviewBody, source=Depends(transformed_source)):
    """
    Apply the edits, write the review whole and return it with the file and whether it replaced one.
    """
    return review.save(source, session_id, [edit.model_dump() for edit in body.edits], body.notes)


@router.post("/preview")
def preview_review(session_id: str, body: EditsBody, source=Depends(transformed_source)):
    """
    The blocks, cuts and flagged runs the edits make and the edits skipped, nothing written.
    """
    return review.preview(source, session_id, [edit.model_dump() for edit in body.edits])
