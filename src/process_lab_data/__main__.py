"""
Turn the converter's tables into labelled trajectory blocks in metres, run as pixi run process-lab-data.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from proj_helpers import paths
from proj_helpers.paths import repo_root

from . import select

# What a run writes under PROCESSED_LAB_DATA besides the block parquet files: one blocks csv per epoch kind and the
# manifest.
BLOCKS_CSV = tuple(f"{kind}/blocks.csv" for kind in select.EPOCHS)
MANIFEST = "manifest.json"


def parse_args(argv):
    """
    The command line: --dry-run and --only PREFIX.
    """
    parser = argparse.ArgumentParser(
        prog="process_lab_data", description="Turn the converter's tables into trajectory blocks in metres.")
    parser.add_argument("--dry-run", action="store_true", help="print the funnel counts and what would be written, then stop")
    parser.add_argument("--only", metavar="PREFIX",
                        help="sessions whose id is PREFIX or continues it after an underscore")
    return parser.parse_args(argv)


def refuse(message):
    """
    Print a configuration problem to stderr and exit 2.
    """
    print(f"process_lab_data: {message}", file=sys.stderr)
    raise SystemExit(2)


def roots(config):
    """
    The resolved transformed lab data folder and the resolved output folder, or exit 2 naming what is wrong.
    """
    for key in ("TRANSFORMED_LAB_DATA", "PROCESSED_LAB_DATA"):
        if not config.get(key):
            refuse(f"{paths.LOCAL_CONFIG} has no {key}")
    source = Path(str(config["TRANSFORMED_LAB_DATA"])).expanduser().resolve()
    root = Path(str(config["PROCESSED_LAB_DATA"])).expanduser().resolve()
    tables = [f"{name}.csv" for name in select.TABLES]
    if not all((source / name).is_file() for name in tables) or not (source / select.FRAMES).is_dir():
        refuse(f"TRANSFORMED_LAB_DATA {source} is not a folder holding {', '.join(tables)} and a {select.FRAMES} folder")
    if root == source or source in root.parents:
        refuse(f"PROCESSED_LAB_DATA {root} is the transformed lab data or inside it")
    if root in source.parents:
        refuse(f"PROCESSED_LAB_DATA {root} contains the transformed lab data {source}")
    repo = repo_root().resolve()
    if root == repo or repo in root.parents:
        refuse(f"PROCESSED_LAB_DATA {root} is the repository {repo} or inside it")
    return source, root


def print_counts(counts):
    """
    Print the funnel, one line per step in order.
    """
    print("funnel:")
    for step, count in counts:
        print(f"  {step}: {count}")


def dry_run(epochs, root):
    """
    Print the epochs that would become blocks, per kind and one per line, and the files that would be written.
    """
    print("dry run, nothing is written")
    print("epochs that would become blocks per kind:")
    for kind, count in sorted(Counter(e["epoch"] for e in epochs).items()):
        print(f"  {kind}: {count}")
    print(f"epochs that would become blocks ({len(epochs)}):")
    for e in epochs:
        print(f"  {e['session_id']}  {e['epoch']}  {e['duration_s']:.0f} s")
    print(f"files to write under {root}:")
    for name in BLOCKS_CSV + (MANIFEST,):
        print(f"  {name}")


def main(argv=None, config=None):
    """
    Run the funnel and the dry run: 0, SystemExit 2 for a bad setup. The real run is a stub that exits 3 until T6.
    """
    args = parse_args(argv)
    source, root = roots(paths.local_config() if config is None else config)
    epochs, counts = select.funnel(select.read_tables(source), args.only)
    print_counts(counts)
    if args.dry_run:
        dry_run(epochs, root)
        return 0
    print("block writing arrives with T3 and T6, nothing is written", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
