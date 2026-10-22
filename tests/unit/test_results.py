"""
An experiment's record: save_results writes summary.json with its keys, metrics.csv and the figures, and new-experiment writes the template notebook with the title in place and a copy of the named config.
"""

import csv
import json
from datetime import date

import nbformat
from matplotlib.figure import Figure

from axis_of_travel_rnn import __version__, load_config, save_results
from proj_helpers.new import new_experiment
from proj_helpers.paths import configs_dir

BASELINE = configs_dir() / "experiments" / "baseline.yaml"
BIOLOGICAL = configs_dir() / "experiments" / "biological.yaml"
ROWS = [{"epoch": 1, "train_loss": 0.5, "val_loss": 0.6, "seconds": 1.0, "best": True},
        {"epoch": 2, "train_loss": 0.4, "val_loss": 0.7, "seconds": 1.0, "best": False}]
SUMMARY_KEYS = {"git_commit", "package_version", "blueprint", "data_id", "config", "pixi_lock_sha256", "started", "finished", "metrics"}


def test_save_results_writes_the_summary_the_metrics_and_the_figures(tmp_path):
    config = load_config(BASELINE)
    fig = Figure()
    fig.suptitle("A figure")
    save_results(tmp_path / "run", config, "abc", ROWS, {"test_loss": 0.1}, {"loss": fig}, "2026-10-21T10:00:00+00:00",
                 "2026-10-21T10:05:00+00:00")
    summary = json.loads((tmp_path / "run" / "summary.json").read_text())
    assert set(summary) == SUMMARY_KEYS
    assert summary["blueprint"] == "blocks_v1" and summary["data_id"] == "abc" and summary["package_version"] == __version__
    assert summary["config"]["model"]["hidden_size"] == config.model.hidden_size and summary["metrics"] == {"test_loss": 0.1}
    assert len(summary["git_commit"]) == 40 and len(summary["pixi_lock_sha256"]) == 64
    with open(tmp_path / "run" / "metrics.csv") as file:
        assert [row["epoch"] for row in csv.DictReader(file)] == ["1", "2"]
    assert (tmp_path / "run" / "figures" / "loss.png").is_file()


def test_new_experiment_writes_the_template_with_the_title_in_place_and_copies_the_config(tmp_path):
    folder = new_experiment("Window 60 s", directory=tmp_path, author="kyle", today=date(2026, 10, 22))
    assert folder == tmp_path / "2026-10-22_window-60-s"
    assert sorted(path.name for path in folder.iterdir()) == ["config.yaml", "notebook.ipynb"]
    assert load_config(folder / "config.yaml") == load_config(BASELINE)
    other = new_experiment("Biological", "biological", directory=tmp_path, author="kyle", today=date(2026, 10, 22))
    assert load_config(other / "config.yaml") == load_config(BIOLOGICAL)
    notebook = nbformat.read(folder / "notebook.ipynb", as_version=4)
    assert notebook.cells[0].source.startswith("# Window 60 s\n") and "{{" not in notebook.cells[0].source
    assert any("parameters" in cell.metadata.get("tags", []) for cell in notebook.cells)
