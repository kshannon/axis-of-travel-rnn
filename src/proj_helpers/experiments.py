"""
New experiment folders from templates/experiment, run as pixi run new-experiment "<title>".
"""

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

from .notebooks import git_user_name, slugify
from .paths import repo_root

EXPERIMENTS_DIR = "experiments"
TEMPLATE_DIR = "templates/experiment"
NOTEBOOK = "notebook.ipynb"


def fill(text, fields):
    """
    The text with every placeholder replaced by its value.
    """
    for placeholder, value in fields.items():
        text = text.replace(placeholder, value)
    return text


def new_experiment(title, *, directory=None, template=None, author=None, today=None):
    """
    Copy the template folder to <directory>/<today>_<slug>/ with the title, date and author in its notebook, and return the folder.
    """
    import nbformat

    slug = slugify(title)
    if not slug:
        raise ValueError("experiment title has no letters or digits")
    directory = repo_root() / EXPERIMENTS_DIR if directory is None else Path(directory)
    template = repo_root() / TEMPLATE_DIR if template is None else Path(template)
    today = date.today() if today is None else today
    folder = directory / f"{today.isoformat()}_{slug}"
    if folder.exists():
        raise FileExistsError(f"{folder} already exists")
    fields = {"{{TITLE}}": title, "{{DATE}}": today.isoformat(), "{{AUTHOR}}": git_user_name() if author is None else author}
    shutil.copytree(template, folder)
    notebook = nbformat.read(folder / NOTEBOOK, as_version=4)
    for cell in notebook.cells:
        cell.source = fill(cell.source, fields)
    nbformat.write(notebook, folder / NOTEBOOK)
    return folder


def main(argv=None):
    """
    The command line behind the new-experiment task: print the folder made.
    """
    parser = argparse.ArgumentParser(prog="new-experiment", description="Copy templates/experiment to experiments/YYYY-MM-DD_<slug>/.")
    parser.add_argument("title", nargs="+", help="the experiment's title, e.g. window 60 s")
    args = parser.parse_args(argv)
    try:
        folder = new_experiment(" ".join(args.title))
    except (ValueError, FileExistsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
