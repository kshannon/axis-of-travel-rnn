"""
An experiment's configuration: one yaml file read into a pydantic model that refuses an unknown key, and its plain dict for recording.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from .analysis import MEASURES
from .dataset import ALLOWED_INPUTS, DEFAULT_INPUTS
from .models import KINDS

SPLIT_TOLERANCE = 1e-9  # the split fractions must sum to 1 within this


class Section(BaseModel):
    """
    A section of the config: unknown keys refused, values frozen.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class DataConfig(Section):
    """
    The built folder by blueprint name, the training rate, the train, validation and test fractions of recording dates, and the split's seed.
    """

    blueprint: str
    rate_hz: int
    split: tuple[float, float, float]
    seed: int

    @field_validator("split")
    @classmethod
    def sums_to_one(cls, value):
        """
        The fractions, refused unless they sum to 1.
        """
        if abs(sum(value) - 1) > SPLIT_TOLERANCE:
            raise ValueError(f"split fractions {value} do not sum to 1")
        return value


class WindowsConfig(Section):
    """
    The window settings of blocks.SETTINGS but rate_hz, which is the data section's training rate.
    """

    window_s: float
    stride_s: float
    burn_in_s: float
    horizon_s: float
    min_heading_measured: float
    min_complete_trips: int


class InputsConfig(Section):
    """
    The block columns the network is given, position only by default, heading being given as two inputs, its sine and cosine (heading_sin and heading_cos).
    """

    columns: tuple[str, ...] = DEFAULT_INPUTS

    @field_validator("columns")
    @classmethod
    def allowed(cls, value):
        """
        The columns, refused when one is not an allowed input.
        """
        refused = sorted(set(value) - set(ALLOWED_INPUTS))
        if refused:
            raise ValueError(f"inputs {', '.join(refused)} are not allowed, only {', '.join(ALLOWED_INPUTS)}")
        return value


class ModelConfig(Section):
    """
    The network's kind and hidden size.
    """

    kind: Literal[KINDS]
    hidden_size: int


class TrainingConfig(Section):
    """
    The most epochs, the batch size, the learning rate, the epochs without a better validation loss before stopping, and the torch device.
    """

    epochs: int
    batch_size: int
    learning_rate: float
    patience: int
    device: str = "cpu"


class AnalysisConfig(Section):
    """
    The thresholds yaml, relative to the repository, and the measures to run.
    """

    thresholds: str
    measures: tuple[Literal[MEASURES], ...] = MEASURES


class ExperimentConfig(Section):
    """
    One experiment: data, windows, inputs, model, training, analysis and the seed of the weights, the batches and the nulls.
    """

    data: DataConfig
    windows: WindowsConfig
    inputs: InputsConfig = InputsConfig()
    model: ModelConfig
    training: TrainingConfig
    analysis: AnalysisConfig
    seed: int


def load_config(path):
    """
    The experiment config in the yaml file, a pydantic ValidationError when a key is unknown, missing or of the wrong type.
    """
    return ExperimentConfig.model_validate(yaml.safe_load(Path(path).read_text()))


def resolved(config):
    """
    The config with every default filled in as a plain dict of json values, for recording.
    """
    return config.model_dump(mode="json")
