"""
New notebooks and lab notes: the slug, the author, and the template with its placeholders filled.
"""

import argparse
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from .paths import repo_root


def slugify(text: str) -> str:
    """
    Lowercase; every run of other characters becomes one dash; no outer dashes.
    """
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def git_user_name() -> str:
    """
    git's configured user.name, empty when git is missing or the name is unset.
    """
    try:
        done = subprocess.run(["git", "config", "user.name"], cwd=repo_root(),
                              capture_output=True, text=True)
    except OSError:
        return ""
    return done.stdout.strip()


def new_notebook(name: str, *, title: str | None = None, author: str | None = None,
                 directory: Path | None = None, template: Path | None = None,
                 today: date | None = None) -> Path:
    """
    Write <directory>/<today>_<slug>.ipynb from the template and return its path.
    """
    import nbformat

    slug = slugify(name)
    if not slug:
        raise ValueError("notebook name has no letters or digits")
    if directory is None:
        directory = repo_root() / "src" / "notebooks"
    if template is None:
        template = repo_root() / "templates" / "notebook.ipynb"
    if today is None:
        today = date.today()
    path = directory / f"{today.isoformat()}_{slug}.ipynb"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    fields = {
        "{{DATE}}": today.isoformat(),
        "{{TITLE}}": slug.replace("-", " ") if title is None else title,
        "{{NAME}}": slug,
        "{{AUTHOR}}": git_user_name() if author is None else author,
        "{{CREATED}}": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    notebook = nbformat.read(template, as_version=4)
    for cell in notebook.cells:
        for placeholder, value in fields.items():
            cell.source = cell.source.replace(placeholder, value)
    directory.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, path)
    return path


def new_labnote(words: str = "", *, directory: Path | None = None,
                template: Path | None = None, now: datetime | None = None) -> Path:
    """
    Write <directory>/<date>.md, or <date>__<slug>.md, from the template and return its path.
    """
    if directory is None:
        directory = repo_root() / "labnotebook"
    if template is None:
        template = repo_root() / "templates" / "labnotebook.md"
    if now is None:
        now = datetime.now().astimezone()
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
    fields = {
        "{{DATE}}": day,
        "{{CREATED}}": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "{{TITLE}}": title,
    }
    text = template.read_text()
    for placeholder, value in fields.items():
        text = text.replace(placeholder, value)
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def main(argv: list[str] | None = None) -> int:
    """
    The command line behind the new-jupyter-nb and new-labnote tasks: print the path written.
    """
    parser = argparse.ArgumentParser(prog="python -m proj_helpers.notebooks")
    kinds = parser.add_subparsers(dest="kind", required=True)
    nb = kinds.add_parser("notebook", help="create a notebook from templates/notebook.ipynb")
    nb.add_argument("name", nargs="+", help="notebook name, slugified, e.g. matlab axis analysis")
    nb.add_argument("--title", help="header title (default: the name with spaces)")
    nb.add_argument("--author", help="header author (default: git's user.name)")
    nb.add_argument("--dir", type=Path, help="directory to write into (default: src/notebooks/)")
    note = kinds.add_parser("labnote", help="create a lab notebook entry from templates/labnotebook.md")
    note.add_argument("slug", nargs="*", help="optional words for the file name, e.g. axis analysis")
    note.add_argument("--dir", type=Path, help="directory to write into (default: labnotebook/)")
    args = parser.parse_args(argv)
    try:
        if args.kind == "notebook":
            path = new_notebook(" ".join(args.name), title=args.title, author=args.author,
                                directory=args.dir)
        else:
            path = new_labnote(" ".join(args.slug), directory=args.dir)
    except (ValueError, FileExistsError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
