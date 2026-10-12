"""Shared environment geometry.

An EnvSpec is pure geometry (walls, centerline, routes, reward sites) plus a
content hash. It is serialized into dataset metadata so any artifact stays
regenerable and traceable to the exact geometry that produced it.

Shared frame: every environment lives in one room frame, meters, origin
bottom left, room north = +y, track squared to the room as in the paper.

RatInABox is touched only inside to_ratinabox().
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field

ROUND = 6


def rnd(x) -> float:
    return round(float(x), ROUND)


def rnd_point(p) -> list:
    return [rnd(p[0]), rnd(p[1])]


@dataclass
class EnvSpec:
    name: str
    kind: str
    room: list                # [width, height] in meters
    boundary: list | None     # polygon vertices, None = room rectangle
    walls: list               # [[[x0,y0],[x1,y1]], ...]
    centerline: list          # [{"name","p0","p1","axis_deg"}, ...]
    routes: dict              # name -> [[x,y], ...] waypoints
    returns: dict             # name -> [[x,y], ...] waypoints
    reward_sites: dict        # name -> [x,y]
    params: dict = field(default_factory=dict)

    def canonical(self) -> dict:
        d = asdict(self)
        return json.loads(json.dumps(d), parse_float=lambda v: round(float(v), ROUND))

    @property
    def hash(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


# ---------------------------------------------------------------------------
# walls for axis-aligned corridor mazes
# ---------------------------------------------------------------------------
#
# Each centerline segment gets two offset walls at +-h (h = width/2). The only
# subtlety is where a wall ends at a node, and one rule covers every case.
# For a wall on side n (unit normal) of a segment whose unit vector pointing
# away from the node is u, look at the away-vectors incident at that node:
#
#   n  incident  -> pull back by h    a branch opens on this side
#   -u incident  -> flush             the corridor continues straight through
#   -n incident  -> extend by h       this is the outer wall of an L corner
#   otherwise    -> flush, plus cap   dead end
#
#   T junction (branch up):          L corner (in from left, out up):
#        |    |                            |   |
#   -----+    +-----  near wall opens      |   |
#                                     -----+   |   inner wall pulls back
#   ----------------  far wall flush            |
#                                     ---------+   outer wall extends
#
# Getting this wrong is the failure mode: naive offsets seal every junction
# and turn the maze into disconnected boxes.

_DIRS = {(1, 0), (-1, 0), (0, 1), (0, -1)}


def _unit(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d = (int(math.copysign(1, dx)) if abs(dx) > 1e-9 else 0,
         int(math.copysign(1, dy)) if abs(dy) > 1e-9 else 0)
    if d not in _DIRS:
        raise ValueError(f"segment {p0}->{p1} is not axis aligned")
    return d


def _key(p):
    return (rnd(p[0]), rnd(p[1]))


def corridor_walls(centerline, width):
    h = width / 2.0
    incident: dict = {}
    for seg in centerline:
        d = _unit(seg["p0"], seg["p1"])
        incident.setdefault(_key(seg["p0"]), set()).add(d)
        incident.setdefault(_key(seg["p1"]), set()).add((-d[0], -d[1]))

    def endpoint(node, u_away, n):
        inc = incident[_key(node)]
        if n in inc:
            return [node[0] + h * u_away[0] + h * n[0],
                    node[1] + h * u_away[1] + h * n[1]]
        if (-u_away[0], -u_away[1]) in inc:
            return [node[0] + h * n[0], node[1] + h * n[1]]
        if (-n[0], -n[1]) in inc:
            return [node[0] - h * u_away[0] + h * n[0],
                    node[1] - h * u_away[1] + h * n[1]]
        return [node[0] + h * n[0], node[1] + h * n[1]]

    walls = []
    for seg in centerline:
        p0, p1 = seg["p0"], seg["p1"]
        d = _unit(p0, p1)
        for n in ((-d[1], d[0]), (d[1], -d[0])):
            walls.append([rnd_point(endpoint(p0, d, n)),
                          rnd_point(endpoint(p1, (-d[0], -d[1]), n))])
    for node, inc in incident.items():
        if len(inc) == 1:
            (u,) = inc
            n = (-u[1], u[0])
            walls.append([rnd_point([node[0] + h * n[0], node[1] + h * n[1]]),
                          rnd_point([node[0] - h * n[0], node[1] - h * n[1]])])
    return walls


def segment(name, p0, p1) -> dict:
    axis = 90 if _unit(p0, p1)[0] == 0 else 0
    return {"name": name, "p0": rnd_point(p0), "p1": rnd_point(p1), "axis_deg": axis}


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def rotate_spec(spec: EnvSpec, deg: float, name=None) -> EnvSpec:
    """Rotate an environment about the room center."""
    c = (spec.room[0] / 2.0, spec.room[1] / 2.0)
    th = math.radians(deg)
    co, si = math.cos(th), math.sin(th)

    def rot(p):
        x, y = p[0] - c[0], p[1] - c[1]
        return rnd_point([c[0] + x * co - y * si, c[1] + x * si + y * co])

    return EnvSpec(
        name=name or f"{spec.name}_rot{int(deg)}",
        kind=spec.kind, room=list(spec.room),
        boundary=[rot(p) for p in spec.boundary] if spec.boundary else None,
        walls=[[rot(a), rot(b)] for a, b in spec.walls],
        centerline=[{**s, "p0": rot(s["p0"]), "p1": rot(s["p1"]),
                     "axis_deg": rnd((s["axis_deg"] + deg) % 180)}
                    for s in spec.centerline],
        routes={k: [rot(p) for p in v] for k, v in spec.routes.items()},
        returns={k: [rot(p) for p in v] for k, v in spec.returns.items()},
        reward_sites={k: rot(p) for k, p in spec.reward_sites.items()},
        params={**spec.params, "rotated_deg": deg},
    )


# ---------------------------------------------------------------------------
# RatInABox adapter, the only place the package is touched
# ---------------------------------------------------------------------------

def to_ratinabox(spec: EnvSpec):
    """Build a RatInABox Environment in the shared room frame. Composition
    only, no subclassing."""
    from ratinabox import Environment

    if spec.boundary is not None:
        env = Environment(params={"boundary": spec.boundary})
    else:
        env = Environment(params={"scale": spec.room[1],
                                  "aspect": spec.room[0] / spec.room[1]})
    for a, b in spec.walls:
        env.add_wall([a, b])
    return env
