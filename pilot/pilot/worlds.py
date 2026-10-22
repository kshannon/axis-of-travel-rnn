"""
The two worlds, their cell layouts, session simulation with save and load, the segment classifier and the data checks.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ratinabox import utils
from ratinabox.Agent import Agent
from ratinabox.Environment import Environment
from ratinabox.Neurons import HeadDirectionCells, PlaceCells

from .config import (
    ALONG_DEG, CORRIDOR, DATA_DIR, DATA_KEYS, DRIFT_RATIO, MAX_ACROSS_RATE, MAX_OPEN_RESULTANT, MAX_STALL_S, MEAN_LAPS,
    MIN_ALONG_FRACTION, MIN_DIRECTION_S, MOVING_SPEED, REPEL_FRACTION, ROOM, STALL_SPEED, STEER_SPEED, WAYPOINT_RADIUS,
    WORLDS,
)

SEGMENTS = ("bottom", "top", "left", "right")
SEGMENT_ANGLE = np.array([0.0, 0.0, np.pi / 2, np.pi / 2])  # corridor direction: east for bottom and top, else north
DIRECTION_LABELS = ("E", "W", "E", "W", "N", "S", "N", "S")  # for bottom, bottom, top, top, left, left, right, right
RATE_CHUNK = 2000  # positions per place cell call, to bound memory
FIELD_GRID = 50  # points per metre of a place field map


@dataclass(frozen=True)
class CellLayout:
    world: str
    place_centres: np.ndarray  # (n_pc, 2) metres
    place_width: float
    wall_geometry: str
    n_hd: int
    hd_spread_deg: float


@dataclass
class SessionData:
    world: str
    seed: int
    t: np.ndarray  # (T,) seconds, the first kept step is dt
    pos: np.ndarray  # (T, 2) metres
    heading: np.ndarray  # (T,) radians, 0 = east, counterclockwise, from the agent's smoothed head direction
    speed: np.ndarray  # (T,) m/s
    turn_rate: np.ndarray  # (T,) rad/s as RatInABox measures it, with the spikes at wall bounces left in
    place: np.ndarray  # (T, n_pc) float32 in [0, 1]
    hd: np.ndarray  # (T, n_hd) float32 in [0, 1]

    def save(self, path):
        """
        Write every field to one compressed npz, through a part file so an interrupted write is never loaded.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        with open(part, "wb") as f:
            np.savez_compressed(f, **vars(self))
        part.replace(path)

    @classmethod
    def load(cls, path):
        """
        The session written by save.
        """
        with np.load(path) as z:
            fields = {key: z[key] for key in z.files}
        fields["world"] = str(fields["world"])
        fields["seed"] = int(fields["seed"])
        return cls(**fields)


# ---------------------------------------------------------------------------
# worlds and cell layouts
# ---------------------------------------------------------------------------

def hole_bounds(size=ROOM, width=CORRIDOR):
    """
    The hole as (x_low, x_high, y_low, y_high): the room less the corridor width on every side.
    """
    return width, size[0] - width, width, size[1] - width


def make_environment(kind, size=ROOM, width=CORRIDOR):
    """
    The room of this size, with the central hole that leaves a corridor of this width when kind is loop.
    """
    assert kind in WORLDS
    env = Environment(params={"scale": size[1], "aspect": size[0] / size[1], "boundary_conditions": "solid"})
    if kind == "loop":
        x0, x1, y0, y1 = hole_bounds(size, width)
        env.add_hole([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    return env


def in_hole(pos, size=ROOM, width=CORRIDOR):
    """
    True for each row of pos (N, 2) strictly inside the hole.
    """
    x0, x1, y0, y1 = hole_bounds(size, width)
    return (pos[:, 0] > x0) & (pos[:, 0] < x1) & (pos[:, 1] > y0) & (pos[:, 1] < y1)


def make_layout(world, cfg, seed):
    """
    The place cell centres of a world: RatInABox's jittered grid, with any centre out of bounds redrawn with our RNG.
    """
    np.random.seed(seed)  # sample_positions draws from the legacy global generator
    rng = np.random.default_rng(seed)
    env = make_environment(world)
    centres = env.sample_positions(cfg["place_n"], method="uniform_jitter")
    assert len(centres) == cfg["place_n"]  # sample_positions returns more than asked when its grid has more points
    for i, centre in enumerate(centres):
        while not env.check_if_position_is_in_environment(centre):  # the jitter can push a centre out or into the hole
            centre = rng.uniform([0.0, 0.0], ROOM)
        centres[i] = centre
    assert world == "open_field" or not in_hole(centres).any()
    return CellLayout(world=world, place_centres=centres, place_width=cfg["place_width"],
                      wall_geometry=cfg["wall_geometry"][world], n_hd=cfg["hd_n"], hd_spread_deg=cfg["hd_spread_deg"])


def make_layouts(cfg):
    """
    The layout of each world, from its fixed layout seed.
    """
    return {world: make_layout(world, cfg, cfg["layout_seed"][world]) for world in WORLDS}


def make_agent(cfg, world, size=ROOM, width=CORRIDOR, repel=None):
    """
    A RatInABox agent in the world; speed_mean is the Rayleigh scale, so the target mean is converted.
    """
    params = {"dt": cfg["dt"], "speed_mean": utils.get_rayleigh_sigma(cfg["speed_mean"])}
    if repel is not None:
        params["wall_repel_distance"] = repel
    return Agent(make_environment(world, size, width), params=params)


def corner_waypoints(size=ROOM, width=CORRIDOR):
    """
    The four corners of the corridor centre line (4, 2), counterclockwise from the bottom left.
    """
    low, right, top = width / 2, size[0] - width / 2, size[1] - width / 2
    return np.array([[low, low], [right, low], [right, top], [low, top]])


def walk(agent, steps, rng, size=ROOM, width=CORRIDOR, ratio=DRIFT_RATIO):
    """
    Steer a loop agent for steps updates towards the next corner of the centre line, turning round after random laps.
    """
    corners = corner_waypoints(size, width)
    target = int(np.argmin(np.linalg.norm(corners - agent.pos, axis=1)))
    direction = int(rng.choice([1, -1]))
    corners_left = 4 * rng.geometric(1 / MEAN_LAPS)
    for _ in range(steps):
        if np.linalg.norm(corners[target] - agent.pos) < WAYPOINT_RADIUS:
            corners_left -= 1
            if corners_left == 0:
                direction = -direction
                corners_left = 4 * rng.geometric(1 / MEAN_LAPS)
            target = (target + direction) % 4
        to_target = corners[target] - agent.pos
        agent.update(drift_velocity=STEER_SPEED * to_target / np.linalg.norm(to_target),
                     drift_to_random_strength_ratio=ratio)


def place_rates(cfg, layout, pos):
    """
    The place cell rates (len(pos), n_pc) float32 at each position, with the neuron noise left off.
    """
    agent = make_agent(cfg, layout.world)
    cells = PlaceCells(agent, params={"widths": layout.place_width, "place_cell_centres": layout.place_centres,
                                      "wall_geometry": layout.wall_geometry})
    chunks = [cells.get_state(evaluate_at=None, pos=pos[i:i + RATE_CHUNK]) for i in range(0, len(pos), RATE_CHUNK)]
    return np.concatenate(chunks, axis=1).T.astype(np.float32)


def hd_rates(cfg, layout, heading):
    """
    The head direction cell rates (len(heading), n_hd) float32 at each heading in radians.
    """
    agent = make_agent(cfg, layout.world)
    cells = HeadDirectionCells(agent, params={"n": layout.n_hd, "angular_spread_degrees": layout.hd_spread_deg})
    rates = [cells.get_state(evaluate_at=None, head_direction=np.array([np.cos(h), np.sin(h)]))[:, 0] for h in heading]
    return np.array(rates, dtype=np.float32)


def place_field_maps(cfg, layout, cells):
    """
    Rate maps (len(cells), ny, nx) over the room, FIELD_GRID points per metre, indexed [cell, y, x] with y rising.
    """
    nx, ny = (round(FIELD_GRID * extent) for extent in ROOM)
    xs, ys = np.meshgrid((np.arange(nx) + 0.5) / FIELD_GRID, (np.arange(ny) + 0.5) / FIELD_GRID)
    grid = np.column_stack([xs.ravel(), ys.ravel()])
    maps = place_rates(cfg, layout, grid)[:, cells].T.reshape(len(cells), ny, nx).copy()
    if layout.world == "loop":
        maps[:, in_hole(grid).reshape(ny, nx)] = np.nan
    return maps


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

def run_agent(cfg, world, seed, size=ROOM, width=CORRIDOR, repel=None, ratio=None):
    """
    The agent alone, burn-in dropped, as a dict of t, pos, heading, speed and turn_rate; steered when ratio is given.
    """
    np.random.seed(seed)  # RatInABox draws everything, including the start, from the legacy global generator
    rng = np.random.default_rng(seed)  # the steering's choices of direction and laps
    agent = make_agent(cfg, world, size, width, repel)
    n_burn = round(cfg["burn_in_s"] / cfg["dt"])
    steps = n_burn + round(cfg["session_s"] / cfg["dt"])
    if ratio is None:
        for _ in range(steps):
            agent.update()
    else:
        walk(agent, steps, rng, size, width, ratio)
    kept = {key: np.array(values)[n_burn:] for key, values in agent.history.items()}
    heading = np.arctan2(kept["head_direction"][:, 1], kept["head_direction"][:, 0])
    return {"t": kept["t"] - n_burn * cfg["dt"], "pos": kept["pos"], "heading": heading,
            "speed": np.linalg.norm(kept["vel"], axis=1), "turn_rate": kept["rot_vel"]}


def simulate(cfg, layout, seed):
    """
    One session: the agent alone (steered in the loop, stock in the open field), then the cell rates along its path.
    """
    if layout.world == "loop":
        path = run_agent(cfg, "loop", seed, repel=CORRIDOR * REPEL_FRACTION, ratio=DRIFT_RATIO)
    else:
        path = run_agent(cfg, "open_field", seed)
    return SessionData(world=layout.world, seed=seed, **path, place=place_rates(cfg, layout, path["pos"]),
                       hd=hd_rates(cfg, layout, path["heading"]))


def data_hash(cfg):
    """
    A short hash of every setting that changes a session: the DATA_KEYS of the preset, the room and the steering.
    """
    settings = [cfg[key] for key in DATA_KEYS]
    settings += [ROOM, CORRIDOR, DRIFT_RATIO, REPEL_FRACTION, WAYPOINT_RADIUS, MEAN_LAPS, STEER_SPEED]
    return hashlib.sha256(repr(settings).encode()).hexdigest()[:8]


def session_path(cfg, world, seed):
    """
    Where a session lives: datasets/pilot/sessions/<preset>_<data hash>/<world>_<seed>.npz.
    """
    return DATA_DIR / "sessions" / f"{cfg['name']}_{data_hash(cfg)}" / f"{world}_{seed}.npz"


def n_sessions(cfg):
    """
    Sessions per world.
    """
    return cfg["n_train"] + cfg["n_val"] + cfg["n_test"]


def split_of(cfg, index):
    """
    train, val or test for the session with this index within its world.
    """
    if index < cfg["n_train"]:
        return "train"
    if index < cfg["n_train"] + cfg["n_val"]:
        return "val"
    return "test"


def load_or_run(cfg, layout, seed):
    """
    The session of this seed: loaded when its file exists, otherwise simulated and saved.
    """
    path = session_path(cfg, layout.world, seed)
    if path.exists():
        return SessionData.load(path)
    print(f"simulating {layout.world} seed {seed}")
    session = simulate(cfg, layout, seed)
    session.save(path)
    return session


def load_sessions(cfg, layouts):
    """
    {world: [SessionData]} in session index order, simulating and saving the missing ones.
    """
    seeds = {world: [cfg["session_seed_base"][world] + i for i in range(n_sessions(cfg))] for world in WORLDS}
    return {world: [load_or_run(cfg, layouts[world], seed) for seed in seeds[world]] for world in WORLDS}


# ---------------------------------------------------------------------------
# segments of the loop
# ---------------------------------------------------------------------------

def classify_segment(pos, size=ROOM, width=CORRIDOR):
    """
    The segment of each row of pos (N, 2) as an index into SEGMENTS, or -1 in a corner, the hole or outside the room.
    """
    x0, x1, y0, y1 = hole_bounds(size, width)
    along_x = (pos[:, 0] > x0) & (pos[:, 0] < x1)
    along_y = (pos[:, 1] > y0) & (pos[:, 1] < y1)
    segment = np.full(len(pos), -1)
    segment[(pos[:, 1] < y0) & along_x] = 0
    segment[(pos[:, 1] > y1) & along_x] = 1
    segment[(pos[:, 0] < x0) & along_y] = 2
    segment[(pos[:, 0] > x1) & along_y] = 3
    return segment


def travel_direction(heading, segment):
    """
    +1 when heading is within ALONG_DEG of east (bottom, top) or north (left, right), -1 near west or south, else 0.
    """
    offset = np.angle(np.exp(1j * (heading - SEGMENT_ANGLE[segment])))
    limit = np.deg2rad(ALONG_DEG)
    direction = np.zeros(len(heading), dtype=int)
    direction[np.abs(offset) < limit] = 1
    direction[np.abs(offset) > np.pi - limit] = -1
    direction[segment < 0] = 0
    return direction


# ---------------------------------------------------------------------------
# section 1 data checks
# ---------------------------------------------------------------------------

def longest_run(mask):
    """
    The length of the longest run of True in a boolean array.
    """
    edges = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(int), [0]])))
    return int((edges[1::2] - edges[::2]).max(initial=0))


def bleed(cfg, layout, pos):
    """
    Pairs of cell and position with a line through the hole, those an unwalled field reaches, the largest walled rate.
    """
    rates = place_rates(cfg, layout, pos)
    centres = layout.place_centres
    s = np.linspace(0.0, 1.0, 201)[:, None, None, None]
    line = centres[None, :, None, :] + s * (pos[None, None, :, :] - centres[None, :, None, :])  # (201, n_pc, P, 2)
    through = in_hole(line.reshape(-1, 2)).reshape(line.shape[:3]).any(axis=0).T  # (P, n_pc)
    gap = np.linalg.norm(pos[:, None, :] - centres[None, :, :], axis=2)
    open_rates = np.exp(-gap ** 2 / (2 * layout.place_width ** 2))
    return int(through.sum()), int((through & (open_rates > 0.01)).sum()), float(rates[through].max(initial=0.0))


def across_the_hole(cfg, layout):
    """
    The place cell nearest the middle of the bottom segment: its rate at its own centre and straight across the hole.
    """
    bottom = np.flatnonzero(classify_segment(layout.place_centres) == 0)
    middle = np.array([ROOM[0] / 2, CORRIDOR / 2])
    i = bottom[np.argmin(np.linalg.norm(layout.place_centres[bottom] - middle, axis=1))]
    centre = layout.place_centres[i]
    rates = place_rates(cfg, layout, np.array([centre, [centre[0], ROOM[1] - centre[1]]]))[:, i]
    return centre, float(rates[0]), float(rates[1])


def moving_in_segments(pos, heading, speed, size=ROOM, width=CORRIDOR):
    """
    Per moving step in a segment: the segment, the heading minus the corridor direction, and the travel direction.
    """
    segment = classify_segment(pos, size, width)
    inside = (segment >= 0) & (speed > MOVING_SPEED)
    segment = segment[inside]
    return segment, heading[inside] - SEGMENT_ANGLE[segment], travel_direction(heading[inside], segment)


def along_axis(pos, heading, speed, size=ROOM, width=CORRIDOR):
    """
    The share of moving steps in a segment heading along it, the same per segment, and the doubled angle resultant.
    """
    segment, offset, direction = moving_in_segments(pos, heading, speed, size, width)
    along = direction != 0
    per_segment = [along[segment == s].mean() if (segment == s).any() else np.nan for s in range(4)]
    return along.mean(), per_segment, abs(np.mean(np.exp(2j * offset)))


def cell_seconds(pos, heading, speed, dt, size=ROOM, width=CORRIDOR):
    """
    The seconds in each of the 8 segment and direction cells (bottom E, bottom W, top E, top W, left N, ...).
    """
    segment, _, direction = moving_in_segments(pos, heading, speed, size, width)
    return np.array([(direction[segment == s] == d).sum() * dt for s in range(4) for d in (1, -1)])


def stack(group):
    """
    The position, heading and speed of the sessions joined end to end.
    """
    return tuple(np.concatenate([getattr(s, name) for s in group]) for name in ("pos", "heading", "speed"))


def check_sessions(cfg, layouts, sessions):
    """
    The section 1 checks on the loaded sessions as (name, status, measured) with status pass or FAIL.
    """
    loop, field = sessions["loop"], sessions["open_field"]
    pos, heading, speed = stack(loop)
    results = []

    n_hole = int(in_hole(pos).sum())
    n_outside = int(((pos < 0) | (pos > np.array(ROOM))).any(axis=1).sum())
    results.append(("no position inside the hole", "pass" if n_hole == n_outside == 0 else "FAIL",
                    f"{n_hole} of {len(pos)} loop steps in the hole, {n_outside} outside the room"))

    seconds = cell_seconds(pos, heading, speed, cfg["dt"])
    text = ", ".join(f"{SEGMENTS[i // 2]} {DIRECTION_LABELS[i]} {sec:.0f} s" for i, sec in enumerate(seconds))
    results.append(("all four segments, both directions", "pass" if seconds.min() >= MIN_DIRECTION_S else "FAIL",
                    f"least {seconds.min():.1f} s (needs {MIN_DIRECTION_S:.0f}): {text}"))

    angle = np.concatenate([s.heading[s.speed > MOVING_SPEED] for s in field])
    one, two, four = (abs(np.mean(np.exp(1j * k * angle))) for k in (1, 2, 4))
    uniform = "pass" if max(one, two) < MAX_OPEN_RESULTANT else "FAIL"
    results.append(("heading roughly uniform in the open field", uniform,
                    f"resultant length {one:.3f} on the angles, {two:.3f} on the doubled angles "
                    f"(limit {MAX_OPEN_RESULTANT}), {four:.3f} on the quadrupled"))

    along, per_segment, resultant = along_axis(pos, heading, speed)
    baseline = along_axis(*stack(field))[0]
    results.append(("heading on two axes in the loop", "pass" if along >= MIN_ALONG_FRACTION else "FAIL",
                    f"{along:.2f} of moving steps in a segment run along it (limit {MIN_ALONG_FRACTION}; a uniform "
                    f"heading gives 0.5 and the open field in the same regions {baseline:.2f}), resultant length "
                    f"{resultant:.2f} on the doubled angles from the corridor; per segment "
                    + ", ".join(f"{SEGMENTS[s]} {per_segment[s]:.2f}" for s in range(4))))

    centre, own, across = across_the_hole(cfg, layouts["loop"])
    probes = loop[0].pos[::max(1, len(loop[0].pos) // 120)]
    n_through, n_reached, worst = bleed(cfg, layouts["loop"], probes)
    ok = across <= MAX_ACROSS_RATE and worst <= MAX_ACROSS_RATE
    results.append(("no place field across the hole", "pass" if ok else "FAIL",
                    f"cell at ({centre[0]:.2f}, {centre[1]:.2f}): rate {own:.3f} at its centre, {across:.2g} straight "
                    f"across; {n_through} cell and position pairs have a line through the hole, {n_reached} of them "
                    f"within reach of an unwalled field, largest rate among them {worst:.2g}"))

    for name, group in (("loop", loop), ("open field", field)):
        stall = max(longest_run(s.speed < STALL_SPEED) for s in group) * cfg["dt"]
        mean = np.mean(np.concatenate([s.speed for s in group]))
        status = "pass" if stall <= MAX_STALL_S else "FAIL"
        results.append((f"agent keeps moving, {name}", status,
                        f"longest time below {STALL_SPEED} m/s is {stall:.1f} s (limit {MAX_STALL_S}); mean speed "
                        f"{mean:.3f} m/s against the {cfg['speed_mean']} target"))
    return results
