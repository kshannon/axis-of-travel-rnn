"""
The funnel: which sessions and epochs of the transformed lab data become blocks, with the count after each step.
"""

from pathlib import Path

import pyarrow.csv as pacsv

# The spec's Selection: sessions of this protocol, outside these groups and not excluded by hand, then their epochs
# of these kinds under this condition.
PROTOCOL = "standard"
CONDITION = "baseline"
EPOCHS = ("arena", "track")
EXCLUDED_GROUPS = ("JL1HPCData",)

# The converter's tables (tables.md 2) and the folder of frames files, all required, and the two files made by hand,
# each optional.
TABLES = ("sessions", "epochs", "runs")
FRAMES = "frames"
ANNOTATIONS = "annotations.csv"
VERDICTS = "verdicts.csv"


def read_csv(path):
    """
    A csv file as a list of dicts, one per row, with blanks as None.
    """
    return pacsv.read_csv(path).to_pylist()


def read_tables(root):
    """
    The three tables plus annotations and verdicts (empty when the file is absent), each a list of row dicts.
    """
    root = Path(root)
    tables = {name: read_csv(root / f"{name}.csv") for name in TABLES}
    for name, file in (("annotations", ANNOTATIONS), ("verdicts", VERDICTS)):
        tables[name] = read_csv(root / file) if (root / file).is_file() else []
    return tables


def matches(session_id, only):
    """
    Whether a session id is PREFIX or continues it after an underscore, and always when there is no PREFIX.
    """
    return only is None or session_id == only or session_id.startswith(only + "_")


def funnel(tables, only):
    """
    Apply the Selection steps in order and return the surviving epochs and the (step, count) list the steps produce.
    """
    excluded = {row["session_id"] for row in tables["annotations"] if row.get("exclude")}
    session_steps = (
        ("all sessions", lambda s: True),
        (f"protocol {PROTOCOL}", lambda s: s["protocol"] == PROTOCOL),
        ("group allowed", lambda s: s["group"] not in EXCLUDED_GROUPS),
        ("not excluded by annotations", lambda s: s["session_id"] not in excluded),
        ("--only", lambda s: matches(s["session_id"], only)),
    )
    counts = []
    sessions = tables["sessions"]
    for step, keep in session_steps:
        sessions = [s for s in sessions if keep(s)]
        counts.append((f"sessions, {step}", len(sessions)))
    kept = {s["session_id"] for s in sessions}
    epoch_steps = (
        ("of those sessions", lambda e: e["session_id"] in kept),
        ("kind " + " or ".join(EPOCHS), lambda e: e["epoch"] in EPOCHS),
        (f"condition {CONDITION}", lambda e: e["condition"] == CONDITION),
    )
    epochs = tables["epochs"]
    for step, keep in epoch_steps:
        epochs = [e for e in epochs if keep(e)]
        counts.append((f"epochs, {step}", len(epochs)))
    tracks = {(e["session_id"], e["epoch"]) for e in epochs if e["epoch"] == "track"}
    runs = [r for r in tables["runs"] if (r["session_id"], r["epoch"]) in tracks]
    counts.append(("runs, of surviving track epochs", len(runs)))
    counts.append(("runs, clean", sum(1 for r in runs if r["clean"])))
    return epochs, counts
