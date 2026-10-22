"""
The geometry the engine registers a session against: an entry of the environments section of configs/project.yaml built into plain data, with a person's start offset laid over the entry's.
"""

# The RatInABox export of these environments stays out of here. It comes back later as riab_envs_builder, with a viewer.
#
# Every environment lives in one room frame: metres, origin bottom left, room north +y, the track squared to the room as in
# the paper. An environment is a dict of name, kind, room, boundary, walls, centerline, routes, returns, reward_sites, params.

import math

from ..config import section

SECTION = "environments"
BASE_KEY = "base"  # an entry may name a base entry and a transform (rotate_deg), merged over the base
ROUND = 6  # decimals every coordinate is rounded to
START_OFFSET = "start_offset"  # the start offset applies to the one type with a start site up a stem
OFFSET_TYPE = "triple_t"
MIN_CLEARANCE = 0.02  # metres, the side gap and the goal connector of the triple-T must be wider than this
DIRECTIONS = {(1, 0), (-1, 0), (0, 1), (0, -1)}


def rnd(value):
    """
    The value as a float rounded to ROUND decimals.
    """
    return round(float(value), ROUND)


def rnd_point(p):
    """
    The point as a rounded [x, y] list.
    """
    return [rnd(p[0]), rnd(p[1])]


def unit(p0, p1):
    """
    The unit step of an axis aligned segment as (dx, dy), a ValueError when the segment is not axis aligned.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d = (int(math.copysign(1, dx)) if abs(dx) > 1e-9 else 0, int(math.copysign(1, dy)) if abs(dy) > 1e-9 else 0)
    if d not in DIRECTIONS:
        raise ValueError(f"segment {p0}->{p1} is not axis aligned")
    return d


def segment(name, p0, p1):
    """
    A centre line segment with its axis, 0 degrees east-west and 90 north-south.
    """
    return {"name": name, "p0": rnd_point(p0), "p1": rnd_point(p1), "axis_deg": 90 if unit(p0, p1)[0] == 0 else 0}


def corridor_walls(centerline, width):
    """
    The two walls of every corridor and a cap at every dead end.
    """
    # Each segment gets two walls at +-h (h half the width). For a wall on side n of a segment whose unit vector away from
    # a node is u, the away vectors incident at that node decide where the wall ends:
    #   n incident: pull back by h (a branch opens on this side)
    #   -u incident: flush (the corridor runs straight through)
    #   -n incident: extend by h (the outer wall of an L corner)
    #   otherwise: flush, plus a cap (a dead end)
    # Naive offsets seal every junction and turn the maze into disconnected boxes.
    h = width / 2.0
    incident = {}
    for seg in centerline:
        d = unit(seg["p0"], seg["p1"])
        incident.setdefault(tuple(rnd_point(seg["p0"])), set()).add(d)
        incident.setdefault(tuple(rnd_point(seg["p1"])), set()).add((-d[0], -d[1]))

    def endpoint(node, u, n):
        here = incident[tuple(rnd_point(node))]
        if n in here:
            return [node[0] + h * u[0] + h * n[0], node[1] + h * u[1] + h * n[1]]
        if (-n[0], -n[1]) in here and (-u[0], -u[1]) not in here:
            return [node[0] - h * u[0] + h * n[0], node[1] - h * u[1] + h * n[1]]
        return [node[0] + h * n[0], node[1] + h * n[1]]

    walls = []
    for seg in centerline:
        p0, p1 = seg["p0"], seg["p1"]
        d = unit(p0, p1)
        for n in ((-d[1], d[0]), (d[1], -d[0])):
            walls.append([rnd_point(endpoint(p0, d, n)), rnd_point(endpoint(p1, (-d[0], -d[1]), n))])
    for node, here in incident.items():
        if len(here) == 1:
            (u,) = here
            n = (-u[1], u[0])
            walls.append([rnd_point([node[0] + h * n[0], node[1] + h * n[1]]), rnd_point([node[0] - h * n[0], node[1] - h * n[1]])])
    return walls


def build_triple_t(params, room, name):
    """
    The triple-T of Olson, Tongprasearth and Nitz (2017): the paper pins the envelope, the corridor width and the run segments, the goal approaches and the perimeter returns are inferred from its figure, and start_offset (metres, default 0) moves the start and the maze body up the stem.
    """
    # Route names encode the two free choices, the turn at the first T and the turn at the final junction: ee is the
    # outermost east goal, ew the inner east goal, and so on.
    w = params["corridor_width"]
    h = w / 2.0
    l1, l2, l3, l4 = params["run_segments"]
    ex, ey = params["envelope"]
    offset = params.get(START_OFFSET, 0.0)
    cx = room[0] / 2.0
    x0, y0 = (room[0] - ex) / 2.0, (room[1] - ey) / 2.0
    gap = ex / 2.0 - (l2 + l4) - h - w  # maze body to the side return corridor
    conn = ey - (offset + l1 + l3) - w  # goal to the top corridor
    if gap <= MIN_CLEARANCE or conn <= MIN_CLEARANCE:
        raise ValueError(f"geometry does not close: gap={gap:.3f} conn={conn:.3f}")
    yb, yt = y0 + h, y0 + ey - h  # bottom and top corridor centre lines
    xl, xr = x0 + h, x0 + ex - h  # side corridor centre lines
    foot = [cx, yb]  # where the stem meets the bottom corridor
    start = [cx, yb + offset]
    t1 = [cx, start[1] + l1]
    ce, cw = [cx + l2, t1[1]], [cx - l2, t1[1]]
    ue, uw = [ce[0], t1[1] + l3], [cw[0], t1[1] + l3]
    goals = {"g_ee": [ce[0] + l4, ue[1]], "g_ew": [ce[0] - l4, ue[1]], "g_ww": [cw[0] - l4, ue[1]], "g_we": [cw[0] + l4, ue[1]]}
    centerline = [
        segment("stem", foot, t1), segment("cross_e", t1, ce), segment("cross_w", t1, cw),
        segment("up_e", ce, ue), segment("up_w", cw, uw),
        segment("approach_ee", ue, goals["g_ee"]), segment("approach_ew", ue, goals["g_ew"]),
        segment("approach_ww", uw, goals["g_ww"]), segment("approach_we", uw, goals["g_we"]),
    ]
    centerline += [segment(f"conn_{goal[2:]}", p, [p[0], yt]) for goal, p in goals.items()]
    top_x = sorted([xl] + [p[0] for p in goals.values()] + [xr])
    centerline += [segment(f"top_{i}", [top_x[i], yt], [top_x[i + 1], yt]) for i in range(len(top_x) - 1)]
    centerline += [segment("side_w", [xl, yb], [xl, yt]), segment("side_e", [xr, yb], [xr, yt]),
                   segment("bottom_w", [xl, yb], foot), segment("bottom_e", foot, [xr, yb])]
    routes = {"ee": [start, t1, ce, ue, goals["g_ee"]], "ew": [start, t1, ce, ue, goals["g_ew"]],
              "ww": [start, t1, cw, uw, goals["g_ww"]], "we": [start, t1, cw, uw, goals["g_we"]]}
    back = [foot, start] if offset else [start]  # the returns climb the stem to the start
    returns = {"east": [[xr, yt], [xr, yb]] + back, "west": [[xl, yt], [xl, yb]] + back}
    return {"name": name, "kind": "triple_t", "room": list(room), "boundary": None, "walls": corridor_walls(centerline, w),
            "centerline": centerline, "routes": {k: [rnd_point(p) for p in v] for k, v in routes.items()},
            "returns": {k: [rnd_point(p) for p in v] for k, v in returns.items()},
            "reward_sites": {k: rnd_point(p) for k, p in {"start": start, **goals}.items()},
            "params": {**params, "derived": {"side_gap": rnd(gap), "connector": rnd(conn)}}}


def build_circle(params, room, name):
    """
    The open arena: a wall-less circle centred in the room, as the arena placed above the track centre in the paper.
    """
    d, n = params["diameter"], int(params.get("n_vertices", 32))
    cx, cy, r = room[0] / 2.0, room[1] / 2.0, d / 2.0
    boundary = [rnd_point([cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)]) for i in range(n)]
    return {"name": name, "kind": "circle", "room": list(room), "boundary": boundary, "walls": [], "centerline": [],
            "routes": {}, "returns": {}, "reward_sites": {}, "params": dict(params)}


BUILDERS = {"triple_t": build_triple_t, "circle": build_circle}


def rotated(env, deg):
    """
    The environment rotated by deg about the room centre, every centre line axis turned with it.
    """
    c = (env["room"][0] / 2.0, env["room"][1] / 2.0)
    co, si = math.cos(math.radians(deg)), math.sin(math.radians(deg))

    def rot(p):
        x, y = p[0] - c[0], p[1] - c[1]
        return rnd_point([c[0] + x * co - y * si, c[1] + x * si + y * co])

    return {**env, "boundary": [rot(p) for p in env["boundary"]] if env["boundary"] else None,
            "walls": [[rot(a), rot(b)] for a, b in env["walls"]],
            "centerline": [{**s, "p0": rot(s["p0"]), "p1": rot(s["p1"]), "axis_deg": rnd((s["axis_deg"] + deg) % 180)}
                           for s in env["centerline"]],
            "routes": {k: [rot(p) for p in v] for k, v in env["routes"].items()},
            "returns": {k: [rot(p) for p in v] for k, v in env["returns"].items()},
            "reward_sites": {k: rot(p) for k, p in env["reward_sites"].items()},
            "params": {**env["params"], "rotated_deg": deg}}


def environment_config(name, project=None):
    """
    The named entry of the environments section, merged over its base entry when it names one.
    """
    entry = section(f"{SECTION}.{name}", project)
    if BASE_KEY not in entry:
        return entry
    base = section(f"{SECTION}.{entry[BASE_KEY]}", project)
    merged = {**base, **{k: v for k, v in entry.items() if k != BASE_KEY}}
    merged["params"] = {**base.get("params", {}), **entry.get("params", {})}
    return merged


def geometry(name, start_offset_m=None, project=None):
    """
    The environment's geometry as a dict (room, boundary, centerline, reward sites, walls, params), built with this start offset in metres in place of the entry's when one is given and the type has a start site.
    """
    config = environment_config(name, project)
    if config["type"] not in BUILDERS:
        raise ValueError(f"unknown environment type {config['type']!r}, known: {sorted(BUILDERS)}")
    if start_offset_m is not None and config["type"] == OFFSET_TYPE:
        config = {**config, "params": {**config.get("params", {}), START_OFFSET: start_offset_m}}
    env = BUILDERS[config["type"]](config.get("params", {}), config["room"]["extent"], name)
    deg = config.get("transform", {}).get("rotate_deg")
    return rotated(env, deg) if deg else env


def geometries(epochs, rules, start_offset_m=None, project=None):
    """
    The geometry by name of the environments of the epochs of the rules' kinds, what session and blocks take.
    """
    return {e["environment"]: geometry(e["environment"], start_offset_m, project) for e in epochs if e["epoch"] in rules["epochs"]}
