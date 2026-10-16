"""
Write windows.json, the window counts the TypeScript mirror is tested against, with the project's own window_count: pixi run -e ratreplay python make_windows.py
"""

import json
from itertools import product
from pathlib import Path

from axis_of_travel_rnn.windows import DEFAULTS, window_count

RATES_HZ = (30, 60)
BLOCK_SECONDS = (9.5, 10, 40, 40.5, 41.5, 50, 60.5, 79.9, 120, 599.95)
SETTINGS = (DEFAULTS, {**DEFAULTS, "window_s": 5.0, "stride_s": 2.5, "horizon_s": 0.0}, {**DEFAULTS, "window_s": 20.0, "stride_s": 0.1})
KEYS = ("window_s", "stride_s", "horizon_s")

if __name__ == "__main__":
    cases = [{"n_frames": round(seconds * rate), "rate_hz": rate, **{key: settings[key] for key in KEYS},
              "windows": window_count(round(seconds * rate), rate, settings)}
             for rate, seconds, settings in product(RATES_HZ, BLOCK_SECONDS, SETTINGS)]
    lines = ",\n".join(json.dumps(case) for case in cases)
    (Path(__file__).parent / "windows.json").write_text(f"[\n{lines}\n]\n")
