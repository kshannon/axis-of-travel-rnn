"""
The store group: init and inspect.
"""

from pathlib import Path

from axis_of_travel_rnn.store import Store, resolve_store
from ._output import emit, fail, lines


def register(commands) -> None:
    p = commands.add_parser(
        "init", help="create a store's layout and marker",
        description="Create the store layout and its store.yaml marker: "
                    "<store>/store.yaml plus datasets/, models/ and experiments/. "
                    "An initialized store is left untouched.")
    p.add_argument("dir", metavar="DIR", nargs="?",
                   help="directory to initialize (default: the resolved store)")
    p.set_defaults(func=init_store)

    p = commands.add_parser(
        "inspect", help="show the resolved store, its marker and counts",
        description="Show the resolved store: path, how it was chosen, marker "
                    "contents, artifacts per kind. Reads store.yaml and every "
                    "manifest; writes nothing.")
    p.add_argument("--json", action="store_true", help="print the same data as JSON")
    p.set_defaults(func=inspect_store)


def init_store(args) -> int:
    store = (Store(Path(args.dir).expanduser(), "argument") if args.dir
             else resolve_store(args.store))
    existed = store.initialized
    try:
        marker = store.init()
    except OSError as e:
        return fail(str(e))
    state = "already initialized" if existed else "initialized"
    print(f"{state} store at {store.root} (version {marker['store_version']})")
    return 0


def inspect_store(args) -> int:
    store = resolve_store(args.store)
    marker = store.read_marker()
    counts = store.counts()
    report = {"path": str(store.root), "source": store.source, "marker": marker,
              "counts": counts}
    pairs = [("path", store.root), ("chosen by", store.source)]
    pairs += [(key.replace("_", " "), value) for key, value in marker.items()]
    pairs += list(counts.items())
    emit(report, lines(f"store {store.root}", pairs), as_json=args.json)
    return 0
