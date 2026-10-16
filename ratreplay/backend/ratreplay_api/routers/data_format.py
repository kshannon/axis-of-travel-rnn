"""
GET /api/format, the data format contract.
"""

from fastapi import APIRouter

from .. import contract

router = APIRouter()


@router.get("/api/format")
def get_format():
    """
    The files, columns and types a folder must have to be attached, the review file and the window settings.
    """
    return contract.build()
