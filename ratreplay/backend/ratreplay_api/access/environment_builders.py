"""
The geometry builders behind EnvironmentAccess: a yaml's parameters in, walls, centerline, boundary and reward sites out, all in the room frame.
"""

import math

# Every environment lives in one room frame in metres, origin bottom left, north is +y. Coordinates are rounded so the same
# yaml always gives the same numbers.
ROUND = 6
AXIS_TOLERANCE = 1e-9
DIRECTIONS = {(1, 0), (-1, 0), (0, 1), (0, -1)}
DEFAULT_VERTICES = 32
MIN_CLOSURE = 0.02


def rnd(x):
    """
    The number as a float rounded to the coordinate precision.
    """
    return round(float(x), ROUND)


def rnd_point(p):
    """
    The point with both coordinates rounded.
    """
    return [rnd(p[0]), rnd(p[1])]


def unit(p0, p1):
    """
    The axis aligned direction from p0 to p1 as a pair of -1, 0 or 1, ValueError when the segment is not axis aligned.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    direction = (int(math.copysign(1, dx)) if abs(dx) > AXIS_TOLERANCE else 0,
                 int(math.copysign(1, dy)) if abs(dy) > AXIS_TOLERANCE else 0)
    if direction not in DIRECTIONS:
        raise ValueError(f"segment {p0} to {p1} is not axis aligned")
    return direction


def key_of(p):
    """
    The point as a rounded tuple, to find the segments that meet there.
    """
    return (rnd(p[0]), rnd(p[1]))


def segment(name, p0, p1):
    """
    A centerline segment with its axis in degrees, 0 along x and 90 along y.
    """
    return {"name": name, "p0": rnd_point(p0), "p1": rnd_point(p1), "axis_deg": 90 if unit(p0, p1)[0] == 0 else 0}


def corridor_walls(centerline, width):
    """
    Two walls offset by half the width on each side of every segment, a cap at each dead end, and the wall ends opened where a branch leaves.
    """
    # Where a wall ends at a node, with n the wall's side and u the unit vector pointing away from the node, look at the
    # directions leaving the node. A branch on side n pulls the wall back by half the width, the corridor continuing
    # straight (-u) leaves it flush, a branch on the other side (-n) is the outer corner of an L and extends the wall by
    # half the width, and anything else is a dead end, flush and capped. Offsets alone would seal every junction.
    half = width / 2.0
    incident = {}
    for seg in centerline:
        d = unit(seg["p0"], seg["p1"])
        incident.setdefault(key_of(seg["p0"]), set()).add(d)
        incident.setdefault(key_of(seg["p1"]), set()).add((-d[0], -d[1]))

    def endpoint(node, away, n):
        leaving = incident[key_of(node)]
        if n in leaving:
            return [node[0] + half * away[0] + half * n[0], node[1] + half * away[1] + half * n[1]]
        if (-away[0], -away[1]) in leaving:
            return [node[0] + half * n[0], node[1] + half * n[1]]
        if (-n[0], -n[1]) in leaving:
            return [node[0] - half * away[0] + half * n[0], node[1] - half * away[1] + half * n[1]]
        return [node[0] + half * n[0], node[1] + half * n[1]]

    walls = []
    for seg in centerline:
        p0, p1 = seg["p0"], seg["p1"]
        d = unit(p0, p1)
        for n in ((-d[1], d[0]), (d[1], -d[0])):
            walls.append([rnd_point(endpoint(p0, d, n)), rnd_point(endpoint(p1, (-d[0], -d[1]), n))])
    for node, leaving in incident.items():
        if len(leaving) == 1:
            (u,) = leaving
            n = (-u[1], u[0])
            walls.append([rnd_point([node[0] + half * n[0], node[1] + half * n[1]]),
                          rnd_point([node[0] - half * n[0], node[1] - half * n[1]])])
    return walls


def build_circle(params, room, name):
    """
    The open arena, a wall-less circle centred in the room, its boundary a polygon of n_vertices points.
    """
    n = int(params.get("n_vertices", DEFAULT_VERTICES))
    cx, cy, radius = room[0] / 2.0, room[1] / 2.0, params["diameter"] / 2.0
    boundary = [rnd_point([cx + radius * math.cos(2 * math.pi * i / n), cy + radius * math.sin(2 * math.pi * i / n)]) for i in range(n)]
    return {"name": name, "kind": "circle", "room": list(room), "boundary": boundary, "walls": [], "centerline": [],
            "reward_sites": {}, "params": dict(params)}


def build_plus_maze(params, room, name):
    """
    The plus maze, four arms of arm_length from the room centre, a debugging environment.
    """
    cx, cy = room[0] / 2.0, room[1] / 2.0
    arm = params["arm_length"]
    ends = {"n": [cx, cy + arm], "s": [cx, cy - arm], "e": [cx + arm, cy], "w": [cx - arm, cy]}
    centerline = [segment(f"arm_{k}", [cx, cy], p) for k, p in ends.items()]
    return {"name": name, "kind": "plus_maze", "room": list(room), "boundary": None,
            "walls": corridor_walls(centerline, params["corridor_width"]), "centerline": centerline,
            "reward_sites": {k: rnd_point(p) for k, p in ends.items()}, "params": dict(params)}


def build_triple_t(params, room, name):
    """
    The triple-T track of Olson et al. 2017, squared to the room: a stem, two crossbars, four goal approaches and the perimeter return.
    """
    width = params["corridor_width"]
    half = width / 2.0
    stem, cross, rise, reach = params["run_segments"]
    env_x, env_y = params["envelope"]
    cx = room[0] / 2.0
    x0, y0 = (room[0] - env_x) / 2.0, (room[1] - env_y) / 2.0

    side_gap = env_x / 2.0 - (cross + reach) - half - width
    connector = env_y - (stem + rise) - width
    if side_gap <= MIN_CLOSURE or connector <= MIN_CLOSURE:
        raise ValueError(f"geometry does not close: gap={side_gap:.3f} conn={connector:.3f}")

    yb, yt = y0 + half, y0 + env_y - half
    xl, xr = x0 + half, x0 + env_x - half

    start = [cx, yb]
    t1 = [cx, yb + stem]
    cross_e, cross_w = [cx + cross, t1[1]], [cx - cross, t1[1]]
    up_e, up_w = [cross_e[0], t1[1] + rise], [cross_w[0], t1[1] + rise]
    gy = up_e[1]
    goals = {"g_ee": [cross_e[0] + reach, gy], "g_ew": [cross_e[0] - reach, gy],
             "g_ww": [cross_w[0] - reach, gy], "g_we": [cross_w[0] + reach, gy]}

    centerline = [
        segment("stem", start, t1),
        segment("cross_e", t1, cross_e), segment("cross_w", t1, cross_w),
        segment("up_e", cross_e, up_e), segment("up_w", cross_w, up_w),
        segment("approach_ee", up_e, goals["g_ee"]), segment("approach_ew", up_e, goals["g_ew"]),
        segment("approach_ww", up_w, goals["g_ww"]), segment("approach_we", up_w, goals["g_we"]),
    ]
    for goal, p in goals.items():
        centerline.append(segment(f"conn_{goal[2:]}", p, [p[0], yt]))
    top_x = sorted([xl] + [p[0] for p in goals.values()] + [xr])
    for i in range(len(top_x) - 1):
        centerline.append(segment(f"top_{i}", [top_x[i], yt], [top_x[i + 1], yt]))
    centerline += [segment("side_w", [xl, yb], [xl, yt]), segment("side_e", [xr, yb], [xr, yt]),
                   segment("bottom_w", [xl, yb], start), segment("bottom_e", start, [xr, yb])]

    return {"name": name, "kind": "triple_t", "room": list(room), "boundary": None,
            "walls": corridor_walls(centerline, width), "centerline": centerline,
            "reward_sites": {k: rnd_point(p) for k, p in {"start": start, **goals}.items()},
            "params": {**params, "derived": {"side_gap": rnd(side_gap), "connector": rnd(connector)}}}


def rotated(geometry, degrees, name):
    """
    The geometry turned by degrees about the room centre and named name, its params recording the rotation.
    """
    cx, cy = geometry["room"][0] / 2.0, geometry["room"][1] / 2.0
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)

    def turn(p):
        x, y = p[0] - cx, p[1] - cy
        return rnd_point([cx + x * cos - y * sin, cy + x * sin + y * cos])

    return {**geometry, "name": name,
            "boundary": [turn(p) for p in geometry["boundary"]] if geometry["boundary"] else None,
            "walls": [[turn(a), turn(b)] for a, b in geometry["walls"]],
            "centerline": [{**s, "p0": turn(s["p0"]), "p1": turn(s["p1"]), "axis_deg": rnd((s["axis_deg"] + degrees) % 180)}
                           for s in geometry["centerline"]],
            "reward_sites": {k: turn(p) for k, p in geometry["reward_sites"].items()},
            "params": {**geometry["params"], "rotated_deg": degrees}}


BUILDERS = {"triple_t": build_triple_t, "circle": build_circle, "plus_maze": build_plus_maze}
