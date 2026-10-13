"""
The CLI: dispatch, exit codes and what the implemented commands print.
"""

import argparse
import json
from pathlib import Path

import pytest

from cli import STUBS, build_parser, main
from cli._output import not_implemented

ENV_NAMES = ["open_arena", "plus_maze", "triple_t", "triple_t_rot90"]
KINDS = [("data", "datasets"), ("model", "models"), ("experiment", "experiments")]
STUB_COMMANDS = [f"{group} {command}" for group, command, _ in STUBS]
REAL = {"store init", "store inspect", "env list", "env inspect", "data list",
        "model list", "experiment list", "notebook new", "labnote new"}


def _commands(parser):
    """
    Every "<group> <command>" in the parser tree, paired with its own parser.
    """
    def subparsers(p):
        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action.choices
        return {}

    for group, group_parser in subparsers(parser).items():
        for command, command_parser in subparsers(group_parser).items():
            yield f"{group} {command}", command_parser


def _init_store(tmp_path: Path, capsys) -> Path:
    root = tmp_path / "store"
    assert main(["store", "init", str(root)]) == 0
    capsys.readouterr()
    return root


def _manifest(root: Path, kind: str, name: str, body: str) -> None:
    d = root / kind / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.yaml").write_text(body)


def test_no_command_prints_help(capsys):
    assert main([]) == 1
    assert "usage" in capsys.readouterr().out.lower()


def test_group_without_a_command_prints_that_group_help(capsys):
    assert main(["env"]) == 1
    assert "inspect" in capsys.readouterr().out


def test_env_list_shows_every_config(capsys):
    assert main(["env", "list"]) == 0
    out = capsys.readouterr().out
    assert all(name in out for name in ENV_NAMES)
    assert "hash" in out

    assert main(["env", "list", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["name"] for row in rows] == ENV_NAMES
    assert all(len(row["hash"]) == 12 for row in rows)


def test_env_inspect_json_is_the_canonical_spec(capsys):
    assert main(["env", "inspect", "triple_t", "--json"]) == 0
    spec = json.loads(capsys.readouterr().out)
    assert spec["name"] == "triple_t"
    assert {"kind", "hash"} <= set(spec)


def test_env_inspect_unknown_name_lists_what_exists(capsys):
    assert main(["env", "inspect", "nope"]) == 2
    err = capsys.readouterr().err
    assert "nope" in err and all(name in err for name in ENV_NAMES)


def test_store_init_then_inspect(tmp_path: Path, capsys):
    root = _init_store(tmp_path, capsys)
    assert main(["--store", str(root), "store", "inspect"]) == 0
    out = capsys.readouterr().out
    assert str(root) in out
    assert all(kind in out for kind in ("datasets", "models", "experiments"))

    assert main(["--store", str(root), "store", "inspect", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"datasets": 0, "models": 0, "experiments": 0}
    assert report["source"] == "flag"


def test_store_init_without_a_directory_uses_the_environment_variable(
        tmp_path: Path, monkeypatch):
    root = tmp_path / "from-env"
    monkeypatch.setenv("SUBICULUM_RNN_STORE", str(root))
    assert main(["store", "init"]) == 0
    assert (root / "store.yaml").is_file()


def test_an_unusable_store_fails_cleanly(tmp_path: Path, capsys):
    assert main(["--store", str(tmp_path / "unplugged"), "data", "list"]) == 2
    assert "store not found" in capsys.readouterr().err


@pytest.mark.parametrize("group,kind", KINDS, ids=[k for _, k in KINDS])
def test_list_reports_empty_then_registered(group, kind, tmp_path: Path, capsys):
    root = _init_store(tmp_path, capsys)
    assert main(["--store", str(root), group, "list"]) == 0
    assert f"no {kind} registered" in capsys.readouterr().out

    _manifest(root, kind, "a_0001", "id: a_0001\ndescription: first one\n")
    assert main(["--store", str(root), group, "list"]) == 0
    out = capsys.readouterr().out
    assert "a_0001" in out and "first one" in out


def test_a_manifest_with_the_wrong_id_fails_the_list(tmp_path: Path, capsys):
    root = _init_store(tmp_path, capsys)
    _manifest(root, "datasets", "ds_0001", "id: ds_0009\n")
    assert main(["--store", str(root), "data", "list"]) == 2
    assert "ds_0009" in capsys.readouterr().err


@pytest.mark.parametrize("name", STUB_COMMANDS)
def test_every_stub_exits_3(name, capsys):
    assert main(name.split()) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not implemented" in captured.err


def test_notebook_new_writes_a_dated_notebook(tmp_path: Path, capsys):
    assert main(["notebook", "new", "cli", "check", "--dir", str(tmp_path)]) == 0
    written = Path(capsys.readouterr().out.strip())
    assert written.parent == tmp_path and written.name.endswith("_cli-check.ipynb")
    assert written.is_file()


def test_the_implemented_commands_are_the_ones_the_spec_promises():
    assert {name for name, parser in _commands(build_parser())
            if parser.get_default("func") is not not_implemented} == REAL
