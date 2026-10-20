"""
Serve RatReplay on localhost until interrupted, python -m ratreplay_api.
"""

import argparse

import uvicorn

from .app import create_app

HOST = "127.0.0.1"
PORT = 8060


def main(argv=None):
    """
    Serve the app on HOST at --port.
    """
    parser = argparse.ArgumentParser(prog="ratreplay_api", description="Serve RatReplay on localhost.")
    parser.add_argument("--port", type=int, default=PORT, help=f"the localhost port, {PORT} by default")
    args = parser.parse_args(argv)
    uvicorn.run(create_app(), host=HOST, port=args.port)


if __name__ == "__main__":
    main()
