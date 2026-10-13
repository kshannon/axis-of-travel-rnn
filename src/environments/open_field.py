"""Open arena: a wall-less circle centered in the room frame, mirroring the
arena placed above the track center in the paper. The control condition."""

import math

from .common import EnvSpec, rnd_point


def build_circle(params, room, name="open_arena") -> EnvSpec:
    d, n = params["diameter"], int(params.get("n_vertices", 32))
    cx, cy, r = room[0] / 2.0, room[1] / 2.0, d / 2.0
    boundary = [rnd_point([cx + r * math.cos(2 * math.pi * i / n),
                           cy + r * math.sin(2 * math.pi * i / n)]) for i in range(n)]
    return EnvSpec(name=name, kind="circle", room=list(room), boundary=boundary,
                   walls=[], centerline=[], routes={}, returns={},
                   reward_sites={}, params=dict(params))
