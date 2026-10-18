"""
Serve the API on the backend tests' synthetic transformed folder and an empty processed folder for the Playwright flows, everything rebuilt under --root.
"""

import argparse
import shutil
import sys
from pathlib import Path

import uvicorn
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "tests"))

from fixtures import write_transformed  # noqa: E402
from ratreplay_api.app import create_app  # noqa: E402

HOST = "127.0.0.1"


def main(argv=None):
    """
    Rebuild the synthetic transformed folder and an empty processed folder under --root with a local.yaml there naming them, then serve the built frontend and the API on that config, so nothing outside --root is touched and the repository's configs/local.yaml is never read.
    """
    parser = argparse.ArgumentParser(description="Serve RatReplay on synthetic data.")
    parser.add_argument("--root", type=Path, required=True, help="the folder rebuilt on every start")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    shutil.rmtree(args.root, ignore_errors=True)
    transformed, processed = args.root / "transformed", args.root / "processed"
    write_transformed(transformed)
    processed.mkdir()
    local = args.root / "local.yaml"
    local.write_text(yaml.safe_dump({"TRANSFORMED_LAB_DATA": str(transformed), "PROCESSED_LAB_DATA": str(processed)}))
    app = create_app(config_path=local)
    uvicorn.run(app, host=HOST, port=args.port)


if __name__ == "__main__":
    main()
