"""
The drift guard: the committed sample is the build its blueprint names, is found with no configs/local.yaml, and the template notebook runs on it headless (about 10 s).
"""

import json

import papermill

import axis_of_travel_rnn.blocks.__main__ as entry
from axis_of_travel_rnn import data
from axis_of_travel_rnn.blocks.blueprint import read_blueprint
from axis_of_travel_rnn.config import REPO_ROOT

SAMPLE = read_blueprint("sample")
TEMPLATE = REPO_ROOT / "templates" / "notebook-experiment.ipynb"
CONFIG = REPO_ROOT / "configs" / "experiments" / "smoke.yaml"


def test_the_sample_is_found_without_local_config_and_has_the_blueprints_data_id():
    folder = data.built_folder("sample", config={})
    assert folder == REPO_ROOT / "tests" / "fixtures" / "sample"
    assert data.data_id(folder) == entry.data_id(folder) == SAMPLE.expected_data_id  # the manifest's id is the files'


def test_the_template_notebook_runs_on_the_sample_and_writes_its_summary(tmp_path):
    papermill.execute_notebook(TEMPLATE, tmp_path / "notebook.ipynb", cwd=tmp_path, progress_bar=False,
                               parameters={"config_path": str(CONFIG), "results_dir": str(tmp_path)})
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["blueprint"] == "sample" and summary["data_id"] == SAMPLE.expected_data_id
    assert (tmp_path / "metrics.csv").is_file() and (tmp_path / "figures" / "loss.png").is_file()
