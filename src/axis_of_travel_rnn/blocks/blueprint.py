"""
A blueprint: the entry of configs/project.yaml that says which blocks a build makes, read into a model that refuses an unknown key.
"""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from ..config import section
from . import RULES, SETTINGS

# Blueprints live in the blueprints section of configs/project.yaml, keyed by name.
SECTION = "blueprints"
ALL_REVIEWED = "all_reviewed"
FROM_REVIEWS = "from_reviews"


class Blueprint(BaseModel):
    """
    The blueprint's keys: its name and format version, the local.yaml key of the transformed folder, the reviews folder when not the default, the sessions, the rule and setting overrides, the start offsets, the data id a build must give and where the built folder is read from.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    format_version: int
    description: str = ""
    transformed: str
    reviews: str | None = None  # the reviews folder, none for PROCESSED_LAB_DATA/review where the review tool writes them
    sessions: list[str] | Literal["all_reviewed"]
    rules: dict = {}
    settings: dict = {}
    start_offsets: dict[str, float] | Literal["from_reviews"] = FROM_REVIEWS
    expected_data_id: str | None = None
    built: str | None = None  # the built folder relative to the repository, none for PROCESSED_LAB_DATA/<name>

    @field_validator("rules")
    @classmethod
    def known_rules(cls, value):
        """
        The rule overrides, refused when one names no rule.
        """
        unknown = sorted(set(value) - set(RULES))
        if unknown:
            raise ValueError(f"unknown rules {', '.join(unknown)}")
        return value

    @field_validator("settings")
    @classmethod
    def known_settings(cls, value):
        """
        The setting overrides, refused when one names no setting.
        """
        unknown = sorted(set(value) - set(SETTINGS))
        if unknown:
            raise ValueError(f"unknown settings {', '.join(unknown)}")
        return value

    def resolved_rules(self):
        """
        RULES with the overrides laid over them, a list given for a tuple rule kept as a tuple.
        """
        return {key: tuple(self.rules[key]) if key in self.rules and isinstance(RULES[key], tuple) else self.rules.get(key, RULES[key])
                for key in RULES}

    def resolved_settings(self):
        """
        SETTINGS with the overrides laid over them.
        """
        return {**SETTINGS, **self.settings}

    def start_offset(self, sid, review):
        """
        The start offset in metres the session is built with: the blueprint's for it when it lists one, else the review's, none meaning the environment yaml's.
        """
        if self.start_offsets != FROM_REVIEWS and sid in self.start_offsets:
            return self.start_offsets[sid]
        return review.get("start_offset_m")


def blueprint_section(name, project=None):
    """
    The blueprint's own section of the project config (or of the yaml at project) as a plain dict, a KeyError when there is none.
    """
    return section(f"{SECTION}.{name}", project)


def read_blueprint(name, project=None):
    """
    The named blueprint, a KeyError when the project config has none and a pydantic ValidationError when a key is unknown, missing or of the wrong type.
    """
    return Blueprint.model_validate(blueprint_section(name, project))


def blueprint_sha256(raw):
    """
    The sha256 of a blueprint's section in canonical json (sorted keys, no spaces), what the manifest records, so comments and key order in the yaml do not change it.
    """
    return hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
