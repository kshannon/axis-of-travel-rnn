"""
The attached sources: list, attach, detach.
"""

from fastapi import APIRouter, Depends

from ..managers import sources
from ..schemas import AttachBody
from .deps import registry_path

router = APIRouter(prefix="/api/sources")


@router.get("")
def list_sources(path=Depends(registry_path)):
    """
    Every attached source with its status, counts and manifests.
    """
    return sources.list_all(path)


@router.post("")
def attach_source(body: AttachBody, path=Depends(registry_path)):
    """
    Attach a folder after checking it against the data format.
    """
    return sources.attach(path, body.kind, body.path, body.processed_path)


@router.delete("/{sid}")
def detach_source(sid: str, path=Depends(registry_path)):
    """
    Detach a source, its data stays.
    """
    sources.detach(path, sid)
    return {"detached": sid}
