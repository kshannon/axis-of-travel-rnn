"""
The HTTP face of ValidationManager: folder health, the data format, the environments with their registrations, readiness, a built block with its arrays and windows, and the window settings selected for export.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..schemas import ReadinessQuery, SettingsBody, WindowSettings
from ..utilities import arrow
from .deps import config_path, reread_validation_manager, validation_manager

router = APIRouter(prefix="/api")
SettingsQuery = Annotated[WindowSettings, Query()]


@router.get("/health")
def get_health(manager=Depends(reread_validation_manager), config=Depends(config_path)):
    """
    The three folders each with its root, problems, counts and times, and the config file they come from. reload=true reads that file again first.
    """
    return manager.health(config)


@router.get("/format")
def get_format(manager=Depends(validation_manager)):
    """
    The files, columns and types each access declares and the default window settings.
    """
    return manager.format()


@router.get("/environments")
def get_environments(manager=Depends(validation_manager)):
    """
    Every environment with its kind, yaml parameters and geometry, and the built sessions registered against it with the registration each was given and a summary.
    """
    return manager.environments()


@router.get("/blocks")
def readiness(query: Annotated[ReadinessQuery, Query()], manager=Depends(validation_manager)):
    """
    Every built block of the dataset named by which (real for now) with its window count and verdict at the settings in the query, the totals and the settings each session was built with.
    """
    return manager.readiness(query.which, query.model_dump(exclude={"which"}))


@router.get("/blocks/{block_id}")
def block_header(block_id: str, manager=Depends(validation_manager)):
    """
    A built block's row, the geometry of its environment and the spans of its runs, trips, phases and heading fills.
    """
    return manager.block(block_id)


@router.get("/blocks/{block_id}/arrays", response_class=arrow.ArrowResponse)
def block_arrays(block_id: str, manager=Depends(validation_manager)):
    """
    A built block's arrays over its frames, in metres, as an Arrow IPC stream.
    """
    return arrow.ArrowResponse(arrow.encode(manager.arrays(block_id)))


@router.get("/blocks/{block_id}/windows")
def block_windows(block_id: str, settings: SettingsQuery, manager=Depends(validation_manager)):
    """
    The window rows of a built block at the settings in the query with their checks, the verdict of the block and its window count.
    """
    return manager.windows(block_id, settings.model_dump())


@router.get("/windows")
def get_selected(manager=Depends(validation_manager)):
    """
    The window settings selected for export with their totals, when and by whom, or null.
    """
    return manager.selected()


@router.put("/windows")
def select_settings(body: SettingsBody, manager=Depends(validation_manager)):
    """
    Select the settings for export: write windows.json whole with the totals they give, returning the file and whether it replaced a selection.
    """
    return manager.select_settings(body.settings.model_dump())
