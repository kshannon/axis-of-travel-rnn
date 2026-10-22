"""
Build the blocks a blueprint names from the transformed folder and the review files, run as pixi run build-blocks --blueprint NAME.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
from pydantic import ValidationError

from axis_of_travel_rnn import __version__

from ..config import REPO_ROOT, local_config, local_path
from . import VERSION, BlockEngine, io
from .blueprint import ALL_REVIEWED, Blueprint, blueprint_section, blueprint_sha256
from .geometry import geometries

# The local.yaml key of the folder the builds go under, the folder in it the review tool writes the reviews to, the build's
# own files, and the folder a build is made in before it is renamed into place.
PROCESSED_KEY = "PROCESSED_LAB_DATA"
REVIEW_DIR = "review"
MANIFEST = "manifest.json"
BUILDING = ".building"

# The review keys a build records as its stamp, the code version it writes, and the reasons and warning it gives.
STAMP_KEYS = ("reviewed_at", "converter_manifest_timestamp")
CODE_VERSION = "blocks {} {}"
NO_REVIEW = "no review file"
NOT_TRANSFORMED = "not in the transformed folder"
OTHER_RULES = "reviewed under other rules"
UNKNOWN, DIRTY = "unknown", "+dirty"


def now():
    """
    The current time in UTC to the second.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit():
    """
    The short commit of the repository with +dirty when a tracked file has uncommitted changes, unknown when git cannot say.
    """
    def git(*arguments):
        return subprocess.run(["git", "-C", str(REPO_ROOT), *arguments], capture_output=True, text=True, check=True).stdout.strip()
    try:
        commit, changes = git("rev-parse", "--short", "HEAD"), git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.CalledProcessError):
        return UNKNOWN
    return commit + (DIRTY if changes else "")


def sha256_of(path):
    """
    The sha256 of a file's bytes as hex.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def data_id(root):
    """
    The sha256 over blocks.csv and every block parquet in block id order, each file's name and its bytes' sha256: what the blocks are, whatever folder or day built them.
    """
    files = [root / io.BLOCKS_CSV] + sorted((root / io.BLOCKS_DIR).glob(f"*{io.PARQUET}"), key=lambda path: path.stem)
    found = hashlib.sha256()
    for path in files:
        if path.is_file():
            found.update(f"{path.relative_to(root).as_posix()} {sha256_of(path)}\n".encode())
    return found.hexdigest()


def warnings_of(made, review, rules):
    """
    The session's warnings, with one more when its review was saved under rules other than the build's (compared as json).
    """
    other = review.get("rules") is not None and review["rules"] != json.loads(json.dumps(rules))
    return made["warnings"] + ([OTHER_RULES] if other else [])


def build_session(sid, review, offset, transformed, out, rules, settings, code_version):
    """
    Build and write one reviewed session, an excluded one with no blocks, a block with a problem listed in failed and not written, and say how many blocks were written and which failed.
    """
    engine = BlockEngine()
    if review["excluded"]:
        made = {"blocks": [], "frame": None, "warnings": []}
    else:
        arrays = io.session(transformed, sid)
        made = engine.blocks(arrays, review, geometries(arrays["epochs"], rules, offset), rules)
    kept, failed, windows = [], [], {}
    for block in made["blocks"]:
        block_id = block["row"]["block_id"]
        if block["problems"]:
            failed.append({"block_id": block_id, "problems": block["problems"]})
            continue
        kept.append({"row": block["row"], "arrays": block["arrays"]})
        found = engine.windows(block, settings, rules)
        windows[block_id] = {"count": found["count"], "verdict": found["verdict"]}
    metadata = {"rules": rules, "start_offset_m": offset, "settings": settings, "review_stamp": {key: review.get(key) for key in STAMP_KEYS},
                "code_version": code_version, "built_at": now(), "windows": windows, "frame": made["frame"], "excluded": review["excluded"],
                "warnings": warnings_of(made, review, rules), "failed": failed}
    io.write_session(out, sid, kept, metadata)
    return {"built": len(kept), "failed": failed}


def build(blueprint, blueprint_sha256, transformed, reviews, out):
    """
    Build every session of the blueprint into the folder out, which must not exist, and write its manifest: the blueprint, the data id, the transformed stamp, the code, when, and the sessions built, failed, skipped and excluded.
    """
    rules, settings = blueprint.resolved_rules(), blueprint.resolved_settings()
    funnel = BlockEngine().funnel(io.sessions(transformed), rules)
    sids = io.reviews(reviews) if blueprint.sessions == ALL_REVIEWED else list(blueprint.sessions)
    code_version = CODE_VERSION.format(VERSION, git_commit())
    out.mkdir(parents=True)
    built, failed, skipped, excluded, errors = {}, {}, {}, [], {}
    for sid in sids:
        review = io.review(reviews, sid)
        if review is None:
            skipped[sid] = NO_REVIEW
        elif not review["excluded"] and not funnel.get(sid, {}).get("in_dataset"):
            skipped[sid] = funnel[sid]["reason"] if sid in funnel else NOT_TRANSFORMED
        else:
            try:
                result = build_session(sid, review, blueprint.start_offset(sid, review), transformed, out, rules, settings, code_version)
            except (OSError, ValueError, KeyError) as error:
                errors[sid] = f"{type(error).__name__}: {error}"
                print(f"{sid}  error  {errors[sid]}")
                continue
            built[sid] = result["built"]
            if result["failed"]:
                failed[sid] = result["failed"]
            if review["excluded"]:
                excluded.append(sid)
            print(f"{sid}  {'excluded' if review['excluded'] else 'built'}  {result['built']} blocks, {len(result['failed'])} failed")
            continue
        print(f"{sid}  skipped  {skipped[sid]}")
    manifest = {
        "blueprint": {"name": blueprint.name, "sha256": blueprint_sha256, "format_version": blueprint.format_version},
        "data_id": data_id(out), "transformed_stamp": io.stamp(transformed), "git_commit": git_commit(),
        "package_version": __version__, "engine_version": VERSION, "built_at": now(),
        "counts": {"sessions_built": len(built), "blocks_written": sum(built.values()), "failed_blocks": sum(len(f) for f in failed.values()),
                   "skipped_sessions": len(skipped), "excluded_sessions": len(excluded), "errors": len(errors)},
        "failed": failed, "skipped": skipped, "excluded": excluded, "errors": errors,
    }
    io.write_json(manifest, out / MANIFEST)
    return manifest


def same_table(a, b):
    """
    Whether two Arrow tables have the same schema and the same values column by column, NaN equal to NaN.
    """
    if a.schema != b.schema:
        return False
    for name in a.column_names:
        x, y = a.column(name).to_numpy(zero_copy_only=False), b.column(name).to_numpy(zero_copy_only=False)
        if not np.array_equal(x, y, equal_nan=x.dtype.kind == "f"):
            return False
    return True


def compare(built, other):
    """
    The blocks only one folder holds, the blocks whose parquet differs and blocks.csv when it differs, by content, so a pyarrow version that writes other bytes changes nothing.
    """
    blocks = {root: {path.stem for path in (root / io.BLOCKS_DIR).glob(f"*{io.PARQUET}")} for root in (built, other)}
    found = [f"only in {root}: {block_id}" for root, rest in ((built, other), (other, built)) for block_id in sorted(blocks[root] - blocks[rest])]
    found += [f"differs: {block_id}" for block_id in sorted(blocks[built] & blocks[other])
              if not same_table(*(pq.read_table(root / io.BLOCKS_DIR / f"{block_id}{io.PARQUET}") for root in (built, other)))]
    if not same_table(pacsv.read_csv(built / io.BLOCKS_CSV), pacsv.read_csv(other / io.BLOCKS_CSV)):
        found.append(f"differs: {io.BLOCKS_CSV}")
    return found


def refuse(message):
    """
    Print a configuration problem to stderr and exit 2.
    """
    print(f"build-blocks: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_args(argv):
    """
    The command line: --blueprint NAME (an entry of the blueprints section of configs/project.yaml), --replace and --compare FOLDER.
    """
    parser = argparse.ArgumentParser(prog="build-blocks", description="Build the blocks a blueprint names into PROCESSED_LAB_DATA/<name>/.")
    parser.add_argument("--blueprint", required=True, metavar="NAME", help="a blueprint in the blueprints section of configs/project.yaml")
    parser.add_argument("--replace", action="store_true", help="replace an earlier build of this blueprint")
    parser.add_argument("--compare", type=Path, metavar="FOLDER", help="after the build, compare its blocks and blocks.csv by content with FOLDER (the review tool's)")
    return parser.parse_args(argv)


def folders(blueprint, config):
    """
    The transformed folder, the reviews folder (the blueprint's, else PROCESSED_LAB_DATA/review) and the build's folder, or exit 2 naming what is wrong.
    """
    try:
        transformed, processed = (local_path(key, config).resolve() for key in (blueprint.transformed, PROCESSED_KEY))
    except KeyError as error:
        refuse(error.args[0])
    out = processed / blueprint.name
    reviews = processed / REVIEW_DIR if blueprint.reviews is None else (REPO_ROOT / Path(blueprint.reviews).expanduser()).resolve()
    repo = REPO_ROOT.resolve()
    if not transformed.is_dir():
        refuse(f"{blueprint.transformed} {transformed} is not a folder")
    if not reviews.is_dir():
        refuse(f"reviews {reviews} is not a folder")
    if out == repo or repo in out.parents:
        refuse(f"{PROCESSED_KEY} {out.parent} is the repository {repo} or inside it")
    if out == reviews:
        refuse(f"the build's folder {out} is the reviews folder")
    return transformed, reviews, out


def main(argv=None, config=None, project=None):
    """
    Read the blueprint from the project config (or the yaml at project) and local.yaml, build into a temporary folder beside the build's folder and rename it into place, print the summary, exit 1 when the data id is not the expected one or a compared block differs and 2 on a configuration problem.
    """
    args = parse_args(argv)
    try:
        raw = blueprint_section(args.blueprint, project)
    except KeyError as error:
        refuse(error.args[0])
    try:
        blueprint = Blueprint.model_validate(raw)
    except ValidationError as error:
        refuse(f"{args.blueprint}: {error}")
    transformed, reviews, out = folders(blueprint, local_config() if config is None else config)
    if args.compare is not None and not (args.compare / io.BLOCKS_CSV).is_file():
        refuse(f"no {io.BLOCKS_CSV} in {args.compare} to compare with")
    if out.exists() and not args.replace:
        refuse(f"{out} exists, pass --replace to build it again")
    staging = out.with_name(out.name + BUILDING)
    if staging.exists():
        shutil.rmtree(staging)
    # The manifest records the sha256 of the blueprint's own section in canonical json, not of the project file's bytes.
    manifest = build(blueprint, blueprint_sha256(raw), transformed, reviews, staging)
    if out.exists():
        shutil.rmtree(out)
    staging.rename(out)
    counts = manifest["counts"]
    print(f"{counts['sessions_built']} sessions built, {counts['blocks_written']} blocks written, {counts['failed_blocks']} failed, "
          f"{counts['skipped_sessions']} skipped, {counts['excluded_sessions']} excluded, {counts['errors']} errors")
    print(f"data id {manifest['data_id']} in {out}")
    status = 0
    expected = blueprint.expected_data_id
    if expected is not None and expected != manifest["data_id"]:
        print(f"build-blocks: data id differs from the blueprint's expected {expected}", file=sys.stderr)
        status = 1
    if args.compare is not None:
        differs = compare(out, args.compare)
        print("\n".join(differs) if differs else f"{counts['blocks_written']} blocks and {io.BLOCKS_CSV} equal to {args.compare}")
        status = 1 if differs else status
    return status


if __name__ == "__main__":
    sys.exit(main())
