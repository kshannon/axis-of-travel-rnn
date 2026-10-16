"""
The request bodies and the query of the API, validated before a manager sees them.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from axis_of_travel_rnn.windows import DEFAULTS

from .contract import EDIT_FIELDS


class AttachBody(BaseModel):
    """
    A folder to attach, with the processed folder a transformed source is paired with.
    """

    path: str
    kind: Literal["transformed", "processed"]
    processed_path: str | None = None


class WindowSettings(BaseModel):
    """
    The training window settings, the project's defaults where a field is left out.
    """

    window_s: float = Field(DEFAULTS["window_s"], gt=0)
    stride_s: float = Field(DEFAULTS["stride_s"], gt=0)
    burn_in_s: float = Field(DEFAULTS["burn_in_s"], ge=0)
    horizon_s: float = Field(DEFAULTS["horizon_s"], ge=0)
    train_rate_hz: int = Field(DEFAULTS["train_rate_hz"], gt=0)
    min_heading_measured: float = Field(DEFAULTS["min_heading_measured"], ge=0, le=1)
    min_complete_trips: int = Field(DEFAULTS["min_complete_trips"], ge=0)


class SettingsBody(BaseModel):
    """
    The settings to save, with the processed source whose manifest and blocks the file records.
    """

    settings: WindowSettings
    source: str


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
    The edits of a review, in the order they were made.
    """

    edits: list[Edit]


class ReviewBody(EditsBody):
    """
    The edits and the free text note to save as a session's review.
    """

    notes: str = ""
