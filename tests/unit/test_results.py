"""
An experiment's record: save_results writes summary.json with its keys, metrics.csv and the figures.
"""

import csv
import json

from matplotlib.figure import Figure

from axis_of_travel_rnn import __version__, load_config, save_results
from axis_of_travel_rnn.config import REPO_ROOT

BASELINE = REPO_ROOT / "configs" / "experiments" / "baseline.yaml"
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

