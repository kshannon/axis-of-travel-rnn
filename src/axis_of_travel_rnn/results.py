"""
An experiment's record written into its folder: summary.json, metrics.csv and the figures as png.
"""

import csv
import hashlib
import json
import subprocess
from pathlib import Path

from proj_helpers.paths import repo_root

from . import __version__
from .config import resolved

SUMMARY = "summary.json"
METRICS = "metrics.csv"
FIGURES_DIR = "figures"
FIGURE_DPI = 150
LOCK_FILE = "pixi.lock"
UNKNOWN = "unknown"


def git_commit():
    """
    The full commit of the repository's HEAD, unknown when git cannot say.
    """
    done = subprocess.run(["git", "-C", str(repo_root()), "rev-parse", "HEAD"], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else UNKNOWN


def lock_sha256():
    """
    The sha256 of the repository's pixi.lock as hex.
    """
    return hashlib.sha256((repo_root() / LOCK_FILE).read_bytes()).hexdigest()


def json_value(value):
    """
    A numpy value or array as plain python, for json.
    """
    return value.tolist()


def save_results(results_dir, config, data_id, metrics_rows, summary, figures, started, finished):
    """
    Write summary.json (commit, version, blueprint, data id, resolved config, pixi.lock sha256, times, summary metrics), metrics.csv (a row per epoch) and figures/<name>.png into the folder, and return it.
    """
    folder = Path(results_dir)
    (folder / FIGURES_DIR).mkdir(parents=True, exist_ok=True)
    record = {"git_commit": git_commit(), "package_version": __version__, "blueprint": config.data.blueprint, "data_id": data_id,
              "config": resolved(config), "pixi_lock_sha256": lock_sha256(), "started": started, "finished": finished,
              "metrics": summary}
    (folder / SUMMARY).write_text(json.dumps(record, indent=2, default=json_value) + "\n")
    with open(folder / METRICS, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(metrics_rows[0]))
        writer.writeheader()
        writer.writerows(metrics_rows)
    for name, fig in figures.items():
        fig.savefig(folder / FIGURES_DIR / f"{name}.png", dpi=FIGURE_DPI)
    return folder
