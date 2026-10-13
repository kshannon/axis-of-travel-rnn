"""
Listing registered artifacts: datasets, models and experiments.
"""

from axis_of_travel_rnn.store import open_store
from ._output import emit, table

OPTIONAL = ("environment", "dataset", "created", "description")


def register(commands, kind: str) -> None:
    p = commands.add_parser(
        "list", help=f"list registered {kind}",
        description=f"List registered {kind}. Reads <store>/{kind}/*/manifest.yaml; "
                    "writes nothing.")
    p.add_argument("--json", action="store_true", help="print the same data as JSON")
    p.set_defaults(func=list_artifacts, kind=kind)


def list_artifacts(args) -> int:
    store = open_store(args.store)
    entries = store.artifacts(args.kind)
    if not entries:
        print(f"no {args.kind} registered under {store.kind_dir(args.kind)}")
        return 0
    columns = ["id", *(c for c in OPTIONAL if any(c in e.meta for e in entries))]
    rows = [{"id": e.id, **{c: e.meta.get(c, "") for c in columns[1:]}}
            for e in entries]
    emit(rows, table(rows, columns), as_json=args.json)
    return 0
