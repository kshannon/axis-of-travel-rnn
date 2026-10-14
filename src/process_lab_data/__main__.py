"""
Turn the converter's tables into labelled trajectory blocks in metres, run as pixi run process-lab-data.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

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
    parser.add_argument("--list", action="store_true", help="with --dry-run, also print one line per block")
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


def dry_run(blocks, root, listing):
    """
    Print the blocks that would be written per kind, their duration spread, the files to write and, with --list, each block.
    """
    print(f"dry run, nothing is written (gap rule: {select.GAP_LIGHTS} light unfilled over max_gap)")
    print("blocks per kind: count, total s, duration s at min, median, 90th percentile, max")
    for kind in select.EPOCHS:
        seconds = [b["duration_s"] for b in blocks if b["epoch"] == kind]
        if seconds:
            spread = ", ".join(f"{v:.0f}" for v in np.percentile(seconds, [0, 50, 90, 100]))
            print(f"  {kind}: {len(seconds)} blocks, {sum(seconds):.0f} s, durations {spread}")
    if listing:
        print(f"blocks ({len(blocks)}):")
        for b in blocks:
            print(f"  {b['block_id']}  {b['n_frames']} frames  {b['duration_s']:.1f} s")
    print(f"files to write under {root}:")
    for name in BLOCKS_CSV + (MANIFEST,):
        print(f"  {name}")


def main(argv=None, config=None):
    """
    Run the funnel and the dry run: 0, SystemExit 2 for a bad setup. The real run is a stub that exits 3 until T6.
    """
    args = parse_args(argv)
    source, root = roots(paths.local_config() if config is None else config)
    tables = select.read_tables(source)
    epochs, counts = select.funnel(tables, args.only)
    blocks, block_counts = select.blocks_of(source, epochs, tables["sessions"])
    print_counts(counts + block_counts)
    if args.dry_run:
        dry_run(blocks, root, args.list)
        return 0
    print("block writing arrives with T6, nothing is written", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
