"""
Play the lab trajectories in the browser and save a verdict per run, run as pixi run view-lab-data.
"""

import argparse
import sys
from pathlib import Path

from proj_helpers import paths

from .app import make_app
from .data import MANIFEST

HOST = "127.0.0.1"
PORT = 8050


def parse_args(argv):
    """
    The command line: --transformed to view the converter's frames instead of the processed blocks, and --port.
    """
    parser = argparse.ArgumentParser(
        prog="view_lab_data", description="Play the lab trajectories in the browser and save a verdict per run.")
    parser.add_argument("--transformed", action="store_true",
                        help="view the converter's frames in pixels under TRANSFORMED_LAB_DATA instead of the processed blocks")
    parser.add_argument("--port", type=int, default=PORT, help=f"the localhost port, {PORT} by default")
    return parser.parse_args(argv)


def refuse(message):
    """
    Print a configuration problem to stderr and exit 2.
    """
    print(f"view_lab_data: {message}", file=sys.stderr)
    raise SystemExit(2)


def root(config, transformed):
    """
    The resolved data folder, holding a manifest, or exit 2 naming the key or the problem.
    """
    key = "TRANSFORMED_LAB_DATA" if transformed else "PROCESSED_LAB_DATA"
    if not config.get(key):
        refuse(f"{paths.LOCAL_CONFIG} has no {key}")
    folder = Path(str(config[key])).expanduser().resolve()
    if not folder.is_dir():
        refuse(f"{key} {folder} is not a folder")
    if not (folder / MANIFEST).is_file():
        refuse(f"{key} {folder} has no {MANIFEST}")
    return folder


def main(argv=None, config=None):
    """
    Serve the viewer on localhost until interrupted, SystemExit 2 for a bad setup.
    """
    args = parse_args(argv)
    folder = root(paths.local_config() if config is None else config, args.transformed)
    app = make_app(folder, args.transformed)
    print(f"view_lab_data: {folder} at http://{HOST}:{args.port}")
    app.run(host=HOST, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
