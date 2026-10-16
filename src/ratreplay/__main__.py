"""
RatReplay: replay one session at a time in the browser and save its review, run as pixi run ratreplay.
"""

import argparse
import sys
from pathlib import Path

from proj_helpers import paths

from .app import make_app
from .data import FRAMES, MANIFEST, TABLES

HOST = "127.0.0.1"
PORT = 8050
TRANSFORMED = "TRANSFORMED_LAB_DATA"
PROCESSED = "PROCESSED_LAB_DATA"


def parse_args(argv):
    """
    The command line: --port.
    """
    parser = argparse.ArgumentParser(
        prog="ratreplay", description="Replay one session at a time in the browser and save its review.")
    parser.add_argument("--port", type=int, default=PORT, help=f"the localhost port, {PORT} by default")
    return parser.parse_args(argv)


def refuse(message):
    """
    Print a configuration problem to stderr and exit 2.
    """
    print(f"ratreplay: {message}", file=sys.stderr)
    raise SystemExit(2)


def configured(config, key):
    """
    The folder a config key names, resolved, or exit 2 naming the key.
    """
    if not config.get(key):
        refuse(f"{paths.LOCAL_CONFIG} has no {key}")
    return Path(str(config[key])).expanduser().resolve()


def transformed_root(config):
    """
    The converter's folder, holding the tables, the frames and the manifest, or exit 2 naming the problem.
    """
    folder = configured(config, TRANSFORMED)
    for name in (*(f"{table}.csv" for table in TABLES), FRAMES, MANIFEST):
        if not (folder / name).exists():
            refuse(f"{TRANSFORMED} {folder} has no {name}")
    return folder


def main(argv=None, config=None):
    """
    Serve RatReplay on localhost until interrupted, SystemExit 2 for a bad setup.
    """
    args = parse_args(argv)
    config = paths.local_config() if config is None else config
    transformed, processed = transformed_root(config), configured(config, PROCESSED)
    app = make_app(transformed, processed)
    print(f"ratreplay: {transformed}, reviews under {processed} at http://{HOST}:{args.port}")
    app.run(host=HOST, port=args.port, dev_tools_disable_version_check=True)  # the page then talks to nothing but the Tailwind CDN
    return 0


if __name__ == "__main__":
    sys.exit(main())
