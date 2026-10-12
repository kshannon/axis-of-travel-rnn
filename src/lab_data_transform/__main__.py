"""
Convert the lab's MATLAB files into CSV tables and Parquet frames, run as pixi run transform-lab.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from proj_helpers import paths
from proj_helpers.paths import repo_root

from .transform_helpers import readers
from .transform_helpers.orchestrator import Orchestrator


def parse_args(argv):
    """
    The command line: --dry-run, --only PREFIX and --sample N, where N is at least 1.
    """
    parser = argparse.ArgumentParser(
        prog="lab_data_transform", description="Convert the lab's MATLAB files to CSV tables and Parquet frames.")
    parser.add_argument("--dry-run", action="store_true", help="print what would be converted and written, then stop")
    parser.add_argument("--only", metavar="PREFIX",
                        help="sessions whose id is PREFIX or continues it after an underscore")
    parser.add_argument("--sample", type=int, metavar="N", help="the first N sessions per subject in recording order")
    args = parser.parse_args(argv)
    if args.sample is not None and args.sample < 1:
        parser.error("--sample must be at least 1")
    return args


def refuse(message):
    """
    Print a configuration problem to stderr and exit 2.
    """
    print(f"lab_data_transform: {message}", file=sys.stderr)
    raise SystemExit(2)


def roots(config):
    """
    The resolved lab data folder and the Orchestrator on the resolved output folder, or exit 2 naming what is wrong.
    """
    for key in ("LAB_DATA", "TRANSFORMED_LAB_DATA"):
        if not config.get(key):
            refuse(f"{paths.LOCAL_CONFIG} has no {key}")
    lab = Path(str(config["LAB_DATA"])).expanduser().resolve()
    root = Path(str(config["TRANSFORMED_LAB_DATA"])).expanduser().resolve()
    if not lab.is_dir():
        refuse(f"LAB_DATA {lab} is not a folder")
    if root == lab or lab in root.parents:
        refuse(f"TRANSFORMED_LAB_DATA {root} is the lab data or inside it")
    if root in lab.parents:
        refuse(f"TRANSFORMED_LAB_DATA {root} contains the lab data {lab}")
    repo = repo_root().resolve()
    if root == repo or repo in root.parents:
        refuse(f"TRANSFORMED_LAB_DATA {root} is the repository {repo} or inside it")
    return lab, Orchestrator(root)


def dry_run(sessions, skipped, orchestrator):
    """
    Print the sessions that would convert, the skipped names, the counts per group and the files that would be written.
    """
    print("dry run, nothing is written")
    print(f"sessions to convert ({len(sessions)}):")
    for session in sessions:
        print(f"  {session.session_id}  {session.group}")
    print(f"skipped ({len(skipped)}):")
    for name, reason in skipped:
        print(f"  {name}: {reason}")
    print("sessions per group:")
    for group, count in sorted(Counter(session.group for session in sessions).items()):
        print(f"  {group}: {count}")
    print(f"files to write under {orchestrator.root}:")
    for name in orchestrator.planned_files(sessions):
        print(f"  {name}")


def summarize(outcomes, skipped):
    """
    Print how many sessions were written and failed, the failed ids and the skipped names with their reasons.
    """
    failed = [session_id for session_id, outcome in outcomes.items() if outcome == "failed"]
    print(f"{len(outcomes) - len(failed)} written, {len(failed)} failed, {len(skipped)} skipped")
    for session_id in failed:
        print(f"  failed: {session_id}")
    for name, reason in skipped:
        print(f"  skipped: {name} ({reason})")


def main(argv=None, config=None):
    """
    Run the converter: 0 when every selected session was written, 1 when any failed, SystemExit 2 for a bad setup.
    """
    args = parse_args(argv)
    lab, orchestrator = roots(paths.local_config() if config is None else config)
    found, skipped = readers.catalog(lab)
    sessions = readers.select(found, args.only, args.sample)
    if args.dry_run:
        dry_run(sessions, skipped, orchestrator)
        return 0
    outcomes = orchestrator.run(sessions, skipped, {"only": args.only, "sample": args.sample})
    summarize(outcomes, skipped)
    return 1 if "failed" in outcomes.values() else 0


if __name__ == "__main__":
    sys.exit(main())
