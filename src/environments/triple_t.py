"""Triple-T track of Olson, Tongprasearth and Nitz (2017).

Paper-pinned: envelope 1.60 x 1.25 m, corridor width 0.08 m, four 1.40 m
routes with turns at 0.51 / 0.87 / 1.18 m, start at the midpoint of a long
edge, four goal sites, two perimeter returns. Derived, forced by the pinned
values: side return gap and goal-to-top connector. East-west goal approaches
and the return topology are inferred from the paper's figure.

Route names encode the two free choices: turn direction at the first T and
turn direction at the final junction (the middle turn is forced). ``ee`` is
the outermost east goal, ``ew`` the inner east goal, and so on.
"""

from .common import EnvSpec, corridor_walls, rnd, rnd_point, segment


def build_triple_t(params, room, name="triple_t") -> EnvSpec:
    w = params["corridor_width"]
    h = w / 2.0
    L1, L2, L3, L4 = params["run_segments"]
    EX, EY = params["envelope"]
    rx, ry = room
    cx = rx / 2.0
    x0, y0 = (rx - EX) / 2.0, (ry - EY) / 2.0

    gap = EX / 2.0 - (L2 + L4) - h - w       # maze body to side return corridor
    conn = EY - (L1 + L3) - w                # goal to top corridor connector
    if gap <= 0.02 or conn <= 0.02:
        raise ValueError(f"geometry does not close: gap={gap:.3f} conn={conn:.3f}")

    yb, yt = y0 + h, y0 + EY - h             # bottom / top corridor centerlines
    xl, xr = x0 + h, x0 + EX - h             # side corridor centerlines

    S = [cx, yb]
    T1 = [cx, yb + L1]
    CE, CW = [cx + L2, T1[1]], [cx - L2, T1[1]]
    UE, UW = [CE[0], T1[1] + L3], [CW[0], T1[1] + L3]
    gy = UE[1]
    G = {"g_ee": [CE[0] + L4, gy], "g_ew": [CE[0] - L4, gy],
         "g_ww": [CW[0] - L4, gy], "g_we": [CW[0] + L4, gy]}

    centerline = [
        segment("stem", S, T1),
        segment("cross_e", T1, CE), segment("cross_w", T1, CW),
        segment("up_e", CE, UE), segment("up_w", CW, UW),
        segment("approach_ee", UE, G["g_ee"]), segment("approach_ew", UE, G["g_ew"]),
        segment("approach_ww", UW, G["g_ww"]), segment("approach_we", UW, G["g_we"]),
    ]
    for gname, gp in G.items():
        centerline.append(segment(f"conn_{gname[2:]}", gp, [gp[0], yt]))
    top_x = sorted([xl] + [gp[0] for gp in G.values()] + [xr])
    for i in range(len(top_x) - 1):
        centerline.append(segment(f"top_{i}", [top_x[i], yt], [top_x[i + 1], yt]))
    centerline += [
        segment("side_w", [xl, yb], [xl, yt]), segment("side_e", [xr, yb], [xr, yt]),
        segment("bottom_w", [xl, yb], S), segment("bottom_e", S, [xr, yb]),
    ]

    routes = {"ee": [S, T1, CE, UE, G["g_ee"]], "ew": [S, T1, CE, UE, G["g_ew"]],
              "ww": [S, T1, CW, UW, G["g_ww"]], "we": [S, T1, CW, UW, G["g_we"]]}
    returns = {"east": [[xr, yt], [xr, yb], S], "west": [[xl, yt], [xl, yb], S]}

    return EnvSpec(
        name=name, kind="triple_t", room=list(room), boundary=None,
        walls=corridor_walls(centerline, w), centerline=centerline,
        routes={k: [rnd_point(p) for p in v] for k, v in routes.items()},
        returns={k: [rnd_point(p) for p in v] for k, v in returns.items()},
        reward_sites={k: rnd_point(p) for k, p in {"start": S, **G}.items()},
        params={**params, "derived": {"side_gap": rnd(gap), "connector": rnd(conn)}},
    )
