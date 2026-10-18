"""
Write columns.arrow, the Arrow stream the decoder test reads, with the backend's own encoder: pixi run -e ratreplay python make_columns.py
"""

from pathlib import Path

import numpy as np

from ratreplay_api import arrow

ARRAYS = {
    "frame": np.array([10, 11, 12], np.int32),
    "x": np.array([1.5, np.nan, 3.0]),
    "n_lights": np.array([2, 1, 0], np.int8),
    "filled": np.array([True, False, True]),
}

if __name__ == "__main__":
    (Path(__file__).parent / "columns.arrow").write_bytes(arrow.encode(ARRAYS))
