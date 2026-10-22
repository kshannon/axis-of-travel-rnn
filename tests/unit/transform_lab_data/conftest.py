"""
Fixtures for the converter tests: a lab root holding the synthetic session in both formats, a config.
"""

import pytest

import axis_of_travel_rnn.config
import transform_lab_data.__main__ as entry

from .synthetic_mat import example_session, session_names, write_session


@pytest.fixture(autouse=True)
def no_local_config(monkeypatch):
    """
    Make reading configs/local.yaml an error, so every test passes its own config.
    """
    def refuse(*args, **kwargs):
        raise AssertionError("a test read configs/local.yaml; pass config instead")
    monkeypatch.setattr(axis_of_travel_rnn.config, "local_config", refuse)
    monkeypatch.setattr(entry, "local_config", refuse)


@pytest.fixture
def lab_root(tmp_path):
    """
    Two groups with one session each, classic with a tag in NS14Data and v7.3 in JL1HPCData.
    """
    root = tmp_path / "lab"
    names = session_names("NS14", 27, "021915", "001", tag="bilatmusc")
    write_session(root / "NS14Data", example_session("bilatmusc"), names, "classic")
    write_session(root / "JL1HPCData", example_session(), session_names("JL1", 23, "071514", "001"), "v7.3")
    return root


@pytest.fixture
def config(tmp_path, lab_root):
    """
    Both converter keys, the lab data root and an output root next to it under tmp_path.
    """
    return {"LAB_DATA": str(lab_root), "TRANSFORMED_LAB_DATA": str(tmp_path / "transformed")}
