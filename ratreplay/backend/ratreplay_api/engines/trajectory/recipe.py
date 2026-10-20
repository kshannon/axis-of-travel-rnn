"""
The recipe of a set of built blocks per kind: the statistics the generator fits and the numbers real and synthetic blocks are compared on.
"""

import numpy as np

from .cuts import runs_of
from .kinematics import kinematics
from .labels import ARENA, DWELL, FORAGE, OUTBOUND, PAUSE, RETURN

# The quantiles every distribution is summarised by, the phases whose share of frames each kind reports, the two dwell
# sites of the track, and the side of the occupancy grid over the arena's room.
QUANTILES = {"q05": 5, "q25": 25, "q50": 50, "q75": 75, "q95": 95}
TRACK_PHASES = (OUTBOUND, DWELL, RETURN, PAUSE)
ARENA_PHASES = (FORAGE, PAUSE)
START, GOAL = "start", "goal"
GRID = 10
SECONDS_PER_MINUTE = 60.0

# The speed variation: the share of a stretch's frames cut from each end before the standard deviation over the mean of
# its speed is taken, and the shortest running stretch of the arena that counts. The tracking noise: the second
# difference of a position with independent noise of spread s has spread s times sqrt(6).
CV_EDGE_SHARE = 0.2
MIN_RUNNING_S = 1.0
SECOND_DIFFERENCE_GAIN = np.sqrt(6.0)

# The heading against speed: the edges of the speed bins in m/s, the last open above, and the least speed of a frame in
# the regression of the heading's lag on the turn rate. Both measure the heading against the Savitzky-Golay direction of
# motion, not the step to the next frame: with tracking noise the raw step's direction is noise at a walk and its turn
# rate is noise at any speed, which would swamp the spread and dilute the lag toward zero.
HEADING_SPEED_EDGES = (0.0, 0.05, 0.1, 0.17, 0.25, 0.35, 0.5)
LAG_MIN_SPEED = 0.2

# A pause on the track is the phase the labels paint inside a run. The labels paint no pause in the arena (every frame
# forages), so an arena pause is a still stretch: speed under the running floor for over pause_min_s, the rule the
# session's stops use. A frame runs when its smoothed speed and its own step to the next frame are both at or over the
# running floor, so a zero step (common on pixel quantised tracking) gives no direction of motion.


def quantiles(values):
    """
    The quantile dict of the finite values, every entry null when there are none.
    """
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {key: None for key in (*QUANTILES, "mean")}
    found = {key: float(np.percentile(values, q)) for key, q in QUANTILES.items()}
    return {**found, "mean": float(values.mean())}


def circular_std(angles):
    """
    The circular standard deviation of the angles in radians, sqrt(-2 ln R) with R the mean resultant length, null when there are none.
    """
    if len(angles) == 0:
        return None
    resultant = np.clip(np.hypot(np.mean(np.cos(angles)), np.mean(np.sin(angles))), np.finfo(float).tiny, 1.0)
    return float(np.sqrt(-2.0 * np.log(resultant)))


def gathered(blocks, name):
    """
    One array over every block, the named column of each in order.
    """
    return np.concatenate([b["arrays"][name] for b in blocks])


def stretch_seconds(mask, rate_hz):
    """
    The duration in seconds of every stretch where the mask is true.
    """
    return [(stop - first) / rate_hz for first, stop in runs_of(mask)]


def still_stretches(block, rules):
    """
    True on every frame of a stretch with speed under running_floor_m_per_s for over pause_min_s, a missing speed not still.
    """
    slow = np.nan_to_num(block["arrays"]["speed"], nan=np.inf) < rules["running_floor_m_per_s"]
    still = np.zeros(len(slow), bool)
    for first, stop in runs_of(slow):
        if stop - first > rules["pause_min_s"] * block["row"]["rate_hz"]:
            still[first:stop] = True
    return still


def heading_residuals(block, rules):
    """
    Heading minus the direction of motion over the block's running frames with a finite heading, the direction from each frame's step to the next, a frame running when its speed and its step are both at or over the running floor.
    """
    arrays, floor = block["arrays"], rules["running_floor_m_per_s"]
    x, y, heading, speed = (arrays[name][:-1] for name in ("x", "y", "heading", "speed"))
    dx, dy = np.diff(arrays["x"]), np.diff(arrays["y"])
    direction = np.arctan2(dy, dx)
    running = np.isfinite(speed) & (speed >= floor) & (np.hypot(dx, dy) * block["row"]["rate_hz"] >= floor) & np.isfinite(heading)
    return np.angle(np.exp(1j * (heading[running] - direction[running])))


def motion_residuals(block, rules):
    """
    Per frame: heading minus the Savitzky-Golay direction of motion (wrapped), the speed, the turn rate of that direction, and true where the heading, the direction and the speed are all finite.
    """
    arrays, rate_hz = block["arrays"], block["row"]["rate_hz"]
    no_breaks = np.zeros(len(arrays["x"]), bool)
    _, motion, _ = kinematics(arrays["x"], arrays["y"], arrays["heading"], no_breaks, rate_hz, rules)
    _, _, turn = kinematics(arrays["x"], arrays["y"], motion, no_breaks, rate_hz, rules)
    residual = np.angle(np.exp(1j * (arrays["heading"] - motion)))
    return residual, arrays["speed"], turn, np.isfinite(residual) & np.isfinite(arrays["speed"])


def heading_by_speed(blocks, rules):
    """
    Per speed bin over every frame with a heading, a direction of motion and a speed: the median speed, the circular spread of heading minus the direction of motion and the frame count, the speed and spread null in an empty bin.
    """
    found = [motion_residuals(b, rules) for b in blocks]
    residual = np.concatenate([r[defined] for r, _, _, defined in found])
    speed = np.concatenate([s[defined] for _, s, _, defined in found])
    at = np.digitize(speed, HEADING_SPEED_EDGES[1:])
    rows = []
    for k in range(len(HEADING_SPEED_EDGES)):
        here = at == k
        rows.append({"speed_m_per_s": float(np.median(speed[here])) if here.any() else None,
                     "spread_rad": circular_std(residual[here]) if here.any() else None, "n": int(here.sum())})
    return rows


def heading_lag(blocks, rules):
    """
    Minus the slope of heading minus the direction of motion regressed on the turn rate of that direction over frames at or over LAG_MIN_SPEED, in seconds, null with under three frames or no spread in the turn rate.
    """
    residuals, turns = [], []
    for b in blocks:
        residual, speed, turn, defined = motion_residuals(b, rules)
        here = defined & np.isfinite(turn) & (speed >= LAG_MIN_SPEED)
        residuals.append(residual[here])
        turns.append(turn[here])
    residual, turn = np.concatenate(residuals), np.concatenate(turns)
    if residual.size < 3 or np.ptp(turn) == 0:
        return None
    return float(-np.polyfit(turn, residual, 1)[0])


def middle_cv(speed):
    """
    The standard deviation over the mean of the finite speeds of a stretch with CV_EDGE_SHARE of its frames cut from each end, null when none are left or the mean is zero.
    """
    cut = round(CV_EDGE_SHARE * len(speed))
    middle = speed[cut:len(speed) - cut]
    middle = middle[np.isfinite(middle)]
    if middle.size == 0 or middle.mean() == 0:
        return None
    return float(middle.std() / middle.mean())


def median_or_none(values):
    """
    The median of the values that are not null, null when there are none.
    """
    values = [v for v in values if v is not None]
    return float(np.median(values)) if values else None


def tracking_noise(blocks):
    """
    The spread of the second difference of x and of y pooled over every block's frames with finite positions, over sqrt(6): the per frame noise of a position whose path is smooth.
    """
    second = np.concatenate([np.diff(b["arrays"][name], 2) for b in blocks for name in ("x", "y")])
    second = second[np.isfinite(second)]
    return float(second.std() / SECOND_DIFFERENCE_GAIN) if second.size else None


def centreline_distance(x, y, centerline):
    """
    The distance of every position to the nearest centreline segment.
    """
    points = np.column_stack([x, y])
    nearest = np.full(len(points), np.inf)
    for seg in centerline:
        p0, p1 = np.array(seg["p0"], float), np.array(seg["p1"], float)
        along = p1 - p0
        t = np.clip((points - p0) @ along / (along @ along), 0.0, 1.0)
        nearest = np.minimum(nearest, np.hypot(*(points - p0 - t[:, None] * along).T))
    return nearest


def phase_share(blocks, phases):
    """
    The share of every frame in each of the phases, keyed by phase.
    """
    phase = gathered(blocks, "phase")
    return {name: float(np.mean(phase == name)) for name in phases}


def run_stretches(block):
    """
    The (first, stop, path_id) of every stretch of a constant positive run value in the block, in frame order.
    """
    run, path_id = block["arrays"]["run"], block["arrays"]["path_id"]
    found = []
    for number in np.unique(run[run > 0]):
        found += [(first, stop, int(path_id[first])) for first, stop in runs_of(run == number)]
    return sorted(found)


def dwell_site(block, first, rules):
    """
    Which site a dwell starting at this index is at, by the run before it: start after a return run, goal after an outbound run, null when no run comes before.
    """
    run, path_id = block["arrays"]["run"], block["arrays"]["path_id"]
    before = np.flatnonzero(run[:first] > 0)
    if before.size == 0:
        return None
    path = int(path_id[before[-1]])
    return GOAL if path in rules["outbound_paths"] else START if path in rules["return_paths"] else None


def boundary_distance(x, y, boundary):
    """
    The distance of every position to the nearest edge of the boundary polygon.
    """
    p0 = np.array(boundary, float)
    p1 = np.roll(p0, -1, axis=0)
    along = p1 - p0
    points = np.column_stack([x, y])
    t = np.clip(((points[:, None, :] - p0) * along).sum(axis=2) / (along * along).sum(axis=1), 0.0, 1.0)
    nearest = p0 + t[:, :, None] * along
    return np.hypot(*(points[:, None, :] - nearest).transpose(2, 0, 1)).min(axis=1)


def common(blocks, paused, rules):
    """
    The counts, the speed and turn rate distributions, the still fraction, the heading spread (in all, by speed and its lag behind turns), the tracking noise and the pauses, shared by both kinds, the pauses from the mask paused gives per block.
    """
    seconds = sum(b["row"]["duration_s"] for b in blocks)
    speed, turn_rate = gathered(blocks, "speed"), gathered(blocks, "turn_rate")
    finite_speed = speed[np.isfinite(speed)]
    pauses = [s for b in blocks for s in stretch_seconds(paused(b), b["row"]["rate_hz"])]
    return {
        "counts": {"blocks": len(blocks), "frames": int(sum(len(b["arrays"]["speed"]) for b in blocks)), "seconds": float(seconds)},
        "speed": quantiles(speed),
        "turn_rate": quantiles(turn_rate),
        "turn_rate_abs_mean": float(np.nanmean(np.abs(turn_rate))) if np.isfinite(turn_rate).any() else None,
        "still_fraction": float(np.mean(finite_speed < rules["running_floor_m_per_s"])) if finite_speed.size else None,
        "heading_spread_rad": circular_std(np.concatenate([heading_residuals(b, rules) for b in blocks])),
        "heading_spread_by_speed": heading_by_speed(blocks, rules),
        "heading_lag_s": heading_lag(blocks, rules),
        "tracking_noise_m": tracking_noise(blocks),
        "pauses": {"per_min": len(pauses) / (seconds / SECONDS_PER_MINUTE), "duration_s": quantiles(pauses)},
    }


def track(blocks, environments, rules):
    """
    The track's additions: run durations per path, the speed variation within a run (the median over runs), the distance from the centreline over running frames, dwell durations per site, trips per minute, the share of outbound runs per goal and the phase shares.
    """
    seconds = sum(b["row"]["duration_s"] for b in blocks)
    runs, dwells, trips, cvs, lateral = {}, {START: [], GOAL: []}, 0, [], []
    for b in blocks:
        rate_hz, arrays = b["row"]["rate_hz"], b["arrays"]
        for first, stop, path in run_stretches(b):
            runs.setdefault(path, []).append((stop - first) / rate_hz)
            cvs.append(middle_cv(arrays["speed"][first:stop]))
        running = np.nan_to_num(arrays["speed"], nan=-np.inf) >= rules["running_floor_m_per_s"]
        lateral.append(centreline_distance(arrays["x"][running], arrays["y"][running], environments[b["row"]["environment"]]["centerline"]))
        for first, stop in runs_of(b["arrays"]["phase"] == DWELL):
            site = dwell_site(b, first, rules)
            if site is not None:
                dwells[site].append((stop - first) / rate_hz)
        trip = b["arrays"]["trip"]
        trips += len(np.unique(trip[trip > 0]))
    outbound = sum(len(runs.get(path, [])) for path in rules["outbound_paths"])
    return {
        **common(blocks, lambda b: b["arrays"]["phase"] == PAUSE, rules),
        "runs": {str(path): {"count": len(durations), "duration_s": quantiles(durations)} for path, durations in sorted(runs.items())},
        "speed_cv_run": median_or_none(cvs),
        "lateral_m": quantiles(np.concatenate(lateral)),
        "dwell_s": {site: quantiles(durations) for site, durations in dwells.items()},
        "trips_per_min": trips / (seconds / SECONDS_PER_MINUTE),
        "goal_share": {str(path): len(runs.get(path, [])) / outbound if outbound else 0.0 for path in rules["outbound_paths"]},
        "phase_share": phase_share(blocks, TRACK_PHASES),
    }


def arena(blocks, environments, rules):
    """
    The arena's additions: the speed variation within running stretches over MIN_RUNNING_S (the median over stretches), the distance to the environment's boundary, the occupancy over a 10 by 10 grid of its room (rows from the bottom, the first block's room) and the phase shares, the pauses being still stretches.
    """
    distance = np.concatenate([boundary_distance(b["arrays"]["x"], b["arrays"]["y"], environments[b["row"]["environment"]]["boundary"]) for b in blocks])
    x, y = gathered(blocks, "x"), gathered(blocks, "y")
    finite = np.isfinite(x) & np.isfinite(y)
    room = environments[blocks[0]["row"]["environment"]]["room"]
    cvs = []
    for b in blocks:
        speed = b["arrays"]["speed"]
        for first, stop in runs_of(np.nan_to_num(speed, nan=-np.inf) >= rules["running_floor_m_per_s"]):
            if stop - first >= MIN_RUNNING_S * b["row"]["rate_hz"]:
                cvs.append(middle_cv(speed[first:stop]))
    counts, _, _ = np.histogram2d(y[finite], x[finite], bins=GRID, range=[[0.0, room[1]], [0.0, room[0]]])
    return {
        **common(blocks, lambda b: still_stretches(b, rules), rules),
        "environment": blocks[0]["row"]["environment"],
        "speed_cv": median_or_none(cvs),
        "boundary_distance_m": quantiles(distance),
        "occupancy_grid": (counts / counts.sum()).tolist(),
        "phase_share": phase_share(blocks, ARENA_PHASES),
    }


def recipe(blocks, environments, rules):
    """
    The recipe keyed by kind, arena and track, a kind with no blocks absent, every value JSON ready, the geometry of each block's environment given by name.
    """
    found = {}
    for kind, of_kind in ((ARENA, arena), ("track", track)):
        blocks_of_kind = [b for b in blocks if b["row"]["kind"] == kind]
        if blocks_of_kind:
            found[kind] = of_kind(blocks_of_kind, environments, rules)
    return found
