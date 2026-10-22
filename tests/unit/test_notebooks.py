"""
New notebooks and lab notes: the filled template, the refusal to overwrite, and the git filter.
"""

import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import nbformat
import pytest

from proj_helpers.notebooks import main, new_labnote, new_notebook, slugify
from proj_helpers.paths import repo_root


def _run(cwd: Path, command: list[str]) -> str:
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_new_notebook_fills_the_template_and_refuses_to_overwrite(tmp_path: Path):
    template = tmp_path / "template.ipynb"
    nbformat.write(nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("# {{DATE}} {{TITLE}}\n"
                                      "{{AUTHOR}} {{NAME}} {{CREATED}}"),
        nbformat.v4.new_code_cell("x = 1"),
    ]), template)
    options = dict(author="Test Author", directory=tmp_path / "nb",
                   template=template, today=date(2026, 9, 29))

    path = new_notebook("Matlab Axis Analysis", **options)
    assert path == tmp_path / "nb" / "2026-09-29_matlab-axis-analysis.ipynb"

    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    header = notebook.cells[0].source
    assert "2026-09-29" in header and "matlab axis analysis" in header
    assert "Test Author" in header and "{{" not in header

    with pytest.raises(FileExistsError, match="already exists"):
        new_notebook("Matlab Axis Analysis", **options)

    assert slugify("  Hello,  World!! ") == "hello-world"
    with pytest.raises(ValueError, match="no letters or digits"):
        new_notebook("!!!", **options)


def test_new_notebooks_go_under_notebooks_at_the_top_level(tmp_path: Path, monkeypatch):
    (tmp_path / "templates").mkdir()
    nbformat.write(nbformat.v4.new_notebook(), tmp_path / "templates" / "notebook.ipynb")
    monkeypatch.setattr("proj_helpers.notebooks.repo_root", lambda: tmp_path)
    path = new_notebook("scratch", author="Test Author", today=date(2026, 10, 21))
    assert path == tmp_path / "notebooks" / "2026-10-21_scratch.ipynb"


def test_the_command_line_writes_a_dated_notebook(tmp_path: Path, capsys):
    assert main(["notebook", "cli", "check", "--dir", str(tmp_path)]) == 0
    written = Path(capsys.readouterr().out.strip())
    assert written.parent == tmp_path and written.name.endswith("_cli-check.ipynb")
    assert main(["notebook", "cli", "check", "--dir", str(tmp_path)]) == 2


NOW = datetime(2026, 10, 12, 9, 5, 7, tzinfo=timezone(timedelta(hours=-7)))


def test_new_labnote_without_words_is_named_by_the_date(tmp_path: Path):
    path = new_labnote(directory=tmp_path, now=NOW)
    assert path == tmp_path / "2026-10-12.md"
    assert path.read_text() == ("---\ndate: 2026-10-12\ncreated: 2026-10-12T09:05:07-0700\n"
                                "tags: []\n---\n\n# 2026-10-12\n\n")


def test_new_labnote_with_words_is_named_by_the_slug(tmp_path: Path):
    path = new_labnote("Axis  Analysis, Take 2!", directory=tmp_path, now=NOW)
    assert path == tmp_path / "2026-10-12__axis-analysis-take-2.md"
    assert "\n# axis analysis take 2\n" in path.read_text()
    with pytest.raises(ValueError, match="slug is empty"):
        new_labnote("!!!", directory=tmp_path, now=NOW)


def test_new_labnote_refuses_an_existing_file(tmp_path: Path):
    new_labnote("notes", directory=tmp_path, now=NOW)
    with pytest.raises(FileExistsError, match="2026-10-12__notes.md already exists"):
        new_labnote("notes", directory=tmp_path, now=NOW)


def test_git_filter_stores_notebooks_without_outputs(tmp_path: Path):
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    _run(tmp_path, ["git", "init", "-q"])
    _run(tmp_path, ["git", "config", "user.name", "Test Author"])
    _run(tmp_path, ["git", "config", "user.email", "test@example.com"])
    shutil.copy(repo_root() / ".gitattributes", tmp_path / ".gitattributes")
    _run(tmp_path, [sys.executable, "-m", "nbstripout", "--install",
                    "--attributes", ".gitattributes"])

    cell = nbformat.v4.new_code_cell("print('hello')")
    cell.outputs = [nbformat.v4.new_output("stream", name="stdout", text="hello")]
    cell.execution_count = 1
    nbformat.write(nbformat.v4.new_notebook(cells=[cell]), tmp_path / "nb.ipynb")
    _run(tmp_path, ["git", "add", "nb.ipynb"])

    staged = nbformat.reads(_run(tmp_path, ["git", "show", ":nb.ipynb"]), as_version=4)
    assert staged.cells[0].outputs == []
    assert staged.cells[0].execution_count is None
    on_disk = nbformat.read(tmp_path / "nb.ipynb", as_version=4)
    assert len(on_disk.cells[0].outputs) == 1
