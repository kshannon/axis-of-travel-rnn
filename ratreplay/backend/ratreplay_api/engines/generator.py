"""
GeneratorEngine: the one contract for generating synthetic behavior from a recipe.
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.signal import lfilter
from scipy.stats import norm, rankdata

from ..utilities.errors import Invalid

# The epoch kinds in the order a session holds them, the track's start site, the goals by path id (an assumption to check
# against the lab's numbering) and the return path ids by the side the return runs down. The generator knows the triple T
# alone (these sites and the segments check_track names) and the circular arena alone (the walk is confined to a disc).
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

# Track runs: the raised cosine ramp at each end, the per run pace multiplier (lognormal, its sigma), the within run speed
# modulation's time constant (its spread is the recipe's speed_cv_run) and the least share of the cruise it leaves, and the
# hesitation: its chance per run, its length in seconds, the share of the cruise it dips to and the part of the run it
# falls in.
RAMP_S = 0.5
PACE_SIGMA = 0.2
PACE_TAU_S, MIN_PACE = 1.0, 0.1
HESITATION_P, HESITATION_S, HESITATION_SPEED, HESITATION_SPAN = 0.3, (0.3, 0.8), 1 / 3, (0.25, 0.75)

# The lateral wander: a slow and a fast smooth AR(1) process of these time constants, each carrying an equal share of the
# variance, the total spread the root mean square implied by the recipe's lateral_m median for a half normal (the median
# over HALF_NORMAL_MEDIAN) and at most MAX_LATERAL_SHARE of the clip (a source off the maze, such as the test fixtures'
# circle, would pile the rat on both walls and split every corridor's occupancy peak, which the registration reads), the
# share of the half corridor width used when the recipe lacks it, the distance over which it
# fades in and out at a run's ends, and the corners rounded by a centred moving average of CORNER_SMOOTH_S per run, its
# ends held at the sites.
LATERAL_TAUS_S = (3.0, 0.5)
HALF_NORMAL_MEDIAN = 0.6745
MAX_LATERAL_SHARE = 0.5
FALLBACK_LATERAL_SHARE = 0.25
END_TAPER_M = 0.05
CORNER_SMOOTH_S = 0.25

# The lateral offset by segment class (version 3): on the perimeter (by the start of a segment's name) and on the inner
# segments the offset along the segment's normal away from the room's centre is the recipe's lateral_outward_m mean for the
# class plus the wander with the class's spread, the spread the interquartile range over IQR_PER_SD, so a real rat's lean
# toward the outer wall on the perimeter is kept. A recipe without the classes falls back to the unsigned wander.
PERIMETER_PREFIXES = ("side_", "bottom_", "top_", "conn_")
PERIMETER, INNER = "perimeter", "inner"
IQR_PER_SD = 1.349

# Reversals (version 3): during a run or an excursion the rat turns back along its path for REVERSE_BACK_S at the run's
# pace, the turn about each way taking REVERSE_TURN_S, at a point in REVERSE_SPAN of the run, and then on again, at the
# recipe's run_reversals_per_min over the time spent in runs, each back and forth being TURNS_PER_REVERSAL of the turns
# the recipe counts. A run with one is still one run row, marked not clean as the lab's labeller would.
REVERSE_TURN_S, REVERSE_BACK_S, REVERSE_SPAN = 0.3, (0.5, 2.0), (0.25, 0.75)
TURNS_PER_REVERSAL = 2

# Dwells: a slow wander around the site, its spread along the corridor (across it the lateral spread) and time constant,
# still stretches of this mean length covering the share of the dwell that gives the recipe's still fraction (held inside
# the bounds), the fade from
# and back to the site at each end, and the seconds over which the travel direction turns to the next run's.
DWELL_ALONG_M, DWELL_TAU_S = 0.05, 1.0
STILL_MEAN_S, STILL_BOUNDS = 1.5, (0.05, 0.8)
DWELL_FADE_S = 0.3
DWELL_TURN_S = 1.0

# Dwell moves (version 3): in one moving stretch between still stretches the rat walks out along one of the corridors
# meeting at its site, stands there, and walks back in the next, DWELL_MOVE_M out (at most the corridor's length), at a
# speed drawn between the running floor and the recipe's speed at DWELL_MOVE_QUANTILE, the move shortened to fit its
# stretches. A move out and back in one stretch turned the travel direction a full circle each time, which drove the turn
# rate over the recipe's.
DWELL_MOVE_M, DWELL_MOVE_QUANTILE = (0.1, 0.3), "q25"

# Excursions, not runs: the chance after a start dwell of going down to a bottom corridor and along it and back, the
# chance after a goal dwell of going up the goal's connector and back, and how far along, as a share of the segment.
EXCURSION_START_P, EXCURSION_GOAL_P, EXCURSION_REACH = 0.25, 0.15, (0.2, 0.8)
BOTTOM_SEGMENTS, STEM = ("bottom_w", "bottom_e"), "stem"
CONNECTOR = "conn_{}"

# Heading: the travel direction is the tangent of the path smoothed over TRAVEL_SMOOTH_S, held at its last value while the
# rat dwells or moves under STILL_M_PER_S (the running floor), and the heading is that direction delayed by the recipe's
# lag plus a smooth AR(1) noise of time constant HEADING_TAU_S whose spread follows the speed through the recipe's spread
# by speed, that spread smoothed over SPREAD_SMOOTH_S so a start or a stop does not jerk the head (0.25 s in version 2, 0.5 s
# in version 3, as the spread's change with speed turns the head too).
TRAVEL_SMOOTH_S = 0.1
STILL_M_PER_S = 0.03
HEADING_TAU_S = 0.5
SPREAD_SMOOTH_S = 0.5

# The heading noise time constant fitted per kind (version 3): a smooth AR(1) of spread s and time constant tau turns at
# a mean absolute rate of s over tau times sqrt(2 over pi) (its derivative has spread s over tau), and that rate and the
# travel direction's own add in quadrature to the recipe's turn_rate_abs_mean, so tau follows from the mean spread, times
# TAU_CORRECTION (the closed form leaves the measured arena turn rate 1.26 times the recipe's, the spread's own change and
# the tracking noise adding turn, a search over the factor on the round trip put 1.5 at 0.96). Held within
# HEADING_TAU_BOUNDS_S, HEADING_TAU_S when the recipe lacks the turn rate.
HEADING_TAU_BOUNDS_S = (0.1, 5.0)
MEAN_ABS_NORMAL = np.sqrt(2 / np.pi)
TAU_CORRECTION = 1.5

# The fastest the travel direction turns, in rad/s, so a turn about at the end of an excursion sweeps the head round over
# half a second and does not flip it from one frame to the next. A rounded corner at a run's cruise turns under it.
TRAVEL_TURN_LIMIT = 2 * np.pi

# Tracking noise: Gaussian pixel noise per frame on each LED, a part shared by the two (the blob jitters as one) and a part
# drawn for each LED alone, LED_OWN_SHARE of the midpoint's variance from the own parts, so the midpoint, which the recipe
# measures, carries the recipe's tracking noise. All own noise (independent LEDs) jitters the heading by about 7 degrees
# a frame at 2 mm and 5 cm separation, the real median being about 2 degrees (Kyle's 109 sessions), which a share of 0.2
# gives.
LED_OWN_SHARE = 0.1

# The arena walk: the time constants of the speed and the turn rate, and the within stretch speed modulation, its spread
# the recipe's speed_cv times ARENA_CV_SHARE, the modulated speed mapped back by rank onto the recipe's quantiles so it
# does not widen the tail. The boundary (version 3): a target distance from the boundary drawn from the recipe's
# boundary_distance_m and held for TARGET_HOLD_S, the walk steered at STEER_PER_S toward the tangent at that distance,
# turned inward or outward by the arctangent of the radial error over TARGET_SCALE_M, never past the boundary.
ARENA_SPEED_TAU_S, ARENA_TURN_TAU_S = 1.0, 0.2
TARGET_HOLD_S, TARGET_SCALE_M, STEER_PER_S = (2.0, 6.0), 0.05, 3.0
ARENA_CV_TAU_S, ARENA_CV_SHARE = 0.5, 1.0


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
    Invalid unless the track has the start and the four goal sites, the west side segment the routes are named by and the stem, bottom and connector segments the excursions follow.
    """
    sites = [name for name in (START, *GOALS.values()) if name not in geometry["reward_sites"]]
    names = {seg["name"] for seg in geometry["centerline"]}
    wanted = (WEST_SIDE, STEM, *BOTTOM_SEGMENTS, *(CONNECTOR.format(goal[2:]) for goal in GOALS.values()))
    segments = [name for name in wanted if name not in names]
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
    A run's duration in seconds drawn from the recipe's run durations for its path (when absent, the length at the recipe's q75 speed) times a lognormal pace multiplier, lengthened so its cruise speed stays under the recipe's q95 speed.
    """
    runs, speed = recipe["runs"].get(str(path_id)), recipe["speed"]
    duration = drawn(runs["duration_s"], rng) if runs and runs["duration_s"]["q50"] is not None else length / speed["q75"] + RAMP_S
    duration *= rng.lognormal(0.0, PACE_SIGMA)
    return max(duration, length / speed["q95"] + RAMP_S, 2 * RAMP_S + 2.0 / rate_hz)


def moving_average(xy, width):
    """
    The centred moving average of the rows over width frames, the window shrinking toward each end so the first and the last row stay where they are.
    """
    n, half = len(xy), width // 2
    reach = np.minimum(np.minimum(np.arange(n), n - 1 - np.arange(n)), half)
    total = np.concatenate([np.zeros((1, xy.shape[1])), np.cumsum(xy, axis=0)])
    index = np.arange(n)
    return (total[index + reach + 1] - total[index - reach]) / (2 * reach + 1)[:, None]


def reversed_pace(t, start, back_s):
    """
    The sign of the pace over the times t for a reversal starting at start: 1 before, a half cosine down to -1 over REVERSE_TURN_S, -1 for back_s, a half cosine up to 1 over REVERSE_TURN_S, then 1.
    """
    u = t - start
    turn = REVERSE_TURN_S
    return np.where(u < turn + back_s / 2, np.cos(np.pi * np.clip(u / turn, 0.0, 1.0)),
                    np.cos(np.pi * np.clip((2 * turn + back_s - u) / turn, 0.0, 1.0)))


def pace(n, cv, rate_hz, rng, reversal=None):
    """
    The signed speed profile of a run of n frames, its shape alone: a raised cosine bell, a slow AR(1) modulation of spread cv, with chance HESITATION_P a dip to HESITATION_SPEED of it somewhere in the middle half, and when reversal is (where, back_s) a turn back for back_s starting at that share of REVERSE_SPAN.
    """
    t = (np.arange(n - 1) + 0.5) / rate_hz
    total = (n - 1) / rate_hz
    ramp = np.minimum(np.minimum(t, total - t) / RAMP_S, 1.0)
    speed = 0.5 * (1 - np.cos(np.pi * ramp)) * np.maximum(1 + cv * ar1(rng.standard_normal(n - 1), PACE_TAU_S * rate_hz), MIN_PACE)
    hesitates, length, where = rng.random() < HESITATION_P, rng.uniform(*HESITATION_S), rng.random()
    low, high = HESITATION_SPAN[0] * total, HESITATION_SPAN[1] * total - length
    if hesitates and high > low:
        phase = np.clip((t - (low + where * (high - low))) / length, 0.0, 1.0)
        speed *= 1 - (1 - HESITATION_SPEED) * 0.5 * (1 - np.cos(2 * np.pi * phase))
    if reversal is not None:
        where, back_s = reversal
        window = back_s + 2 * REVERSE_TURN_S
        speed *= reversed_pace(t, (REVERSE_SPAN[0] + where * (REVERSE_SPAN[1] - REVERSE_SPAN[0])) * (total - window), back_s)
    return speed


def outward_normal(seg, centre):
    """
    The unit perpendicular of a centreline segment pointing away from the room's centre at its midpoint, the east or the north one for a segment on a line through the centre (the stem), as the recipe measures it.
    """
    p0, p1 = np.array(seg["p0"], float), np.array(seg["p1"], float)
    along = (p1 - p0) / np.hypot(*(p1 - p0))
    normal = np.array([along[1], -along[0]])
    away = normal @ ((p0 + p1) / 2 - centre)
    if abs(away) < 1e-9:
        away = normal[0] + normal[1]
    return normal if away > 0 else -normal


def step_sides(points, geometry):
    """
    Per step of a route: the outward normal of the centreline segment nearest the step's midpoint, and true where that segment is on the perimeter.
    """
    centre = np.array(geometry["room"], float) / 2
    normals, perimeter = [], []
    for mid in (np.asarray(points[1:]) + np.asarray(points[:-1])) / 2:
        seg = min(geometry["centerline"], key=lambda s: point_distance(mid, s))
        normals.append(outward_normal(seg, centre))
        perimeter.append(seg["name"].startswith(PERIMETER_PREFIXES))
    return np.array(normals), np.array(perimeter)


def point_distance(point, seg):
    """
    The distance of the point to the centreline segment.
    """
    p0, p1 = np.array(seg["p0"], float), np.array(seg["p1"], float)
    along = p1 - p0
    return float(np.hypot(*(point - p0 - np.clip((point - p0) @ along / (along @ along), 0.0, 1.0) * along)))


def run_positions(points, duration, cv, wander, lateral, limit, geometry, rate_hz, rng, reversal=None):
    """
    The positions of one run along the route's points: the pace profile (with its reversal, if any) scaled to cover the route in the duration, the lateral offset along each segment's outward normal (the class mean plus the unit wander times the class spread, clipped at the limit) faded in and out over END_TAPER_M at the ends, the corners rounded by the moving average.
    """
    steps = np.diff(points, axis=0)
    lengths = np.hypot(*steps.T)
    edges = np.concatenate(([0.0], np.cumsum(lengths)))
    normals, perimeter = step_sides(points, geometry)
    n = round(duration * rate_hz) + 1
    s = np.concatenate(([0.0], np.cumsum(pace(n, cv, rate_hz, rng, reversal))))
    s = np.clip(s * edges[-1] / s[-1], 0.0, edges[-1])
    at = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, len(steps) - 1)
    unit = steps[at] / lengths[at][:, None]
    mean, sd = (np.where(perimeter, lateral[PERIMETER][k], lateral[INNER][k])[at] for k in range(2))
    taper = np.clip(np.minimum(s, edges[-1] - s) / END_TAPER_M, 0.0, 1.0)
    offset = np.clip(mean + sd * wander[:n], -limit, limit) * taper
    xy = points[at] + (s - edges[at])[:, None] * unit + offset[:, None] * normals[at]
    return moving_average(xy, round(CORNER_SMOOTH_S * rate_hz))


def dwell_still_share(recipe):
    """
    The share of a dwell spent still: the recipe's still fraction over its dwell phase share (the still frames being in the dwells), the still fraction itself when the phase share is absent, a half when both are, inside STILL_BOUNDS.
    """
    still, dwell = recipe.get("still_fraction"), (recipe.get("phase_share") or {}).get("dwell")
    share = 0.5 if still is None else still / dwell if dwell else still
    return float(np.clip(share, *STILL_BOUNDS))


def dwell_moves(n, share, exits, speeds, rate_hz, rng):
    """
    Over n frames of a dwell, still stretches of mean STILL_MEAN_S covering about the share and between them moves along the exits (unit direction, length, lean), leaning outward as on that corridor: out along one in a moving stretch, standing there through the still stretch, back to the site in the next, a last lone stretch going out and back: the offset from the site per frame and true on the frames between still stretches.
    """
    means = {True: STILL_MEAN_S, False: STILL_MEAN_S * (1 - share) / share}
    offset, moving, stretches, at, still = np.zeros((n, 2)), np.zeros(n, bool), [], 0, rng.random() < share
    while at < n:
        length = min(max(1, round(rng.exponential(means[still]) * rate_hz)), n - at)
        if not still:
            stretches.append((at, at + length))
            moving[at:at + length] = True
        at, still = at + length, not still
    for k in range(0, len(stretches), 2):
        direction, reach, lean = exits[rng.integers(len(exits))]
        pair = stretches[k:k + 2]
        shortest = min(stop - first for first, stop in pair) / (rate_hz * (2 if len(pair) == 1 else 1))
        end = (min(rng.uniform(*DWELL_MOVE_M), reach, rng.uniform(*speeds) * shortest) * direction + lean)
        first, stop = pair[0]
        if len(pair) == 1:
            shape = 0.5 * (1 - np.cos(2 * np.pi * (np.arange(stop - first) + 1) / (stop - first + 1)))
            offset[first:stop] = shape[:, None] * end
            continue
        back_first, back_stop = pair[1]
        offset[first:stop] = (0.5 * (1 - np.cos(np.pi * (np.arange(stop - first) + 1) / (stop - first))))[:, None] * end
        offset[stop:back_first] = end
        offset[back_first:back_stop] = (0.5 * (1 + np.cos(np.pi * (np.arange(back_stop - back_first) + 1) / (back_stop - back_first))))[:, None] * end
    return offset, moving


def dwell_positions(site, n, along, exits, lateral_sd, still_share, speeds, rate_hz, rng):
    """
    The positions of a dwell and true on its frames between still stretches: moves out along the corridors meeting at the site and back, and a slow two dimensional wander, DWELL_ALONG_M along the corridor and the lateral spread across it, standing during still stretches and faded from and back to the site over DWELL_FADE_S at each end.
    """
    moves, moving = dwell_moves(n, still_share, exits, speeds, rate_hz, rng)
    clock = np.cumsum(moving)
    a, b = (sd * smooth_ar1(rng.standard_normal(n + 1), DWELL_TAU_S * rate_hz)[clock] for sd in (DWELL_ALONG_M, lateral_sd))
    k = np.arange(n)
    fade = 0.5 * (1 - np.cos(np.pi * np.clip(np.minimum(k + 1, n - k) / (DWELL_FADE_S * rate_hz), 0.0, 1.0)))
    along = np.asarray(along, float)
    return np.array(site) + moves + (fade * a)[:, None] * along + (fade * b)[:, None] * np.array([-along[1], along[0]]), moving


def site_exits(geometry, lateral):
    """
    Per reward site by name, the corridors meeting there from the centreline graph as (unit direction, length, lean), the lean the class's mean offset along the segment's outward normal.
    """
    coords, edges = centreline_graph(geometry)
    centre, segments = np.array(geometry["room"], float) / 2, {seg["name"]: seg for seg in geometry["centerline"]}
    found = {}
    for name, point in geometry["reward_sites"].items():
        node, found[name] = node_of(coords, point), []
        for i, j, length, seg in edges:
            if node in (i, j):
                step = coords[j if i == node else i] - coords[node]
                mean = lateral[PERIMETER if seg.startswith(PERIMETER_PREFIXES) else INNER][0]
                found[name].append((step / length, length, mean * outward_normal(segments[seg], centre)))
    return found


def inside(xy, centerline, limit):
    """
    The positions pulled back to within the limit of the nearest centreline segment.
    """
    nearest, distance = xy.copy(), np.full(len(xy), np.inf)
    for seg in centerline:
        p0, p1 = np.array(seg["p0"], float), np.array(seg["p1"], float)
        along = p1 - p0
        foot = p0 + np.clip((xy - p0) @ along / (along @ along), 0.0, 1.0)[:, None] * along
        d = np.hypot(*(xy - foot).T)
        closer = d < distance
        nearest[closer], distance[closer] = foot[closer], d[closer]
    over = distance > limit
    xy = xy.copy()
    xy[over] = nearest[over] + (xy[over] - nearest[over]) * (limit / distance[over])[:, None]
    return xy


def lateral_sd(recipe, half, limit):
    """
    The total spread of the lateral wander: the root mean square implied by the recipe's lateral_m median for a half normal, at most MAX_LATERAL_SHARE of the limit, a share of the half corridor width when the recipe lacks it.
    """
    lateral = recipe.get("lateral_m")
    if lateral and lateral["q50"] is not None:
        return min(lateral["q50"] / HALF_NORMAL_MEDIAN, MAX_LATERAL_SHARE * limit)
    return FALLBACK_LATERAL_SHARE * half


def lateral_of(recipe, half, limit):
    """
    Per segment class, perimeter and inner, the mean offset outward and the spread of the wander about it: the class's lateral_outward_m mean and its interquartile range over IQR_PER_SD (at most MAX_LATERAL_SHARE of the limit), no lean and the unsigned spread of lateral_sd when the recipe lacks the class.
    """
    found = {}
    for name in (PERIMETER, INNER):
        q = (recipe.get("lateral_outward_m") or {}).get(name)
        if q and q["q50"] is not None:
            found[name] = (q["mean"], min((q["q75"] - q["q25"]) / IQR_PER_SD, MAX_LATERAL_SHARE * limit))
        else:
            found[name] = (0.0, lateral_sd(recipe, half, limit))
    return found


def reversing(recipe, duration, rng):
    """
    A run or excursion piece's duration and its reversal: with chance the recipe's run_reversals_per_min over TURNS_PER_REVERSAL and over the share of time in runs, for this duration, a reversal (where, back_s) and the duration lengthened by its turn back and forth, else None and the duration as it was.
    """
    rate, share = (recipe.get("run_reversals_per_min") or 0.0) / TURNS_PER_REVERSAL, recipe.get("phase_share") or {}
    in_runs = share.get("outbound", 0.0) + share.get("return", 0.0)
    if not rate or not in_runs or rng.random() >= rate / 60.0 * duration / in_runs:
        return duration, None
    back_s = rng.uniform(*REVERSE_BACK_S)
    return duration + 2 * back_s + 2 * REVERSE_TURN_S, (rng.random(), back_s)


def segment_of(geometry, name):
    """
    The two ends of the named centreline segment as points.
    """
    seg = next(s for s in geometry["centerline"] if s["name"] == name)
    return np.array(seg["p0"], float), np.array(seg["p1"], float)


def excursion(points, recipe, rate_hz, rng):
    """
    An excursion out along the points and back the same way, two moves that are not runs, each at the recipe's q75 speed with its ramps and now and then a reversal.
    """
    keep = np.concatenate(([True], np.hypot(*np.diff(points, axis=0).T) > 0))
    out = np.array(points)[keep]
    length = np.hypot(*np.diff(out, axis=0).T).sum()
    duration = max(length / recipe["speed"]["q75"] + RAMP_S, 2 * RAMP_S + 2.0 / rate_hz)
    return [("run", None, route, *reversing(recipe, duration, rng)) for route in (out, out[::-1])]


def start_excursion(geometry, rng):
    """
    The points of an excursion from the start: down the stem to the bottom corridor and a random share of the way along one of the two bottom segments.
    """
    foot = segment_of(geometry, STEM)[0]
    p0, p1 = segment_of(geometry, BOTTOM_SEGMENTS[rng.integers(2)])
    far = p0 if np.allclose(p1, foot) else p1
    return [np.array(geometry["reward_sites"][START], float), foot, foot + rng.uniform(*EXCURSION_REACH) * (far - foot)]


def goal_excursion(geometry, goal, rng):
    """
    The points of an excursion from a goal: a random share of the way up its connector.
    """
    p0, p1 = segment_of(geometry, CONNECTOR.format(goal[2:]))
    return [p0, p0 + rng.uniform(*EXCURSION_REACH) * (p1 - p0)]


def first_direction(points):
    """
    The unit vector of a route's first step.
    """
    step = np.array(points[1], float) - np.array(points[0], float)
    return step / np.hypot(*step)


def track_plan(recipe, geometry, n_frames, rate_hz, rng):
    """
    The track epoch as pieces in order, each ("dwell", site name, frames, the corridor's direction there) or ("run", path id or None for an excursion, route, duration, reversal or None): trips from the start while they fit, now and then an excursion after a dwell, the rest a dwell where the rat stands.
    """
    check_recipe(recipe)
    routes, returns = track_routes(geometry)
    goals = list(GOALS)
    share = np.array([recipe["goal_share"][str(pid)] for pid in goals], float)
    pieces, used, along = [], 0, first_direction(routes[goals[0]])
    while True:
        pid = int(rng.choice(goals, p=share / share.sum()))
        back_pid, back = returns[pid]
        trip = [("dwell", START, max(1, round(drawn(recipe["dwell_s"]["start"], rng) * rate_hz)), first_direction(routes[pid]))]
        if rng.random() < EXCURSION_START_P:
            trip += excursion(start_excursion(geometry, rng), recipe, rate_hz, rng)
        duration = run_duration(recipe, pid, np.hypot(*np.diff(routes[pid], axis=0).T).sum(), rate_hz, rng)
        trip.append(("run", pid, routes[pid], *reversing(recipe, duration, rng)))
        trip.append(("dwell", GOALS[pid], max(1, round(drawn(recipe["dwell_s"]["goal"], rng) * rate_hz)), first_direction(back)))
        if rng.random() < EXCURSION_GOAL_P:
            trip += excursion(goal_excursion(geometry, GOALS[pid], rng), recipe, rate_hz, rng)
        duration = run_duration(recipe, back_pid, np.hypot(*np.diff(back, axis=0).T).sum(), rate_hz, rng)
        trip.append(("run", back_pid, back, *reversing(recipe, duration, rng)))
        frames = sum(p[2] if p[0] == "dwell" else round(p[3] * rate_hz) + 1 for p in trip)
        if used + frames > n_frames:
            break
        pieces, used, along = pieces + trip, used + frames, trip[0][3]
    return pieces + [("dwell", START, n_frames - used, along)] if n_frames > used else pieces


def track(recipe, geometry, n_frames, led_half, rate_hz, rng):
    """
    The track epoch's room positions and heading per frame and its runs as (path id, first index, last index, clean), every position within the half corridor width and the LED half separation of the centreline, a run with a reversal not clean.
    """
    half = geometry["params"]["corridor_width"] / 2
    limit = half + led_half
    lateral = lateral_of(recipe, half, limit)
    wander = sum(smooth_ar1(rng.standard_normal(n_frames), tau * rate_hz) for tau in LATERAL_TAUS_S) / np.sqrt(len(LATERAL_TAUS_S))
    cv, still_share, exits = recipe.get("speed_cv_run") or 0.0, dwell_still_share(recipe), site_exits(geometry, lateral)
    speeds = (STILL_M_PER_S, max(STILL_M_PER_S, recipe["speed"][DWELL_MOVE_QUANTILE]))
    xy, held, dwells, runs, at = np.zeros((n_frames, 2)), np.zeros(n_frames, bool), [], [], 0
    for piece in track_plan(recipe, geometry, n_frames, rate_hz, rng):
        if piece[0] == "dwell":
            _, name, n, along = piece
            xy[at:at + n], moving = dwell_positions(geometry["reward_sites"][name], n, along, exits[name], lateral[INNER][1], still_share, speeds, rate_hz, rng)
            held[at:at + n] = ~moving
            dwells.append((at, at + n))
            at += n
            continue
        _, pid, route, duration, reversal = piece
        found = run_positions(route, duration, cv, wander[at:], lateral, limit, geometry, rate_hz, rng, reversal)
        xy[at:at + len(found)] = found
        if pid is not None:
            runs.append((pid, at, at + len(found) - 1, reversal is None))
        at += len(found)
    xy = inside(xy, geometry["centerline"], limit)
    return xy, heading_of(xy, held, dwells, recipe, rate_hz, rng), runs


def travel(xy, held, dwells, rate_hz):
    """
    The travel direction and speed per frame from the path smoothed over TRAVEL_SMOOTH_S: its tangent, held at the last value where the frame is held or slower than STILL_M_PER_S, and over the last DWELL_TURN_S of each dwell turned along the shorter arc to the direction the rat sets off in.
    """
    velocity = np.gradient(moving_average(xy, round(TRAVEL_SMOOTH_S * rate_hz)), axis=0) * rate_hz
    speed, direction = np.hypot(*velocity.T), np.arctan2(velocity[:, 1], velocity[:, 0])
    keep = np.flatnonzero(~held & (speed >= STILL_M_PER_S))
    if keep.size == 0:
        return np.zeros(len(xy)), speed
    marked = np.full(len(xy), keep[0])
    marked[keep] = keep
    last = np.maximum.accumulate(marked)
    found = direction[last]
    turn = round(DWELL_TURN_S * rate_hz)
    for first, stop in dwells:
        after = np.searchsorted(keep, stop)
        if after < keep.size:
            m = min(stop - first, turn)
            base, target = found[stop - m], direction[keep[after]]
            found[stop - m:stop] = base + wrapped(target - base) * np.arange(1, m + 1) / (m + 1)
    return turn_limited(wrapped(found), TRAVEL_TURN_LIMIT / rate_hz), speed


def turn_limited(direction, step):
    """
    The directions followed frame by frame along the shorter arc, turning by at most step a frame.
    """
    found = direction.copy()
    for k in range(1, len(found)):
        found[k] = found[k - 1] + np.clip(wrapped(direction[k] - found[k - 1]), -step, step)
    return wrapped(found)


def heading_of(xy, held, dwells, recipe, rate_hz, rng):
    """
    The heading per frame: the travel direction delayed by the recipe's lag plus a smooth AR(1) noise whose spread at each frame is the recipe's spread at the frame's speed, interpolated over its speed bins.
    """
    direction, speed = travel(xy, held, dwells, rate_hz)
    lag = round((recipe.get("heading_lag_s") or 0.0) * rate_hz)
    if lag > 0:
        direction = np.concatenate([np.full(lag, direction[0]), direction[:-lag]])
    curve = [row for row in recipe.get("heading_spread_by_speed") or [] if row["spread_rad"] is not None]
    if curve:
        spread = np.interp(speed, [row["speed_m_per_s"] for row in curve], [row["spread_rad"] for row in curve])
    else:
        spread = np.full(len(speed), recipe.get("heading_spread_rad") or 0.0)
    spread = moving_average(spread[:, None], round(SPREAD_SMOOTH_S * rate_hz))[:, 0]
    return wrapped(direction + spread * smooth_ar1(rng.standard_normal(len(speed)), noise_tau_s(recipe, spread, direction, rate_hz) * rate_hz))


def noise_tau_s(recipe, spread, direction, rate_hz):
    """
    The heading noise time constant in seconds: the mean spread times MEAN_ABS_NORMAL over the turn rate left for the noise, that left being the recipe's turn_rate_abs_mean less the travel direction's own mean absolute turn rate in quadrature, times TAU_CORRECTION, within HEADING_TAU_BOUNDS_S, HEADING_TAU_S when the recipe lacks the turn rate.
    """
    target = recipe.get("turn_rate_abs_mean")
    if not target:
        return HEADING_TAU_S
    own = np.mean(np.abs(wrapped(np.diff(direction)))) * rate_hz
    left = np.sqrt(max(target * target - own * own, 0.0))
    if left == 0:
        return HEADING_TAU_BOUNDS_S[1]
    return float(np.clip(TAU_CORRECTION * MEAN_ABS_NORMAL * np.mean(spread) / left, *HEADING_TAU_BOUNDS_S))


def arena_speed(recipe, n_frames, rate_hz, rng):
    """
    The arena walk's speed per frame: an AR(1) series through the recipe's speed quantiles, modulated within a stretch by the recipe's speed_cv, and the modulated series mapped back by rank onto the quantiles so the modulation does not widen the tail.
    """
    speed = series_of(recipe["speed"], ar1(rng.standard_normal(n_frames), ARENA_SPEED_TAU_S * rate_hz))
    cv = ARENA_CV_SHARE * (recipe.get("speed_cv") or 0.0)
    speed *= np.maximum(1 + cv * ar1(rng.standard_normal(n_frames), ARENA_CV_TAU_S * rate_hz), MIN_PACE)
    return series_of(recipe["speed"], norm.ppf((rankdata(speed) - 0.5) / n_frames))


def boundary_targets(recipe, n_frames, rate_hz, rng):
    """
    The target distance from the boundary per frame, drawn from the recipe's boundary_distance_m and held for a time drawn from TARGET_HOLD_S.
    """
    target, at = np.zeros(n_frames), 0
    while at < n_frames:
        length = round(rng.uniform(*TARGET_HOLD_S) * rate_hz)
        target[at:at + length] = drawn(recipe["boundary_distance_m"], rng)
        at += length
    return target


def arena(recipe, geometry, n_frames, rate_hz, rng):
    """
    The arena epoch's room positions and heading per frame: a correlated random walk inside the circle, AR(1) speed and turn rate from the recipe, the speed modulated within a stretch by the recipe's speed_cv, steered toward a held target distance from the boundary drawn from the recipe, stopped for the recipe's pauses, its midpoint never past the boundary (the recipe's distance is unsigned, so a point outside would read as inside), the heading made from the path as on the track.
    """
    if geometry["kind"] != CIRCLE:
        raise Invalid(NOT_A_CIRCLE.format(name=geometry["name"], kind=geometry["kind"]))
    centre = np.array(geometry["room"], float) / 2
    radius = geometry["params"]["diameter"] / 2
    turn_q, pauses = recipe["turn_rate"], recipe["pauses"]
    speed = arena_speed(recipe, n_frames, rate_hz, rng)
    turn = series_of(turn_q, ar1(rng.standard_normal(n_frames), ARENA_TURN_TAU_S * rate_hz))
    paused = np.zeros(n_frames, bool)
    starts = np.flatnonzero(rng.random(n_frames) < pauses["per_min"] / 60.0 / rate_hz)
    for first in starts:
        if not paused[first]:
            paused[first:first + round(drawn(pauses["duration_s"], rng) * rate_hz)] = True
    speed[paused], turn[paused] = 0.0, 0.0
    target = radius - boundary_targets(recipe, n_frames, rate_hz, rng)
    xy, p, angle = np.zeros((n_frames, 2)), centre.copy(), rng.uniform(-np.pi, np.pi)
    for k in range(n_frames):
        away = p - centre
        outward = np.arctan2(away[1], away[0])
        side = 1.0 if wrapped(angle - outward) >= 0 else -1.0
        wanted = outward + side * (np.pi / 2 + np.arctan((np.hypot(*away) - target[k]) / TARGET_SCALE_M))
        angle = wrapped(angle + STEER_PER_S * wrapped(wanted - angle) / rate_hz + turn[k] / rate_hz)
        xy[k] = p
        p = p + speed[k] / rate_hz * np.array([np.cos(angle), np.sin(angle)])
        distance = np.hypot(*(p - centre))
        if distance > radius:
            p = centre + (p - centre) * radius / distance
    return xy, heading_of(xy, np.zeros(n_frames, bool), [], recipe, rate_hz, rng)


def lights(xy, heading, led_half, p, noise_m, rng):
    """
    The frames' light and position columns in camera pixels: the two LEDs half the separation ahead of and behind the rat, with Gaussian pixel noise shared by the two and of each alone that gives their midpoint noise_m at the scale, head_dir their camera angle, avg and mashup their mean.
    """
    ahead = led_half * np.column_stack([np.cos(heading), np.sin(heading)])
    sd = noise_m * p["scale_px_per_m"]
    shared = rng.normal(0.0, sd * np.sqrt(1 - LED_OWN_SHARE), (2, len(xy)))
    own = rng.normal(0.0, sd * np.sqrt(2 * LED_OWN_SHARE), (4, len(xy)))
    front_x, front_y = (v + shared[k] + own[k] for k, v in enumerate(to_pixels(*(xy + ahead).T, p)))
    back_x, back_y = (v + shared[k] + own[k + 2] for k, v in enumerate(to_pixels(*(xy - ahead).T, p)))
    mid_x, mid_y = (front_x + back_x) / 2, (front_y + back_y) / 2
    return {"front_x": front_x, "front_y": front_y, "back_x": back_x, "back_y": back_y,
            "head_dir": np.arctan2(front_y - back_y, front_x - back_x), "avg_x": mid_x, "avg_y": mid_y, "mashup_x": mid_x, "mashup_y": mid_y}


def tables(session_id, date, environments, epochs, runs, rate_hz, max_gap):
    """
    The session row, the epoch rows and the run rows in the transformed schema, from the epoch kinds with their first and last frames and the runs as (path id, first frame, last frame, clean).
    """
    n_frames = epochs[-1][2]
    session = {"session_id": session_id, "subject_id": SYNTHETIC, "group": SYNTHETIC, "date": date, "protocol": SYNTHETIC,
               "dvt_file": None, "rmaps_file": None, "rate_hz": rate_hz, "max_gap": max_gap, "n_frames": n_frames, "n_pauses": 0,
               "paused_s": 0.0, "unfilled_front": 0.0, "unfilled_back": 0.0, "n_events": 0, "n_runs": len(runs)}
    epoch_rows = [{"session_id": session_id, "epoch": kind, "environment": environments[kind]["name"], "condition": CONDITION,
                   "frame_start": first, "frame_end": last, "t_start": (first - 1) / rate_hz, "t_end": (last - 1) / rate_hz,
                   "duration_s": (last - first + 1) / rate_hz} for kind, first, last in epochs]
    run_rows = [{"session_id": session_id, "run": number, "epoch": TRACK, "path_id": pid, "frame_start": first, "frame_end": last,
                 "t_start": (first - 1) / rate_hz, "t_end": (last - 1) / rate_hz, "duration_s": (last - first) / rate_hz, "clean": clean,
                 "duplicate_of": None, "overlap_frames": 0, "spans_pause": False} for number, (pid, first, last, clean) in enumerate(runs, 1)]
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
                xy, heading = arena(recipe[kind], environments[kind], n, rate_hz, rng)
            else:
                xy, heading, found = track(recipe[kind], environments[kind], n, led_half, rate_hz, rng)
                runs += [(pid, first + a, first + b, clean) for pid, a, b, clean in found]
            noise = recipe[kind].get("tracking_noise_m") or 0.0
            columns.append({**lights(xy, heading, led_half, camera[kind], noise, rng), "epoch": np.full(n, kind, object)})
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
