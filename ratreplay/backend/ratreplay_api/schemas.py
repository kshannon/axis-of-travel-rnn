"""
The request bodies and the query of the API, validated before a manager sees them.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from .contract import EDIT_FIELDS
from .engines.trajectory import SETTINGS


class WindowSettings(BaseModel):
    """
    The training window settings, the engine's defaults where a field is left out.
    """

    window_s: float = Field(SETTINGS["window_s"], gt=0)
    stride_s: float = Field(SETTINGS["stride_s"], gt=0)
    burn_in_s: float = Field(SETTINGS["burn_in_s"], ge=0)
    horizon_s: float = Field(SETTINGS["horizon_s"], ge=0)
    rate_hz: int = Field(SETTINGS["rate_hz"], gt=0)
    min_heading_measured: float = Field(SETTINGS["min_heading_measured"], ge=0, le=1)
    min_complete_trips: int = Field(SETTINGS["min_complete_trips"], ge=0)


class SettingsBody(BaseModel):
    """
    The window settings a request works at: the ones to save, or the ones a rebuild computes its window counts at.
    """

    settings: WindowSettings


# Frames and runs are whole numbers counted from 1. Strict, so 2700.5 or true are refused instead of reaching the edits.
COUNT = Annotated[int, Field(strict=True, ge=1)]
FIELD_TYPES = {"edge": Literal["start", "end"]}


def starts_before_it_ends(edit):
    """
    A range of frames ends at or after its start, since a cut over an inverted range would leave overlapping blocks.
    """
    if edit.frame_start > edit.frame_end:
        raise ValueError("the range ends before it starts")
    return edit


def edit_model(op, fields):
    """
    The model of one op: exactly the fields the contract lists for it, each typed, and a range in order.
    """
    types = {field: (FIELD_TYPES.get(field, COUNT), ...) for field in fields}
    checks = {"range_in_order": model_validator(mode="after")(starts_before_it_ends)} if "frame_start" in fields else {}
    return create_model(f"{op.capitalize()}Edit", __config__=ConfigDict(extra="forbid"), __validators__=checks,
                        op=(Literal[op], ...), **types)


Edit = Annotated[Union[tuple(edit_model(op, fields) for op, fields in EDIT_FIELDS.items())], Field(discriminator="op")]


class EditsBody(BaseModel):
    """
    The edits of a review, in the order they were made, and the window settings the blocks they make are counted at.
    """

    edits: list[Edit]
    settings: WindowSettings = Field(default_factory=WindowSettings)


class ReviewBody(EditsBody):
    """
    The edits, the free text note and the window settings of a session's save.
    """

    notes: str = ""
