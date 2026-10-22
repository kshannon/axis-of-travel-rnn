"""
One-off sweep that chose the loop's room, corridor width and steering strength: the agent alone, no cells, run once.
"""

import numpy as np

from .config import MAX_STALL_S, MIN_ALONG_FRACTION, MIN_DIRECTION_S, PILOT, REPEL_FRACTION, STALL_SPEED
from .worlds import along_axis, cell_seconds, in_hole, longest_run, run_agent

# The grid. Steered rows take every box, width and drift ratio, with wall_repel_distance = width * REPEL_FRACTION (1/3).
BOXES = ((1.0, 1.0), (2.0, 1.0))  # m, x by y; the first is the reference
WIDTHS = (0.25, 0.15, 0.10, 0.076)  # m; the first is the stock reference
RATIOS = (2, 5, 10)  # drift_to_random_strength_ratio
COMPARISON_REPEL = 0.1  # m, RatInABox's default wall_repel_distance, run for the widest corridor only
N_SESSIONS = 5  # of PILOT["session_s"] seconds each
SEED_BASE = 5000  # session i has seed SEED_BASE + i in every row; no other part of the pilot uses these seeds

# The selection rule, written before the first run and about data quality only; no axis measure is looked at.
# A steered row passes when all of these hold (the stock and comparison rows are printed for reference and are never
# chosen). MIN_ALONG_FRACTION, MAX_STALL_S and MIN_DIRECTION_S are the pilot's section 1 limits in config.py.
#   a  the share of moving steps inside corridor segments, corners excluded, heading within ALONG_DEG of the corridor
#      direction is at least MIN_ALONG_FRACTION
#   b  the longest time below STALL_SPEED is at most MAX_STALL_S
#   c  the mean speed is within SPEED_RANGE
#   d  fewer than MAX_REVERSAL_SHARE of the turn rates are at the reversal cap, |turn rate| above
#      REVERSAL_FRACTION * pi / dt, where a full reversal in one step sits
#   e  in at least MIN_SESSION_SHARE of the sessions every one of the 8 segment and direction cells has at least
#      MIN_DIRECTION_S
# Of the rows that pass, the widest corridor is chosen, then the lowest drift ratio, then the 2.0 by 1.0 box. If none
# passes, nothing is relaxed: the two rows that pass the most criteria (ties by criterion a) are reported.
SPEED_RANGE = (0.12, 0.18)  # m/s
MAX_REVERSAL_SHARE = 0.02
REVERSAL_FRACTION = 0.9
MIN_SESSION_SHARE = 0.8


def rows_to_run():
    """
    (kind, box, width, ratio, repel) for the stock rows, then the steered rows, then the comparison rows.
    """
    stock = [("stock", box, width, None, None) for box in BOXES for width in WIDTHS]
    steered = [("steered", box, width, ratio, width * REPEL_FRACTION)
               for box in BOXES for width in WIDTHS for ratio in RATIOS]
    comparison = [("repel 0.1", box, WIDTHS[0], ratio, COMPARISON_REPEL) for box in BOXES for ratio in RATIOS]
    return stock + steered + comparison


def measure(kind, box, width, ratio, repel):
    """
    Run N_SESSIONS sessions of the agent alone and return the row: the criteria values and whether each is met.
    """
    cfg = PILOT
    paths = [run_agent(cfg, "loop", SEED_BASE + i, box, width, repel, ratio) for i in range(N_SESSIONS)]
    keys = ("pos", "heading", "speed", "turn_rate")
    pos, heading, speed, turn = (np.concatenate([p[key] for p in paths]) for key in keys)
    along = along_axis(pos, heading, speed, box, width)[0]
    stall = max(longest_run(p["speed"] < STALL_SPEED) for p in paths) * cfg["dt"]
    reversed_share = np.mean(np.abs(turn) > REVERSAL_FRACTION * np.pi / cfg["dt"])
    cells_ok = sum(cell_seconds(p["pos"], p["heading"], p["speed"], cfg["dt"], box, width).min() >= MIN_DIRECTION_S
                   for p in paths)
    met = (along >= MIN_ALONG_FRACTION, stall <= MAX_STALL_S, SPEED_RANGE[0] <= speed.mean() <= SPEED_RANGE[1],
           reversed_share < MAX_REVERSAL_SHARE, cells_ok >= MIN_SESSION_SHARE * N_SESSIONS)
    bad = int(in_hole(pos, box, width).sum() + ((pos < 0) | (pos > np.array(box))).any(axis=1).sum())
    return {"kind": kind, "box": box, "width": width, "ratio": ratio, "repel": repel, "along": along, "stall": stall,
            "speed": speed.mean(), "reversed": reversed_share, "cells_ok": cells_ok, "met": met, "bad": bad}


def table_row(r):
    """
    One markdown table row; a criterion that fails is marked with a star.
    """
    values = (f"{r['along']:.2f}", f"{r['stall']:.1f}", f"{r['speed']:.3f}", f"{100 * r['reversed']:.1f}",
              f"{r['cells_ok']}/{N_SESSIONS}")
    cells = [f"{v}{'' if ok else '*'}" for v, ok in zip(values, r["met"])]
    ratio = "-" if r["ratio"] is None else r["ratio"]
    repel = "0.1 default" if r["repel"] is None else f"{r['repel']:.3f}"
    verdict = "PASS" if all(r["met"]) else f"{sum(r['met'])}/5"
    return (f"| {r['kind']} | {r['box'][0]:.1f}x{r['box'][1]:.1f} | {r['width']} | {repel} | {ratio} | "
            + " | ".join(cells) + f" | {r['bad']} | {verdict} |")


def choose(rows):
    """
    The passing steered row that is widest, then has the lowest ratio, then the largest box; None when none passes.
    """
    passing = [r for r in rows if r["kind"] == "steered" and all(r["met"])]
    return min(passing, key=lambda r: (-r["width"], r["ratio"], -r["box"][0]), default=None)


def main():
    """
    Run every row, printing the table as it fills, then the chosen row or the two best.
    """
    print("| row | box (m) | corridor (m) | repel (m) | ratio | a along | b stall (s) | c speed (m/s) | d reversed (%) "
          "| e sessions | bad steps | met |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = []
    for spec in rows_to_run():
        rows.append(measure(*spec))
        print(table_row(rows[-1]), flush=True)
    print("\n* marks a criterion that is not met. bad steps: positions in the hole or outside the room.")
    chosen = choose(rows)
    if chosen is not None:
        print(f"\nchosen: box {chosen['box']}, corridor {chosen['width']}, drift ratio {chosen['ratio']}, "
              f"repel {chosen['repel']:.3f}")
        return
    steered = [r for r in rows if r["kind"] == "steered"]
    best = sorted(steered, key=lambda r: (-sum(r["met"]), -r["along"]))[:2]
    print("\nnothing passes; the two best steered rows:")
    for r in best:
        print(table_row(r))


if __name__ == "__main__":
    main()
