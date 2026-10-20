"""
The request bodies and the query of the API, validated before a manager sees them.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, create_model, model_validator

from .access.processed import EDIT_FIELDS
from .engines.trajectory import SETTINGS


class WindowSettings(BaseModel):
    """
    The training window settings, the engine's defaults where a field is left out, a key it does not know refused.
    """

    model_config = ConfigDict(extra="forbid")

    window_s: float = Field(SETTINGS["window_s"], gt=0)
    stride_s: float = Field(SETTINGS["stride_s"], gt=0)
    burn_in_s: float = Field(SETTINGS["burn_in_s"], ge=0)
    horizon_s: float = Field(SETTINGS["horizon_s"], ge=0)
    rate_hz: int = Field(SETTINGS["rate_hz"], gt=0)
    min_heading_measured: float = Field(SETTINGS["min_heading_measured"], ge=0, le=1)
    min_complete_trips: int = Field(SETTINGS["min_complete_trips"], ge=0)


# The start offset in metres the person tuned for a session, none for the yaml's. In a query, absent means the review's applies.
StartOffset = Annotated[float | None, Field(allow_inf_nan=False)]


class SessionQuery(WindowSettings):
    """
    The query of a session's header: the window settings and the start offset. A query model must be the only query parameter, so the offset is a field of it.
    """

    start_offset_m: StartOffset = None


class ReadinessQuery(WindowSettings):
    """
    The query of readiness: the window settings and the dataset they are tried on, real or a synthetic set. A query model must be the only query parameter, so which is a field of it.
    """

    which: str = "real"


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
    The model of one op: exactly the fields EDIT_FIELDS lists for it, each typed, and a range in order.
    """
    types = {field: (FIELD_TYPES.get(field, COUNT), ...) for field in fields}
    checks = {"range_in_order": model_validator(mode="after")(starts_before_it_ends)} if "frame_start" in fields else {}
    return create_model(f"{op.capitalize()}Edit", __config__=ConfigDict(extra="forbid"), __validators__=checks,
                        op=(Literal[op], ...), **types)


Edit = Annotated[Union[tuple(edit_model(op, fields) for op, fields in EDIT_FIELDS.items())], Field(discriminator="op")]


class EditsBody(BaseModel):
    """
    The edits of a review, in the order they were made, the window settings the blocks they make are counted at and the start offset the session is registered with, always given: null is the yaml's and saving it clears a saved value.
    """

    edits: list[Edit]
    settings: WindowSettings = Field(default_factory=WindowSettings)
    start_offset_m: StartOffset


class ReviewBody(EditsBody):
    """
    The edits, the free text note and the window settings of a session's save.
    """

    notes: str = ""


class ExclusionBody(BaseModel):
    """
    The person's exclusion of a session or taking it back, with a note that is appended to the review's notes when it is not empty and the window settings the empty build of an exclusion records.
    """

    model_config = ConfigDict(extra="forbid")

    excluded: StrictBool
    note: str = ""
    settings: WindowSettings = Field(default_factory=WindowSettings)


# The epoch kinds a synthetic set is generated for and the sides of a quiz pair.
Kind = Literal["arena", "track"]
Side = Literal["left", "right"]


class GenerateBody(BaseModel):
    """
    What a synthetic set is generated from and how: the source sessions whose built blocks give the recipe, the seed, the seconds to generate per epoch kind and the window settings recorded in its provenance.
    """

    model_config = ConfigDict(extra="forbid")

    sources: list[str] = Field(min_length=1)
    seed: int = Field(strict=True, ge=0)
    length_s: dict[Kind, Annotated[float, Field(gt=0, allow_inf_nan=False)]] = Field(min_length=1)
    settings: WindowSettings = Field(default_factory=WindowSettings)


class PairBody(BaseModel):
    """
    The kind of the blocks a quiz pair shows, null for any kind the set has.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Kind | None = None


class GuessBody(BaseModel):
    """
    The person's answer on a quiz pair: which side they call real.
    """

    model_config = ConfigDict(extra="forbid")

    pair_id: str
    side: Side
