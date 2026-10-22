"""
The experiment config: the baseline loads with position only inputs, and an unknown key or a label as an input is refused.
"""

import pytest
import yaml
from pydantic import ValidationError

from axis_of_travel_rnn.config import REPO_ROOT, load_config

BASELINE = REPO_ROOT / "configs" / "experiments" / "baseline.yaml"


def test_the_baseline_loads_and_an_unknown_key_or_a_label_as_an_input_is_refused(tmp_path):
    config = load_config(BASELINE)
    assert config.inputs.columns == ("x", "y") and config.data.blueprint == "blocks_v1"
    for change in (lambda raw: raw.update(extra=1), lambda raw: raw["inputs"].update(columns=["x", "y", "phase"])):
        raw = yaml.safe_load(BASELINE.read_text())
        change(raw)
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(raw))
        with pytest.raises(ValidationError):
            load_config(path)
