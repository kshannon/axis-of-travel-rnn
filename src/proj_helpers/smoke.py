"""
The drift guard, run as pixi run smoke: the template experiment notebook run headless by papermill on the committed sample.
"""

import json
import tempfile
import time
from pathlib import Path

from .paths import repo_root

TEMPLATE = "templates/experiment/notebook.ipynb"
CONFIG = "configs/experiments/smoke.yaml"
EXECUTED = "notebook.ipynb"
SUMMARY = "summary.json"


def run_smoke(results_dir):
    """
    Run the template notebook with the smoke config into the results folder and return its summary.json, FileNotFoundError when the run wrote none.
    """
    import papermill

    folder = Path(results_dir)
    folder.mkdir(parents=True, exist_ok=True)
    papermill.execute_notebook(repo_root() / TEMPLATE, folder / EXECUTED, cwd=folder, progress_bar=False,
                               parameters={"config_path": str(repo_root() / CONFIG), "results_dir": str(folder)})
    return json.loads((folder / SUMMARY).read_text())


def main():
    """
    Run the smoke into a temporary folder and print the data id and the wall time, a failing cell raising papermill's error.
    """
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_smoke(tmp)
    print(f"smoke: passed on {summary['blueprint']} data id {summary['data_id'][:12]} in {time.perf_counter() - start:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
