"""
The two data folders the config names: each is checked against the data format and described with its status, counts and manifest.
"""

from axis_of_travel_rnn import trajectory

from .. import contract
from ..stores import folder, processed, review, transformed


def has_key(manifest, dotted):
    """
    Whether the manifest holds the key, "run.timestamp" meaning the timestamp inside run.
    """
    for part in dotted.split("."):
        manifest = manifest.get(part) if isinstance(manifest, dict) else None
    return manifest is not None


def manifest_problems(present, read, keys):
    """
    What is wrong with a manifest file: missing, not json, or lacking a key.
    """
    if not present:
        return ["missing manifest.json"]
    try:
        manifest = read()
    except ValueError:
        return ["manifest.json is not valid json"]
    return [f"manifest.json lacks {key}" for key in keys if not has_key(manifest, key)]


def column_problems(name, required, found):
    """
    The one problem of a file lacking required columns, none when it has them all.
    """
    missing = [column for column in required if column not in found]
    return [f"{name} lacks {', '.join(missing)}"] if missing else []


def transformed_problems(sources):
    """
    How the transformed folder breaks its format: tables, the manifest and the first frames file are checked.
    """
    problems = []
    for name, (_, required) in contract.TABLES.items():
        if transformed.has_file(sources, name):
            problems += column_problems(name, required, transformed.csv_columns(sources, name))
        elif name not in contract.OPTIONAL_TABLES:
            problems.append(f"missing {name}")
    problems += manifest_problems(transformed.has_file(sources, contract.MANIFEST), lambda: transformed.manifest(sources),
                                  contract.TRANSFORMED_MANIFEST_KEYS)
    ids = transformed.frame_ids(sources)
    if ids:
        problems += column_problems(f"{contract.FRAMES_DIR}/{ids[0]}.parquet", contract.FRAMES_REQUIRED, transformed.frames_columns(sources, ids[0]))
    else:
        problems.append(f"{contract.FRAMES_DIR}/ holds no parquet files")
    return problems


def processed_problems(sources):
    """
    How the processed folder breaks its format: the manifest, each kind's blocks csv and the parquet of every block.
    """
    problems = manifest_problems(processed.is_built(sources), lambda: processed.read_manifest(sources), contract.PROCESSED_MANIFEST_KEYS)
    for kind in trajectory.KINDS:
        name = f"{kind}/{trajectory.BLOCKS_CSV}"
        if processed.has_blocks_csv(sources, kind):
            problems += column_problems(name, contract.BLOCKS_CSV, processed.csv_columns(sources, kind))
        else:
            problems.append(f"missing {name}")
    if not problems:
        absent = [row["block_id"] for row in processed.list_blocks(sources) if not row["path"].is_file()]
        if absent:
            problems.append(f"{len(absent)} block files missing, the first is {absent[0]}")
    return problems


def problems_of(sources, kind):
    """
    Every way the folder breaks the format. A processed folder not built yet has none, the first review save creates it.
    """
    if kind == "processed":
        return processed_problems(sources) if processed.is_built(sources) else []
    return transformed_problems(sources) if folder.exists(sources, kind) else [sources.not_there(kind)]


def counts_of(sources, kind):
    """
    What the folder holds: a transformed one its sessions, epochs, runs and frames files, a processed one its reviews and, once the processor ran, its blocks.
    """
    if kind == "transformed":
        tables = transformed.read_tables(sources)
        return {"sessions": len(tables["sessions"]), "epochs": len(tables["epochs"]), "runs": len(tables["runs"]),
                "frames": len(transformed.frame_ids(sources))}
    counts = {"reviews": len(review.list_ids(sources))}
    return {"blocks": len(processed.list_blocks(sources)), **counts} if processed.is_built(sources) else counts


def manifest_info(sources, kind):
    """
    When the folder's manifest says its run happened and when its newest file was written, none for a processed folder not built yet.
    """
    if kind == "transformed":
        manifest = transformed.manifest(sources)
    elif processed.is_built(sources):
        manifest = processed.read_manifest(sources)
    else:
        return None
    return {"timestamp": manifest["run"]["timestamp"], "modified": folder.modified(sources, kind)}


def describe(sources, kind):
    """
    The folder with its path, status, problems, counts and manifest facts, checked now.
    """
    root = sources.root(kind)
    problems = [sources.not_set(kind)] if root is None else problems_of(sources, kind)
    described = {"path": str(root) if root else None, "status": "invalid", "problems": problems, "counts": {}, "manifest": None}
    if problems:
        return described
    return {**described, "status": "ok", "counts": counts_of(sources, kind), "manifest": manifest_info(sources, kind)}


def status(sources):
    """
    The transformed and processed folders each with its status, counts and manifest, and the config file they come from.
    """
    return {"transformed": describe(sources, "transformed"), "processed": describe(sources, "processed"), "config_path": str(sources.config_path)}
