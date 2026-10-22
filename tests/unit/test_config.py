"""
The experiment config: the baseline and biological configs load, an unknown key or a label as an input is refused, and the resolved dict round trips.
"""

import json

import pytest
import yaml
from pydantic import ValidationError

from axis_of_travel_rnn.analysis import load_thresholds
from axis_of_travel_rnn.config import ExperimentConfig, InputsConfig, load_config, resolved
from axis_of_travel_rnn.dataset import layout
from proj_helpers.paths import configs_dir

BASELINE = configs_dir() / "experiments" / "baseline.yaml"
BIOLOGICAL = configs_dir() / "experiments" / "biological.yaml"


def test_the_baseline_loads_with_position_only_inputs():
    config = load_config(BASELINE)
    assert config.inputs.columns == ("x", "y") and config.data.blueprint == "blocks_v1"
    assert config.analysis.thresholds == "analysis.thresholds" and "min_unit_fraction" in load_thresholds(config.analysis.thresholds)


@pytest.mark.parametrize("change", [
    lambda raw: raw.update(extra=1),
    lambda raw: raw["windows"].update(window=400),
    lambda raw: raw["data"].update(split=[0.5, 0.5, 0.5]),
])
def test_an_unknown_key_or_a_refused_value_fails(tmp_path, change):
    raw = yaml.safe_load(BASELINE.read_text())
    change(raw)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValidationError):
        load_config(path)


def test_the_biological_config_adds_heading_and_turn_rate_and_changes_nothing_else():
    baseline, biological = load_config(BASELINE), load_config(BIOLOGICAL)
    assert biological.inputs.columns == ("x", "y", "speed", "heading", "turn_rate")
    assert len(layout(baseline.inputs.columns)) == 2 and len(layout(biological.inputs.columns)) == 6  # heading is two inputs
    assert resolved(baseline) | {"inputs": None} == resolved(biological) | {"inputs": None}


@pytest.mark.parametrize("column", ["phase", "trip", "run", "path_id", "clean"])
def test_a_label_is_refused_as_an_input(column):
    with pytest.raises(ValidationError, match=column):
        InputsConfig(columns=("x", "y", column))


def test_resolved_is_plain_json_and_round_trips():
    config = load_config(BASELINE)
    plain = resolved(config)
    assert json.loads(json.dumps(plain)) == plain
    assert ExperimentConfig.model_validate(plain) == config
