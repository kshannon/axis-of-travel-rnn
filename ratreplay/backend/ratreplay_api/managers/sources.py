"""
The two data folders the config names: each is checked against the data format and described with its status, counts and manifest.
"""

from pathlib import Path

from axis_of_travel_rnn import trajectory

from .. import contract
from ..errors import Invalid, NotFound
from ..stores import folder, processed, review, transformed

# The config key of each folder, which the processor reads too.
KEYS = {"transformed": "TRANSFORMED_LAB_DATA", "processed": "PROCESSED_LAB_DATA"}


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


def transformed_problems(root):
    """
    How a folder breaks the transformed format: tables, the manifest and the first frames file are checked.
    """
    problems = []
    for name, (_, required) in contract.TABLES.items():
        if transformed.has_file(root, name):
            problems += column_problems(name, required, transformed.csv_columns(root, name))
        elif name not in contract.OPTIONAL_TABLES:
            problems.append(f"missing {name}")
    problems += manifest_problems(transformed.has_file(root, contract.MANIFEST), lambda: transformed.manifest(root),
                                  contract.TRANSFORMED_MANIFEST_KEYS)
    ids = transformed.frame_ids(root)
    if ids:
        problems += column_problems(f"{contract.FRAMES_DIR}/{ids[0]}.parquet", contract.FRAMES_REQUIRED, transformed.frames_columns(root, ids[0]))
    else:
        problems.append(f"{contract.FRAMES_DIR}/ holds no parquet files")
    return problems


def processed_problems(root):
    """
    How a folder breaks the processed format: the manifest, each kind's blocks csv and the parquet of every block.
    """
    problems = manifest_problems(processed.is_built(root), lambda: processed.read_manifest(root), contract.PROCESSED_MANIFEST_KEYS)
    for kind in trajectory.KINDS:
        name = f"{kind}/{trajectory.BLOCKS_CSV}"
        if processed.has_blocks_csv(root, kind):
            problems += column_problems(name, contract.BLOCKS_CSV, processed.csv_columns(root, kind))
        else:
            problems.append(f"missing {name}")
    if not problems:
        absent = [row["block_id"] for row in processed.list_blocks(root) if not row["path"].is_file()]
        if absent:
            problems.append(f"{len(absent)} block files missing, the first is {absent[0]}")
    return problems


def not_set(kind, config_path):
    """
    The problem of a config file without the kind's key.
    """
    return f"{KEYS[kind]} is not set in {config_path}"


def not_there(kind, root):
    """
    The problem of a folder the config names that is not on disk.
    """
    return f"{KEYS[kind]} {root} does not exist"


def root_of(config, kind):
    """
    The folder the config names for the kind, resolved as the processor resolves it, none when the key is not set.
    """
    value = config.get(KEYS[kind])
    return Path(str(value)).expanduser().resolve() if value else None


def required_root(config, config_path, kind):
    """
    The folder the config names for the kind, refused when the key is not set.
    """
    root = root_of(config, kind)
    if root is None:
        raise Invalid(not_set(kind, config_path))
    return root


def transformed_root(config, config_path):
    """
    The transformed folder the sessions are read from, refused when the key is not set or the folder is not there.
    """
    root = required_root(config, config_path, "transformed")
    if not folder.exists(root):
        raise NotFound(not_there("transformed", root))
    return root


def problems_of(kind, root):
    """
    Every way the folder breaks the format. A processed folder not built yet has none, the first review save creates it.
    """
    if kind == "processed":
        return processed_problems(root) if processed.is_built(root) else []
    return transformed_problems(root) if folder.exists(root) else [not_there(kind, root)]


def counts_of(kind, root):
    """
    What the folder holds: a transformed one its sessions, epochs, runs and frames files, a processed one its reviews and, once the processor ran, its blocks.
    """
    if kind == "transformed":
        tables = transformed.read_tables(root)
        return {"sessions": len(tables["sessions"]), "epochs": len(tables["epochs"]), "runs": len(tables["runs"]),
                "frames": len(transformed.frame_ids(root))}
    counts = {"reviews": len(review.list_ids(root))}
    return {"blocks": len(processed.list_blocks(root)), **counts} if processed.is_built(root) else counts


def manifest_info(kind, root):
    """
    When the folder's manifest says its run happened and when its newest file was written, none for a processed folder not built yet.
    """
    if kind == "transformed":
        manifest = transformed.manifest(root)
    elif processed.is_built(root):
        manifest = processed.read_manifest(root)
    else:
        return None
    return {"timestamp": manifest["run"]["timestamp"], "modified": folder.modified(root)}


def describe(kind, root, config_path):
    """
    The folder with its path, status, problems, counts and manifest facts, checked now.
    """
    problems = [not_set(kind, config_path)] if root is None else problems_of(kind, root)
    described = {"path": str(root) if root else None, "status": "invalid", "problems": problems, "counts": {}, "manifest": None}
    if problems:
        return described
    return {**described, "status": "ok", "counts": counts_of(kind, root), "manifest": manifest_info(kind, root)}


def describe_all(config, config_path):
    """
    Both folders described, and the config file they come from.
    """
    return {**{kind: describe(kind, root_of(config, kind), config_path) for kind in KEYS}, "config_path": config_path}
