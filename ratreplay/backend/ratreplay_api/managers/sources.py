"""
The attached sources: a folder is checked against the data format on attach, and each source is described with its status, counts and manifests.
"""

from pathlib import Path

from axis_of_travel_rnn import trajectory

from .. import contract, registry
from ..errors import Conflict, Invalid
from ..stores import folder, processed, review, transformed

PROCESSED_PREFIX = "processed dataset: "
ALREADY_ATTACHED = "{path} is already attached as {kind} with its reviews and blocks in {processed_path}, detach it first to attach it differently"


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


def problems_of(kind, root, processed_root):
    """
    Every way the source breaks the format, none when it can be attached. A processed dataset paired with a transformed source is checked once it has a manifest, it may not be built yet.
    """
    if not folder.exists(root):
        return ["folder does not exist"]
    if kind == "processed":
        return processed_problems(root)
    problems = transformed_problems(root)
    if processed.is_built(processed_root):
        problems += [PROCESSED_PREFIX + problem for problem in processed_problems(processed_root)]
    return problems


def counts_of(entry):
    """
    What the source holds: for a transformed one its sessions, epochs, runs and frames files, then the blocks of a built processed dataset and the reviews.
    """
    root, processed_root = Path(entry["path"]), Path(entry["processed_path"])
    counts = {}
    if entry["kind"] == "transformed":
        tables = transformed.read_tables(root)
        counts = {"sessions": len(tables["sessions"]), "epochs": len(tables["epochs"]), "runs": len(tables["runs"]),
                  "frames": len(transformed.frame_ids(root))}
    if processed.is_built(processed_root):
        counts["blocks"] = len(processed.list_blocks(processed_root))
    return {**counts, "reviews": len(review.list_ids(processed_root))}


def manifest_info(root, read):
    """
    When the folder's manifest says its run happened and when its newest file was written.
    """
    return {"timestamp": read(root)["run"]["timestamp"], "modified": folder.modified(root)}


def describe(entry):
    """
    The entry with its status, problems, counts and the facts of the transformed and processed manifests, checked now.
    """
    root, processed_root = Path(entry["path"]), Path(entry["processed_path"])
    problems = problems_of(entry["kind"], root, processed_root)
    if problems:
        return {**entry, "status": "invalid", "problems": problems, "counts": {}, "manifests": {"transformed": None, "processed": None}}
    manifests = {"transformed": manifest_info(root, transformed.manifest) if entry["kind"] == "transformed" else None,
                 "processed": manifest_info(processed_root, processed.read_manifest) if processed.is_built(processed_root) else None}
    return {**entry, "status": "ok", "problems": [], "counts": counts_of(entry), "manifests": manifests}


def list_all(registry_path):
    """
    Every attached source, described.
    """
    return [describe(entry) for entry in registry.read_all(registry_path)]


def attach(registry_path, kind, path, processed_path):
    """
    Attach the folder when it follows the format, and describe the entry. A transformed source is paired with the processed folder its reviews and blocks live in, a processed one is its own. A folder already attached as another kind or with another processed folder is refused before it is checked.
    """
    if kind == "transformed" and not processed_path:
        raise Invalid("a transformed source needs processed_path, the folder its reviews and blocks live in")
    paired = processed_path if kind == "transformed" else path
    root, paired_root = Path(path).expanduser().resolve(), Path(paired).expanduser().resolve()
    recorded = registry.find(registry_path, root)
    if recorded and (recorded["kind"], recorded["processed_path"]) != (kind, str(paired_root)):
        raise Conflict(ALREADY_ATTACHED.format(**recorded))
    problems = problems_of(kind, root, paired_root)
    if problems:
        raise Invalid(f"cannot attach {path}: " + ", ".join(problems))
    return describe(registry.attach(registry_path, kind, path, paired))


def detach(registry_path, sid):
    """
    Forget the source, its data stays where it is.
    """
    registry.detach(registry_path, sid)
