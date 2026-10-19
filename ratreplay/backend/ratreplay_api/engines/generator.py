"""
GeneratorEngine: the one contract for generating synthetic behavior from a recipe.
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.signal import lfilter
from scipy.stats import norm

from ..utilities.errors import Invalid

# The epoch kinds in the order a session holds them, the track's start site, the goals by path id (an assumption to check
# against the lab's numbering) and the return path ids by the side the return runs down. The generator knows the triple T
# alone (these sites and the west side segment) and the circular arena alone (the walk is confined to a disc).
ARENA, TRACK = "arena", "track"
KINDS = (ARENA, TRACK)
START = "start"
GOALS = {1: "g_ww", 2: "g_we", 3: "g_ew", 4: "g_ee"}
RETURN_WEST, RETURN_EAST = 9, 10
WEST_SIDE = "side_w"
CIRCLE = "circle"

# What a synthetic session row says of itself.
SYNTHETIC = "synthetic"
CONDITION = "baseline"

# What the generator refuses: a track or an arena it does not know, and a track recipe it cannot draw a trip from.
NOT_THE_TRIPLE_T = "the generator knows the triple T alone, {name} lacks {what}"
NOT_A_CIRCLE = "the generator's arena walk knows a circle alone, {name} is a {kind}"
NO_GOALS = "the recipe's track has no outbound runs to draw goals from"
NO_DWELLS = "the recipe's track has no dwells at the {site} to draw from"

# The quantile keys of a recipe distribution and the probabilities they sit at.
QUANTILE_KEYS = ("q05", "q25", "q50", "q75", "q95")
PROBABILITIES = (0.05, 0.25, 0.5, 0.75, 0.95)

# Track runs: the raised cosine ramp at each end, the cruise speed noise and its time constant, the lateral wander's time
# constant and its standard deviation as a share of the half corridor width, and how far from a corner the wander fades out.
RAMP_S = 0.5
SPEED_NOISE, SPEED_TAU_S = 0.05, 0.5
WANDER_TAU_S, WANDER_SHARE = 1.0, 0.25
CORNER_TAPER_M = 0.1

# Dwells and pauses: the jitter around the site and its time constant, small and slow so a dwell reads as still under the
# running floor, the seconds over which the heading turns from the way the rat arrived to the way it leaves, and the
# heading's random walk step per frame while still.
DWELL_JITTER_M, DWELL_TAU_S = 0.002, 3.0
DWELL_TURN_S = 1.0
DWELL_HEADING_STEP_RAD = 0.03

# Heading: the time constant of the noise between the heading and the direction of motion (the direction is each frame's
# step to the next, as the recipe measures it), and the smallest spread (so kappa stays finite). A longer time constant
# gives the heading a smaller turn rate for the same spread.
HEADING_TAU_S = 2.0
MIN_SPREAD_RAD = 1e-3

# The arena walk: the time constants of the speed and the turn rate, and the steering toward the centre near the boundary.
ARENA_SPEED_TAU_S, ARENA_TURN_TAU_S = 1.0, 0.2
BOUNDARY_MARGIN_M, STEER_PER_S = 0.1, 3.0


def wrapped(angle):
    """
    An angle in radians wrapped to the interval from minus pi to pi.
    """
    return (angle + np.pi) % (2 * np.pi) - np.pi


def drawn(q, rng):
    """
    One value drawn by inverse transform over the five quantiles of a recipe distribution, the mean unused.
    """
    return float(np.interp(rng.random(), PROBABILITIES, [q[key] for key in QUANTILE_KEYS]))


def series_of(q, z):
    """
    A series with the recipe distribution's quantiles from unit normal values, each mapped through its probability onto the five quantiles and held at the ends, so a correlated normal series keeps its correlation and takes the distribution.
    """
    return np.interp(norm.cdf(z), PROBABILITIES, [q[key] for key in QUANTILE_KEYS])


def ar1(values, tau_frames):
    """
    The values, independent draws, filtered into an AR(1) process with the same stationary spread and this time constant in frames.
    """
    a = np.exp(-1.0 / tau_frames)
    out, _ = lfilter([np.sqrt(1 - a * a)], [1.0, -a], values, zi=[a * values[0]])
    return out


def smooth_ar1(values, tau_frames):
    """
    The values filtered twice into an AR(1) process of this time constant whose steps are smooth as well, scaled back to the stationary spread of the draws, for a position that is to bend and not jitter.
    """
    a = np.exp(-1.0 / tau_frames)
    return ar1(ar1(values, tau_frames), tau_frames) * np.sqrt((1 - a * a) / (1 + a * a))


def to_pixels(x, y, p):
    """
    Room metres to camera pixels, the inverse of the registration's to_room: offset taken off, rotated back, scaled, y negated when flip.
    """
    dx, dy = x - p["offset_m"][0], y - p["offset_m"][1]
    cos, sin = np.cos(-p["rotation_rad"]), np.sin(-p["rotation_rad"])
    u, v = dx * cos - dy * sin, dx * sin + dy * cos
    return u * p["scale_px_per_m"], (-v if p["flip"] else v) * p["scale_px_per_m"]


def heading_noise(n, spread, rate_hz, rng):
    """
    Von Mises draws with kappa one over the spread squared, made slow by an AR(1) filter that keeps their spread.
    """
    kappa = 1.0 / max(spread or 0.0, MIN_SPREAD_RAD) ** 2
    return ar1(rng.vonmises(0.0, kappa, n + 1), HEADING_TAU_S * rate_hz)[1:]


def centreline_graph(geometry):
    """
    The centreline as a graph: node coordinates at the rounded segment endpoints and the reward sites lying on a segment, and edges (i, j, length, segment name).
    """
    nodes, edges = {}, []
    sites = [np.array(p, float) for p in geometry["reward_sites"].values()]
    for seg in geometry["centerline"]:
        p0, p1 = np.array(seg["p0"], float), np.array(seg["p1"], float)
        along = p1 - p0
        inner = [s for s in sites if 0 < (s - p0) @ along < along @ along and abs(along[0] * (s - p0)[1] - along[1] * (s - p0)[0]) < 1e-9]
        chain = [p0, *sorted(inner, key=lambda s: (s - p0) @ along), p1]
        for a, b in zip(chain[:-1], chain[1:]):
            i, j = (nodes.setdefault(tuple(np.round(p, 6)), len(nodes)) for p in (a, b))
            edges.append((i, j, float(np.hypot(*(b - a))), seg["name"]))
    return np.array(list(nodes)), edges


def route(coords, edges, a, b):
    """
    The shortest route over the edges from node a to node b as a list of nodes, Dijkstra over the edge lengths.
    """
    i, j, length = (np.array([e[k] for e in edges]) for k in range(3))
    matrix = coo_matrix((length, (i, j)), shape=(len(coords), len(coords))).tocsr()
    _, previous = dijkstra(matrix, directed=False, indices=a, return_predecessors=True)
    found = [b]
    while found[-1] != a:
        found.append(int(previous[found[-1]]))
    return found[::-1]


def node_of(coords, point):
    """
    The index of the node at the point.
    """
    return int(np.argmin(np.hypot(*(coords - np.array(point)).T)))


def check_track(geometry):
    """
    Invalid unless the track has the start and the four goal sites and the west side segment the routes are named by.
    """
    sites = [name for name in (START, *GOALS.values()) if name not in geometry["reward_sites"]]
    segments = [] if any(seg["name"] == WEST_SIDE for seg in geometry["centerline"]) else [WEST_SIDE]
    if sites or segments:
        raise Invalid(NOT_THE_TRIPLE_T.format(name=geometry["name"], what=", ".join(sites + segments)))


def check_recipe(recipe):
    """
    Invalid unless the track recipe has outbound runs to draw goals from and dwells at both sites to draw from.
    """
    if sum(recipe["goal_share"].values()) == 0:
        raise Invalid(NO_GOALS)
    for site in ("start", "goal"):
        if recipe["dwell_s"][site]["q50"] is None:
            raise Invalid(NO_DWELLS.format(site=site))


def track_routes(geometry):
    """
    Every path id's route as an array of room points: outbound the shortest route from the start to its goal, return the shortest from a goal back over the graph without the outbound routes' edges.
    """
    check_track(geometry)
    coords, edges = centreline_graph(geometry)
    start = node_of(coords, geometry["reward_sites"][START])
    outbound = {pid: route(coords, edges, start, node_of(coords, geometry["reward_sites"][goal])) for pid, goal in GOALS.items()}
    used = {frozenset(pair) for nodes in outbound.values() for pair in zip(nodes[:-1], nodes[1:])}
    perimeter = [e for e in edges if frozenset(e[:2]) not in used]
    names = {frozenset(e[:2]): e[3] for e in edges}
    routes, returns = {pid: coords[nodes] for pid, nodes in outbound.items()}, {}
    for pid, nodes in outbound.items():
        back = route(coords, perimeter, nodes[-1], start)
        west = any(names[frozenset(pair)] == WEST_SIDE for pair in zip(back[:-1], back[1:]))
        returns[pid] = (RETURN_WEST if west else RETURN_EAST, coords[back])
    return routes, returns


def run_duration(recipe, path_id, length, rate_hz, rng):
    """
    A run's duration in seconds drawn from the recipe's run durations for its path (when absent, the length at the recipe's q75 speed), lengthened so its cruise speed stays under the recipe's q95 speed.
    """
    runs, speed = recipe["runs"].get(str(path_id)), recipe["speed"]
    duration = drawn(runs["duration_s"], rng) if runs and runs["duration_s"]["q50"] is not None else length / speed["q75"] + RAMP_S
    return max(duration, length / speed["q95"] + RAMP_S, 2 * RAMP_S + 2.0 / rate_hz)


def run_positions(points, duration, wander, limit, rate_hz, rng):
    """
    The positions of one run along the route's points: a raised cosine speed bell with a little noise covering the route in the duration, the lateral wander clipped to the limit and faded to zero near every node.
    """
    steps = np.diff(points, axis=0)
    lengths = np.hypot(*steps.T)
    edges = np.concatenate(([0.0], np.cumsum(lengths)))
    n = round(duration * rate_hz) + 1
    t = (np.arange(n - 1) + 0.5) / rate_hz
    ramp = np.minimum(np.minimum(t, (n - 1) / rate_hz - t) / RAMP_S, 1.0)
    speed = 0.5 * (1 - np.cos(np.pi * ramp)) * (1 + SPEED_NOISE * ar1(rng.standard_normal(n - 1), SPEED_TAU_S * rate_hz))
    s = np.concatenate(([0.0], np.cumsum(speed)))
    s *= edges[-1] / s[-1]
    at = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, len(steps) - 1)
    unit = steps[at] / lengths[at][:, None]
    taper = np.clip(np.minimum(s - edges[at], edges[at + 1] - s) / CORNER_TAPER_M, 0.0, 1.0)
    offset = np.clip(wander[:n], -limit, limit) * taper
    return points[at] + (s - edges[at])[:, None] * unit + offset[:, None] * np.column_stack([-unit[:, 1], unit[:, 0]])


def step_direction(xy):
    """
    The direction of motion per frame as the recipe measures it, each frame's step to the next, the last frame repeating the one before.
    """
    steps = np.diff(xy, axis=0)
    direction = np.arctan2(steps[:, 1], steps[:, 0])
    return np.concatenate([direction, direction[-1:]])


def dwell_positions(site, n, limit, rate_hz, rng):
    """
    The positions of a dwell: a slow jitter around the site, inside a disc of the limit, faded to the site at both ends.
    """
    jitter = DWELL_JITTER_M * np.column_stack([smooth_ar1(rng.standard_normal(n), DWELL_TAU_S * rate_hz) for _ in range(2)])
    radius = np.hypot(*jitter.T)
    jitter *= (np.minimum(radius, limit) / np.maximum(radius, 1e-12))[:, None]
    return np.array(site) + jitter * np.sin(np.pi * np.arange(1, n + 1) / (n + 1))[:, None]


def track_plan(recipe, geometry, n_frames, rate_hz, rng):
    """
    The track epoch as pieces in order, each ("dwell", site, frames) or ("run", path id, route, duration): trips from the start while they fit, the rest a dwell where the rat stands.
    """
    check_recipe(recipe)
    routes, returns = track_routes(geometry)
    goals = list(GOALS)
    share = np.array([recipe["goal_share"][str(pid)] for pid in goals], float)
    sites, pieces, used = geometry["reward_sites"], [], 0
    site = sites[START]
    while True:
        pid = int(rng.choice(goals, p=share / share.sum()))
        back_pid, back = returns[pid]
        trip = [("dwell", site, max(1, round(drawn(recipe["dwell_s"]["start"], rng) * rate_hz)))]
        trip.append(("run", pid, routes[pid], run_duration(recipe, pid, np.hypot(*np.diff(routes[pid], axis=0).T).sum(), rate_hz, rng)))
        trip.append(("dwell", sites[GOALS[pid]], max(1, round(drawn(recipe["dwell_s"]["goal"], rng) * rate_hz))))
        trip.append(("run", back_pid, back, run_duration(recipe, back_pid, np.hypot(*np.diff(back, axis=0).T).sum(), rate_hz, rng)))
        frames = sum(p[2] if p[0] == "dwell" else round(p[3] * rate_hz) + 1 for p in trip)
        if used + frames > n_frames:
            break
        pieces, used = pieces + trip, used + frames
    return pieces + [("dwell", site, n_frames - used)] if n_frames > used else pieces


def track(recipe, geometry, n_frames, led_half, rate_hz, rng):
    """
    The track epoch's room positions and heading per frame and its runs as (path id, first index, last index).
    """
    limit = max(geometry["params"]["corridor_width"] / 2 - led_half, 0.0)
    wander = WANDER_SHARE * geometry["params"]["corridor_width"] / 2 * smooth_ar1(rng.standard_normal(n_frames), WANDER_TAU_S * rate_hz)
    xy, direction, runs, at = np.zeros((n_frames, 2)), np.full(n_frames, np.nan), [], 0
    for piece in track_plan(recipe, geometry, n_frames, rate_hz, rng):
        if piece[0] == "dwell":
            xy[at:at + piece[2]] = dwell_positions(piece[1], piece[2], limit, rate_hz, rng)
            at += piece[2]
            continue
        found = run_positions(piece[2], piece[3], wander[at:], limit, rate_hz, rng)
        xy[at:at + len(found)], direction[at:at + len(found)] = found, step_direction(found)
        runs.append((piece[1], at, at + len(found) - 1))
        at += len(found)
    heading = direction + heading_noise(n_frames, recipe["heading_spread_rad"], rate_hz, rng)
    return xy, dwell_headings(heading, rate_hz, rng), runs


def dwell_headings(heading, rate_hz, rng):
    """
    The heading with every NaN stretch filled by a random walk that turns from the heading before it to the heading after it along the shorter arc over DWELL_TURN_S and lands on it.
    """
    edges = np.flatnonzero(np.diff(np.concatenate(([False], np.isnan(heading), [False])).astype(np.int8)))
    filled = heading.copy()
    for first, stop in zip(edges[::2], edges[1::2]):
        n = stop - first
        before = heading[first - 1] if first > 0 else heading[stop] if stop < len(heading) else 0.0
        after = heading[stop] if stop < len(heading) else before
        fraction = np.minimum(np.arange(1, n + 1) / min(n + 1, round(DWELL_TURN_S * rate_hz) + 1), 1.0)
        walk = np.cumsum(rng.normal(0.0, DWELL_HEADING_STEP_RAD, n + 1))
        filled[first:stop] = wrapped(before + wrapped(after - before) * fraction + walk[:-1] - fraction * walk[-1])
    return filled


def arena(recipe, geometry, n_frames, led_half, rate_hz, rng):
    """
    The arena epoch's room positions and heading per frame: a correlated random walk inside the circle, AR(1) speed and turn rate from the recipe, steered toward the centre near the boundary, stopped for the recipe's pauses. The heading is the walk's angle and each step deviates from it by the heading noise, so the heading minus the direction of motion has the recipe's spread, the turn rate is the recipe's and the heading wanders while paused.
    """
    if geometry["kind"] != CIRCLE:
        raise Invalid(NOT_A_CIRCLE.format(name=geometry["name"], kind=geometry["kind"]))
    centre = np.array(geometry["room"], float) / 2
    limit = geometry["params"]["diameter"] / 2 - led_half
    speed_q, turn_q, pauses = recipe["speed"], recipe["turn_rate"], recipe["pauses"]
    speed = series_of(speed_q, ar1(rng.standard_normal(n_frames), ARENA_SPEED_TAU_S * rate_hz))
    turn = series_of(turn_q, ar1(rng.standard_normal(n_frames), ARENA_TURN_TAU_S * rate_hz))
    paused = np.zeros(n_frames, bool)
    starts = np.flatnonzero(rng.random(n_frames) < pauses["per_min"] / 60.0 / rate_hz)
    for first in starts:
        if not paused[first]:
            paused[first:first + round(drawn(pauses["duration_s"], rng) * rate_hz)] = True
    speed[paused], turn[paused] = 0.0, 0.0
    noise = heading_noise(n_frames, recipe["heading_spread_rad"], rate_hz, rng)
    xy, theta, p, angle = np.zeros((n_frames, 2)), np.zeros(n_frames), centre.copy(), rng.uniform(-np.pi, np.pi)
    for k in range(n_frames):
        away = p - centre
        if limit - np.hypot(*away) < BOUNDARY_MARGIN_M:
            angle += STEER_PER_S * wrapped(np.arctan2(-away[1], -away[0]) - angle) / rate_hz
        angle = wrapped(angle + turn[k] / rate_hz)
        xy[k], theta[k] = p, angle
        p = p + speed[k] / rate_hz * np.array([np.cos(angle + noise[k]), np.sin(angle + noise[k])])
        distance = np.hypot(*(p - centre))
        if distance > limit:
            p = centre + (p - centre) * limit / distance
    theta[paused] = np.nan
    return xy, dwell_headings(theta, rate_hz, rng)


def lights(xy, heading, led_half, p):
    """
    The frames' light and position columns in camera pixels: the two LEDs half the separation ahead of and behind the rat, head_dir their camera angle, avg and mashup their mean.
    """
    ahead = led_half * np.column_stack([np.cos(heading), np.sin(heading)])
    front_x, front_y = to_pixels(*(xy + ahead).T, p)
    back_x, back_y = to_pixels(*(xy - ahead).T, p)
    mid_x, mid_y = (front_x + back_x) / 2, (front_y + back_y) / 2
    return {"front_x": front_x, "front_y": front_y, "back_x": back_x, "back_y": back_y,
            "head_dir": np.arctan2(front_y - back_y, front_x - back_x), "avg_x": mid_x, "avg_y": mid_y, "mashup_x": mid_x, "mashup_y": mid_y}


def tables(session_id, date, environments, epochs, runs, rate_hz, max_gap):
    """
    The session row, the epoch rows and the run rows in the transformed schema, from the epoch kinds with their first and last frames and the runs as (path id, first frame, last frame).
    """
    n_frames = epochs[-1][2]
    session = {"session_id": session_id, "subject_id": SYNTHETIC, "group": SYNTHETIC, "date": date, "protocol": SYNTHETIC,
               "dvt_file": None, "rmaps_file": None, "rate_hz": rate_hz, "max_gap": max_gap, "n_frames": n_frames, "n_pauses": 0,
               "paused_s": 0.0, "unfilled_front": 0.0, "unfilled_back": 0.0, "n_events": 0, "n_runs": len(runs)}
    epoch_rows = [{"session_id": session_id, "epoch": kind, "environment": environments[kind]["name"], "condition": CONDITION,
                   "frame_start": first, "frame_end": last, "t_start": (first - 1) / rate_hz, "t_end": (last - 1) / rate_hz,
                   "duration_s": (last - first + 1) / rate_hz} for kind, first, last in epochs]
    run_rows = [{"session_id": session_id, "run": number, "epoch": TRACK, "path_id": pid, "frame_start": first, "frame_end": last,
                 "t_start": (first - 1) / rate_hz, "t_end": (last - 1) / rate_hz, "duration_s": (last - first) / rate_hz, "clean": True,
                 "duplicate_of": None, "overlap_frames": 0, "spans_pause": False} for number, (pid, first, last) in enumerate(runs, 1)]
    return session, epoch_rows, run_rows


class GeneratorEngine:
    """
    Stateless: a recipe in, arrays out, called by SynthesisManager alone.
    """

    def session(self, recipe, environments, camera, seed, length_s, session_id, date):
        """
        A session in the transformed schema dated date, one epoch per kind asked for (arena then track) of its length in seconds, from an explicit RNG seeded with seed, ready for TrajectoryEngine.blocks. Invalid for a track that is not the triple T, an arena that is not a circle, or a track recipe without outbound runs or dwells.
        """
        rng = np.random.default_rng(seed)
        rate_hz, led_half = camera["rate_hz"], camera["led_separation_m"] / 2
        columns, epochs, runs, first = [], [], [], 1
        for kind in [k for k in KINDS if k in length_s]:
            n = round(length_s[kind] * rate_hz)
            if kind == ARENA:
                xy, heading = arena(recipe[kind], environments[kind], n, led_half, rate_hz, rng)
            else:
                xy, heading, found = track(recipe[kind], environments[kind], n, led_half, rate_hz, rng)
                runs += [(pid, first + a, first + b) for pid, a, b in found]
            columns.append({**lights(xy, heading, led_half, camera[kind]), "epoch": np.full(n, kind, object)})
            epochs.append((kind, first, first + n - 1))
            first += n
        n_frames = first - 1
        session, epoch_rows, run_rows = tables(session_id, date, environments, epochs, runs, rate_hz, camera["max_gap"])
        merged = {name: np.concatenate([c[name] for c in columns]) for name in columns[0]}
        off = np.zeros(n_frames, bool)
        arrays = {"frame": np.arange(1, n_frames + 1, dtype=np.int64), "t": np.arange(n_frames) / rate_hz,
                  **{name: merged[name] for name in ("front_x", "front_y", "back_x", "back_y", "head_dir")},
                  "filled_front": off, "filled_back": off.copy(), "unfilled_front": off.copy(), "unfilled_back": off.copy(),
                  "painted_label": np.zeros(n_frames, np.int64),
                  **{name: merged[name] for name in ("avg_x", "avg_y", "mashup_x", "mashup_y", "epoch")}}
        return {"session": session, "epochs": epoch_rows, "runs": run_rows, "arrays": arrays, "stamp": SYNTHETIC}
