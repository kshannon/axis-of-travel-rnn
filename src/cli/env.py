"""
The env group: list and inspect the environment configs in the checkout.
"""

import math

from environments import list_environments, load_environment
from proj_helpers.paths import environments_dir
from ._output import emit, fail, lines, table


def register(commands) -> None:
    p = commands.add_parser(
        "list", help="list every environment config with its hash",
        description="List every environment config with its type, walls, routes and "
                    "hash. Reads configs/environments/*.yaml; writes nothing.")
    p.add_argument("--json", action="store_true", help="print the same data as JSON")
    p.set_defaults(func=list_envs)

    p = commands.add_parser(
        "inspect", help="describe one environment's geometry",
        description="Describe one environment: geometry summary, or the canonical "
                    "spec as JSON. Reads configs/environments/<env>.yaml and the base "
                    "config it names; writes nothing.")
    p.add_argument("env", metavar="<env>", help="config name, e.g. triple_t")
    p.add_argument("--json", action="store_true", help="print the same data as JSON")
    p.set_defaults(func=inspect_env)


def _path_length(waypoints) -> float:
    return sum(math.dist(a, b) for a, b in zip(waypoints[:-1], waypoints[1:]))


def _named_lengths(paths: dict) -> str:
    return ", ".join(f"{k} ({_path_length(v):.2f} m)"
                     for k, v in sorted(paths.items())) or "none"


def list_envs(args) -> int:
    names = list_environments()
    if not names:
        print(f"no environment configs under {environments_dir()}")
        return 0
    rows = []
    for name in names:
        spec = load_environment(name)
        rows.append({"name": spec.name, "type": spec.kind,
                     "room": f"{spec.room[0]:.2f} x {spec.room[1]:.2f} m",
                     "walls": len(spec.walls), "routes": len(spec.routes),
                     "hash": spec.hash})
    emit(rows, table(rows, ["name", "type", "room", "walls", "routes", "hash"]),
         as_json=args.json)
    return 0


def inspect_env(args) -> int:
    try:
        spec = load_environment(args.env)
    except FileNotFoundError as e:
        return fail(str(e))
    pairs = [
        ("config", environments_dir() / f"{spec.name}.yaml"),
        ("type", spec.kind),
        ("room", f"{spec.room[0]:.2f} x {spec.room[1]:.2f} m"),
        ("params", {k: v for k, v in spec.params.items() if k != "derived"}),
    ]
    if "derived" in spec.params:
        pairs.append(("derived", spec.params["derived"]))
    pairs += [
        ("boundary", f"polygon, {len(spec.boundary)} vertices" if spec.boundary
         else "room rectangle"),
        ("walls", len(spec.walls)),
        ("centerline", f"{len(spec.centerline)} segments"),
        ("routes", _named_lengths(spec.routes)),
        ("returns", _named_lengths(spec.returns)),
        ("reward sites", ", ".join(f"{k} ({p[0]:.3f}, {p[1]:.3f})"
                                  for k, p in spec.reward_sites.items()) or "none"),
    ]
    emit({**spec.canonical(), "hash": spec.hash},
         lines(f"{spec.name}  [{spec.hash}]", pairs), as_json=args.json)
    return 0
