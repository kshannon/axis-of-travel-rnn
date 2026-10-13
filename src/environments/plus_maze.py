"""Plus maze: two axes, four arms. A development environment, small enough
to debug the pipeline on before the triple-T."""

from .common import EnvSpec, corridor_walls, rnd_point, segment


def build_plus_maze(params, room, name="plus_maze") -> EnvSpec:
    w, arm = params["corridor_width"], params["arm_length"]
    cx, cy = room[0] / 2.0, room[1] / 2.0
    C = [cx, cy]
    ends = {"n": [cx, cy + arm], "s": [cx, cy - arm],
            "e": [cx + arm, cy], "w": [cx - arm, cy]}
    centerline = [segment(f"arm_{k}", C, p) for k, p in ends.items()]
    routes = {"s_n": [ends["s"], C, ends["n"]], "w_e": [ends["w"], C, ends["e"]],
              "s_e": [ends["s"], C, ends["e"]], "s_w": [ends["s"], C, ends["w"]]}
    return EnvSpec(name=name, kind="plus_maze", room=list(room), boundary=None,
                   walls=corridor_walls(centerline, w), centerline=centerline,
                   routes={k: [rnd_point(p) for p in v] for k, v in routes.items()},
                   returns={}, reward_sites={k: rnd_point(p) for k, p in ends.items()},
                   params=dict(params))
