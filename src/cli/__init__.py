"""
Command-line entry point: axis-of-travel-rnn <group> <command>.
"""

import argparse

from axis_of_travel_rnn import __version__
from axis_of_travel_rnn.store import ENV_VAR, StoreError
from . import artifacts, env, labnote, notebook, store
from ._output import fail, not_implemented

GROUPS = {
    "store": "the artifact store",
    "env": "environment geometry",
    "agent": "behavioral agents (model rats)",
    "data": "synthetic trajectory datasets",
    "model": "trained models (model animals)",
    "analysis": "hidden states and axis-of-travel analysis",
    "experiment": "experiments: populations of models",
    "notebook": "jupyter notebooks from the template",
    "labnote": "lab notebook entries from the template",
}

STUBS = (
    ("agent", "list", "list every agent config with its hash and use counts"),
    ("agent", "inspect", "describe one agent: parameters, hashes, references"),
    ("data", "inspect", "describe one dataset: manifest, counts, split, validation"),
    ("data", "generate", "build a dataset from an environment, agents and seeds"),
    ("data", "validate", "compare a dataset's behavior with a reference file"),
    ("data", "stats", "print a dataset's behavioral statistics"),
    ("model", "inspect", "describe one model: manifest, checkpoints, metrics"),
    ("model", "train", "train one model animal"),
    ("model", "evaluate", "evaluate a frozen model on a held-out split"),
    ("analysis", "record-hidden", "record hidden states from a frozen checkpoint"),
    ("analysis", "axis", "measure axis-of-travel tuning per hidden unit"),
    ("experiment", "inspect", "describe one experiment: members, status, results"),
    ("experiment", "run", "train a population from one config"),
    ("experiment", "reproduce", "re-run an experiment and compare"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="axis-of-travel-rnn",
        description="Axis-of-travel emergence in position-predicting RNNs.",
        epilog="Exit codes: 0 success, 1 no command, 2 usage error or unusable store, "
               "3 not implemented, 4 provenance mismatch.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--store", metavar="DIR",
                        help=f"artifact store for this run (default: ${ENV_VAR}, "
                             "else artifacts/ in the checkout)")
    groups = parser.add_subparsers(dest="group", metavar="<group>", title="groups")
    commands = {}
    for name, summary in GROUPS.items():
        group = groups.add_parser(name, help=summary, description=summary)
        group.set_defaults(group_parser=group)
        commands[name] = group.add_subparsers(dest="command", metavar="<command>",
                                              title="commands")
    store.register(commands["store"])
    env.register(commands["env"])
    artifacts.register(commands["data"], "datasets")
    artifacts.register(commands["model"], "models")
    artifacts.register(commands["experiment"], "experiments")
    notebook.register(commands["notebook"])
    labnote.register(commands["labnote"])
    for group_name, command, summary in STUBS:
        p = commands[group_name].add_parser(command, help=summary)
        p.set_defaults(func=not_implemented, name=f"{group_name} {command}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        getattr(args, "group_parser", parser).print_help()
        return 1
    try:
        return args.func(args)
    except StoreError as e:
        return fail(str(e))
