"""
New EDA notebooks, experiment folders and lab notes from templates/, run as pixi run new-eda, new-experiment and new-labnote.
"""

import argparse
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from .paths import repo_root

# The templates, where each kind is written, the experiment configs a folder copies from and the files of a folder.
EDA_TEMPLATE = "templates/notebook-eda.ipynb"
EXPERIMENT_TEMPLATE = "templates/notebook-experiment.ipynb"
LABNOTE_TEMPLATE = "templates/labnotebook.md"
EDA_DIR = "notebooks/eda"
EXPERIMENTS_DIR = "experiments"
LABNOTE_DIR = "labnotebook"
EXPERIMENT_CONFIGS = "configs/experiments"
DEFAULT_CONFIG = "baseline"
NOTEBOOK = "notebook.ipynb"
CONFIG = "config.yaml"
CONFIG_HEADER = "# This experiment's config, a copy of {} when the folder was made. Edit it before the run, never after.\n"


def slugify(text: str) -> str:
    """
    Lowercase, every run of other characters one dash, no outer dashes.
    """
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def git_user_name() -> str:
    """
    git's configured user.name, empty when git is missing or the name is unset.
    """
    try:
        done = subprocess.run(["git", "config", "user.name"], cwd=repo_root(), capture_output=True, text=True)
    except OSError:
        return ""
    return done.stdout.strip()


def fill(text, fields):
    """
    The text with every placeholder replaced by its value.
    """
    for placeholder, value in fields.items():
        text = text.replace(placeholder, value)
    return text


def write_notebook(template, path, fields):
    """
    Write the template notebook to path with the placeholders of every cell filled.
    """
    import nbformat

    notebook = nbformat.read(template, as_version=4)
    for cell in notebook.cells:
        cell.source = fill(cell.source, fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, path)


def slug_of(title, kind):
    """
    The title's slug, a ValueError when it has no letters or digits.
    """
    slug = slugify(title)
    if not slug:
        raise ValueError(f"{kind} title has no letters or digits")
    return slug


def new_eda(title, *, author=None, directory=None, template=None, today=None):
    """
    Write <directory>/<today>_<slug>.ipynb from the EDA template and return its path.
    """
    slug = slug_of(title, "notebook")
    directory = repo_root() / EDA_DIR if directory is None else Path(directory)
    template = repo_root() / EDA_TEMPLATE if template is None else Path(template)
    today = date.today() if today is None else today
    path = directory / f"{today.isoformat()}_{slug}.ipynb"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    write_notebook(template, path, {
        "{{DATE}}": today.isoformat(), "{{TITLE}}": title, "{{NAME}}": slug,
        "{{AUTHOR}}": git_user_name() if author is None else author,
        "{{CREATED}}": datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    return path


def new_experiment(title, config=DEFAULT_CONFIG, *, author=None, directory=None, template=None, today=None):
    """
    Make <directory>/<today>_<slug>/ with the experiment template's notebook and a copy of configs/experiments/<config>.yaml, and return the folder.
    """
    slug = slug_of(title, "experiment")
    source = repo_root() / EXPERIMENT_CONFIGS / f"{config}.yaml"
    if not source.is_file():
        raise ValueError(f"no experiment config {source}")
    directory = repo_root() / EXPERIMENTS_DIR if directory is None else Path(directory)
    template = repo_root() / EXPERIMENT_TEMPLATE if template is None else Path(template)
    today = date.today() if today is None else today
    folder = directory / f"{today.isoformat()}_{slug}"
    if folder.exists():
        raise FileExistsError(f"{folder} already exists")
    write_notebook(template, folder / NOTEBOOK, {
        "{{TITLE}}": title, "{{DATE}}": today.isoformat(), "{{AUTHOR}}": git_user_name() if author is None else author,
    })
    (folder / CONFIG).write_text(CONFIG_HEADER.format(f"{EXPERIMENT_CONFIGS}/{config}.yaml") + source.read_text())
    return folder


def new_labnote(words="", *, directory=None, template=None, now=None):
    """
    Write <directory>/<date>.md, or <date>__<slug>.md, from the lab note template and return its path.
    """
    directory = repo_root() / LABNOTE_DIR if directory is None else Path(directory)
    template = repo_root() / LABNOTE_TEMPLATE if template is None else Path(template)
    now = datetime.now().astimezone() if now is None else now
    day = now.date().isoformat()
    if words:
        slug = slugify(words)
        if not slug:
            raise ValueError("slug is empty after cleanup")
        path = directory / f"{day}__{slug}.md"
        title = slug.replace("-", " ")
    else:
        path = directory / f"{day}.md"
        title = day
    if path.exists():
        raise FileExistsError(f"{path.name} already exists")
    text = fill(template.read_text(), {"{{DATE}}": day, "{{CREATED}}": now.strftime("%Y-%m-%dT%H:%M:%S%z"), "{{TITLE}}": title})
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def main(argv=None):
    """
    The command line behind new-eda, new-experiment and new-labnote: print the path written, exit 2 on a refusal.
    """
    parser = argparse.ArgumentParser(prog="python -m proj_helpers.new")
    kinds = parser.add_subparsers(dest="kind", required=True)
    eda = kinds.add_parser("eda", help=f"an EDA notebook under {EDA_DIR}/ from {EDA_TEMPLATE}")
    eda.add_argument("title", nargs="+", help="the notebook's title, e.g. heading gaps")
    eda.add_argument("--dir", type=Path, help=f"the folder to write into (default: {EDA_DIR}/)")
    experiment = kinds.add_parser("experiment", help=f"an experiment folder under {EXPERIMENTS_DIR}/")
    experiment.add_argument("title", nargs="+", help="the experiment's title, e.g. window 60 s")
    experiment.add_argument("--config", default=DEFAULT_CONFIG, help=f"a config under {EXPERIMENT_CONFIGS}/ by name (default: {DEFAULT_CONFIG})")
    note = kinds.add_parser("labnote", help=f"a lab notebook entry from {LABNOTE_TEMPLATE}")
    note.add_argument("slug", nargs="*", help="optional words for the file name, e.g. axis analysis")
    note.add_argument("--dir", type=Path, help=f"the folder to write into (default: {LABNOTE_DIR}/)")
    args = parser.parse_args(argv)
    try:
        if args.kind == "eda":
            path = new_eda(" ".join(args.title), directory=args.dir)
        elif args.kind == "experiment":
            path = new_experiment(" ".join(args.title), args.config)
        else:
            path = new_labnote(" ".join(args.slug), directory=args.dir)
    except (ValueError, FileExistsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
