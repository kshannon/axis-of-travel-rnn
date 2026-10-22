"""
Figures of the pilot in the notebook's matplotlib style: the worlds, the live probe, a frozen network, an animation.
"""

from pathlib import Path

import numpy as np
import torch
from IPython.display import clear_output, display
from matplotlib import animation, colormaps
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from . import analysis, train, worlds
from .config import (
    ANIMATION_DPI, ANIMATION_EVERY, ANIMATION_FPS, ANIMATION_STEPS, ANIMATION_UNITS, MOVING_SPEED, ROOM,
)
from .dataset import (
    INPUT_SETS, NOISY_BLOCKS, PilotDataset, fit_scaler, make_feature_layout, select_sessions, session_features,
)
from .models import MemorylessMLP

# Colours are slots 1 to 3 of the data-viz reference palette. Hue carries the axis (blue east-west, orange north-south);
# in the segments, lightness tells the two parallel ones apart.
BLUE, ORANGE, GREEN, INK = "#2a78d6", "#eb6834", "#1baf7a", "0.2"
AXIS_COLOURS = (BLUE, ORANGE)
SEGMENT_COLOURS = {0: BLUE, 1: "#8fbaf0", 2: ORANGE, 3: "#f5a785", -1: "0.75"}  # bottom, top, left, right, no segment
SEGMENT_NAMES = {**dict(enumerate(worlds.SEGMENTS)), -1: "corner"}
DISTANCE_GROUPS = (("opposite", analysis.OPPOSITE, BLUE), ("parallel", analysis.PARALLEL, ORANGE),
                   ("cross", analysis.CROSS, GREEN))
SEQUENTIAL = colormaps["Blues"].with_extremes(bad="0.9")  # magnitude in one hue; NaN (the hole, an unvisited bin) is grey
HEADING_CMAP = "twilight"  # cyclic, for heading in degrees
HEADING_TICKS = [0, 90, 180, 270, 360]
COMPASS = ["E", "N", "W", "S", "E"]

PATH_S = 60.0  # seconds of session 0 drawn as the example path
TURN_LIMIT = 20.0  # rad/s, where the turn rate histogram is cut
PROBE_CELLS = 4  # place cells drawn in the live probe, an even number
PCA_POINTS = 4000  # points drawn per PCA scatter
RATE_BINS_PER_M = 20  # position bins per metre of a rate map
TUNING_BINS = 36  # heading bins of a tuning curve
TRAIL = 40  # steps of trail behind the dot in the animation


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def new_figure(width, height):
    """
    An empty figure outside pyplot, so that nothing is shown twice; display(fig) shows it.
    """
    return Figure(figsize=(width, height), layout="constrained")


def draw_room(ax, world):
    """
    Square the axes to the room and outline the hole in the loop.
    """
    ax.set_xlim(0, ROOM[0])
    ax.set_ylim(0, ROOM[1])
    ax.set_aspect("equal")
    if world == "loop":
        x0, x1, y0, y1 = worlds.hole_bounds()
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="0.3", lw=0.8))


def degrees(heading):
    """
    Heading in radians as degrees in [0, 360).
    """
    return np.degrees(heading) % 360


def heading_scatter(ax, xy, heading, **kwargs):
    """
    A scatter of the rows of xy coloured by heading, with the colour range fixed so that panels match.
    """
    return ax.scatter(xy[:, 0], xy[:, 1], c=degrees(heading), cmap=HEADING_CMAP, vmin=0, vmax=360, **kwargs)


def segment_legend(ax):
    """
    A legend of the segment colours.
    """
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=SEGMENT_COLOURS[s], label=SEGMENT_NAMES[s])
                       for s in SEGMENT_COLOURS], fontsize="small")


def most_axis_like(h, pos, heading, speed, thr, k):
    """
    The k units of h (T, H, scaled) with the largest axis selectivity on the loop, and their east-west selectivity.
    """
    means = analysis.cell_means(h, analysis.cell_masks(pos, heading, speed, thr))
    selectivity = analysis.axis_selectivity(means)[:, 0]
    units = np.argsort(-np.abs(selectivity))[:k]
    return units, selectivity[units]


# ---------------------------------------------------------------------------
# traces of whole sessions
# ---------------------------------------------------------------------------

def session_trace(model, session, layout, scaler, cfg, noise_seed):
    """
    The noisy input "x" and every intermediate of the trace path over one whole session, each as an array (T, n).
    """
    x = session_features(session, layout, scaler)
    rng = np.random.default_rng([noise_seed, session.seed])  # the noise train.hidden_states adds
    for name, columns in layout.columns.items():
        if name in NOISY_BLOCKS:
            x[:, columns] += rng.normal(0.0, cfg["input_noise_sd"], size=x[:, columns].shape)
    with torch.no_grad():
        trace = model(torch.from_numpy(x)[None], trace=True)[2]
    return {"x": x, **{key: value[0].numpy() for key, value in trace.items()}}


# ---------------------------------------------------------------------------
# the worlds
# ---------------------------------------------------------------------------

def motion_panels(fig, grid, world, group, cfg):
    """
    The top row of a world figure: example path, occupancy, speed, heading and turn rate histograms, place centres.
    """
    pos, heading, speed = worlds.stack(group)
    heading = heading[speed > MOVING_SPEED]
    turn = np.concatenate([s.turn_rate for s in group])
    room = [0, ROOM[0], 0, ROOM[1]]

    ax = fig.add_subplot(grid[0, 0])
    walk = group[0].pos[:round(PATH_S / cfg["dt"])]
    ax.plot(walk[:, 0], walk[:, 1], lw=0.6)
    ax.set_title(f"first {PATH_S:.0f} s of session 0")
    draw_room(ax, world)

    ax = fig.add_subplot(grid[0, 1])
    bins = (round(40 * ROOM[1]), round(40 * ROOM[0]))
    ax.imshow(np.histogram2d(pos[:, 1], pos[:, 0], bins=bins, range=[[0, ROOM[1]], [0, ROOM[0]]])[0], origin="lower",
              extent=room, cmap=SEQUENTIAL)
    ax.set_title("occupancy")
    draw_room(ax, world)

    ax = fig.add_subplot(grid[0, 2])
    ax.hist(speed, bins=50, range=(0, 0.5))
    ax.set_xlabel("speed (m/s)")
    ax.set_title(f"mean {speed.mean():.3f} m/s")

    ax = fig.add_subplot(grid[0, 3])
    ax.hist(np.degrees(heading), bins=36, range=(-180, 180))
    ax.set_xlabel("heading (deg)")
    ax.set_title("heading, moving steps")

    ax = fig.add_subplot(grid[0, 4])
    ax.hist(turn, bins=50, range=(-TURN_LIMIT, TURN_LIMIT))
    ax.set_yscale("log")
    ax.set_xlabel("turn rate (rad/s)")
    ax.set_title(f"{np.mean(np.abs(turn) > TURN_LIMIT):.3f} beyond +-{TURN_LIMIT:.0f}")


def cell_panels(fig, grid, world, layout, cfg):
    """
    The rest of a world figure: the place cell centres, six place fields and three head direction tuning curves.
    """
    ax = fig.add_subplot(grid[0, 5])
    ax.scatter(*layout.place_centres.T, s=8)
    ax.set_title(f"{len(layout.place_centres)} place cell centres")
    draw_room(ax, world)

    cells = np.linspace(0, len(layout.place_centres) - 1, 6).astype(int)
    for k, (cell, rate_map) in enumerate(zip(cells, worlds.place_field_maps(cfg, layout, cells))):
        ax = fig.add_subplot(grid[1, k])
        ax.imshow(rate_map, origin="lower", extent=[0, ROOM[0], 0, ROOM[1]], vmin=0, vmax=1, cmap=SEQUENTIAL)
        ax.set_title(f"place cell {cell}")
        draw_room(ax, world)

    angles = np.linspace(-np.pi, np.pi, 361)
    curves = worlds.hd_rates(cfg, layout, angles)
    for k, cell in enumerate([0, 10, 20]):
        ax = fig.add_subplot(grid[2, 2 * k:2 * k + 2])
        ax.plot(np.degrees(angles), curves[:, cell])
        ax.set_xlabel("heading (deg)")
        ax.set_title(f"head direction cell {cell}")


def world_figure(world, layout, group, cfg):
    """
    The section 1 sanity figure of one world, from its layout and its sessions.
    """
    fig = new_figure(14, 7.5)
    grid = fig.add_gridspec(3, 6)
    motion_panels(fig, grid, world, group, cfg)
    cell_panels(fig, grid, world, layout, cfg)
    fig.suptitle(world)
    return fig


# ---------------------------------------------------------------------------
# losses and the live probe
# ---------------------------------------------------------------------------

def plot_losses(ax, curves, reference=None):
    """
    Training (solid) and validation (dashed) loss of each run, curves a list of (train, validation) lists, log scale.
    """
    for train_loss, val_loss in curves:
        line, = ax.plot(range(1, len(train_loss) + 1), train_loss, lw=1)
        ax.plot(range(1, len(val_loss) + 1), val_loss, lw=1, ls="--", color=line.get_color())
    if reference is not None:
        ax.axhline(reference, color="0.5", ls=":")
    ax.plot([], [], color=INK, lw=1, label="train")
    ax.plot([], [], color=INK, lw=1, ls="--", label="validation")
    ax.legend(fontsize="small")
    ax.set_yscale("log")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.set_xlabel("epoch")
    ax.set_ylabel("masked MSE")


def loss_figure(panels, reference):
    """
    A grid of loss panels, panels[row][column] = (title, curves) as for plot_losses; the dotted line is reference.
    """
    fig = new_figure(4.5 * len(panels[0]), 3.2 * len(panels))
    axes = fig.subplots(len(panels), len(panels[0]), squeeze=False, sharey=True)
    for row, row_panels in zip(axes, panels):
        for ax, (title, curves) in zip(row, row_panels):
            plot_losses(ax, curves, reference)
            ax.set_title(title)
    return fig


def fixed_window(arm, cfg, sessions):
    """
    One validation window of the arm's diet (its last world) as arrays: noisy input x, target y, path and shown cells.
    """
    layout = make_feature_layout(arm.input_set, cfg)
    scaler = fit_scaler(select_sessions(sessions, cfg, "train", arm.diet))
    val = select_sessions(sessions, cfg, "val", arm.diet[-1:])
    dataset = PilotDataset(val, layout, cfg, cfg["horizon"], scaler, train.NOISE_SEEDS["val"])
    item = dataset[len(dataset) // 2]
    steps = slice(item["start"], item["start"] + cfg["window"])
    session, y = val[item["session"]], item["y"].numpy()
    return {"x": item["x"][None], "y": y, "t": session.t[steps], "pos": session.pos[steps],
            "heading": session.heading[steps], "speed": session.speed[steps],
            "cells": np.sort(np.argsort(-y.var(axis=0))[:PROBE_CELLS])}  # the cells that vary most in this window


def window_trace(model, window):
    """
    The trace path of a network over the fixed window as arrays (T, n); the memoryless net has only a prediction.
    """
    with torch.no_grad():
        if isinstance(model, MemorylessMLP):
            return {"prediction": model(window["x"])[0].numpy()}
        return {key: value[0].numpy() for key, value in model(window["x"], trace=True)[2].items()}


def probe_figure(history, trace, window, thr):
    """
    Loss curves, predicted against target activity of a few place cells, and the hidden state PCA by heading.
    """
    half = PROBE_CELLS // 2
    fig = new_figure(12, 6)
    grid = fig.add_gridspec(2, PROBE_CELLS)

    ax = fig.add_subplot(grid[0, :half])
    plot_losses(ax, [(history["train_loss"], history["val_loss"])])
    ax.set_title(f"{history['arm']} seed {history['seed']}, best epoch {history['best_epoch']}")

    ax = fig.add_subplot(grid[0, half:])
    if "hidden" in trace:
        pca = analysis.pca_scores(trace["hidden"], window["pos"], window["heading"], window["speed"], thr)
        ax.plot(pca["scores"][:, 0], pca["scores"][:, 1], lw=0.4, color="0.7")
        image = heading_scatter(ax, pca["scores"][:, :2], pca["heading"], s=8)
        fig.colorbar(image, ax=ax, ticks=HEADING_TICKS, label="heading (deg)")
        ax.set_xlabel(f"PC1 ({pca['explained'][0]:.0%})")
        ax.set_ylabel(f"PC2 ({pca['explained'][1]:.0%})")
        ax.set_title("hidden state, one window")
    else:
        ax.set_axis_off()
        ax.set_title("memoryless: no hidden state")

    for k, cell in enumerate(window["cells"]):
        ax = fig.add_subplot(grid[1, k])
        ax.plot(window["t"], window["y"][:, cell], color=INK, lw=1, label="target")
        ax.plot(window["t"], trace["prediction"][:, cell], color=BLUE, lw=1, label="prediction")
        ax.set_xlabel("time (s)")
        ax.set_title(f"place cell {cell}")
        if k == 0:
            ax.legend(fontsize="small")
    return fig


def live_probe(cfg, sessions, thr, every):
    """
    The on_epoch callback for train.run_sweep: every `every` epochs it redraws the probe on the arm's fixed window.
    """
    arms = {arm.name: arm for input_set in INPUT_SETS for arm in train.arms_for(input_set)}
    windows = {}

    def probe(epoch, model, history):
        if epoch % every:
            return
        if history["arm"] not in windows:
            windows[history["arm"]] = fixed_window(arms[history["arm"]], cfg, sessions)
        window = windows[history["arm"]]
        fig = probe_figure(history, window_trace(model, window), window, thr)
        clear_output(wait=True)
        display(fig)

    return probe


# ---------------------------------------------------------------------------
# after training, on whole test sessions (h is the hidden state scaled to [0, 1] per unit, pos and the rest per step)
# ---------------------------------------------------------------------------

def rate_map_figure(h, pos, units, world):
    """
    Mean activity of the chosen units by position over all steps, one panel each.
    """
    bins = (round(RATE_BINS_PER_M * ROOM[0]), round(RATE_BINS_PER_M * ROOM[1]))
    span = [[0, ROOM[0]], [0, ROOM[1]]]
    count = np.histogram2d(pos[:, 0], pos[:, 1], bins=bins, range=span)[0]
    fig = new_figure(3 * len(units) + 1, 3.3)
    axes = fig.subplots(1, len(units), squeeze=False)[0]
    for ax, unit in zip(axes, units):
        total = np.histogram2d(pos[:, 0], pos[:, 1], bins=bins, range=span, weights=h[:, unit])[0]
        rate = np.divide(total, count, out=np.full(total.shape, np.nan), where=count > 0)
        image = ax.imshow(rate.T, origin="lower", extent=[0, ROOM[0], 0, ROOM[1]], vmin=0, vmax=1, cmap=SEQUENTIAL)
        ax.set_title(f"unit {unit}")
        draw_room(ax, world)
    fig.colorbar(image, ax=list(axes), label="scaled activity")
    return fig


def heading_tuning_figure(h, pos, heading, speed, units, thr):
    """
    Mean activity of the chosen units by heading within each segment of the loop (a row per unit), moving steps only.
    """
    segment = worlds.classify_segment(pos)
    moving = speed > thr["moving_speed_m_s"]
    bins = np.floor(heading % (2 * np.pi) / (2 * np.pi) * TUNING_BINS).astype(int)
    centres = (np.arange(TUNING_BINS) + 0.5) * 360 / TUNING_BINS
    fig = new_figure(12, 1.9 * len(units) + 0.8)
    axes = fig.subplots(len(units), 4, squeeze=False, sharex=True, sharey=True)
    for s in range(4):
        keep = moving & (segment == s)
        count = np.bincount(bins[keep], minlength=TUNING_BINS)
        for row, unit in zip(axes, units):
            total = np.bincount(bins[keep], weights=h[keep, unit], minlength=TUNING_BINS)
            row[s].plot(centres, np.divide(total, count, out=np.full(TUNING_BINS, np.nan), where=count > 0),
                        "o-", ms=3, lw=1, color=AXIS_COLOURS[s // 2])
        axes[0, s].set_title(worlds.SEGMENTS[s])
    for row, unit in zip(axes, units):
        row[0].set_ylabel(f"unit {unit}")
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].set_xticks(HEADING_TICKS, COMPASS)
    return fig


def cell_heatmap_figure(means, direction, axis):
    """
    The 8 numbers per unit the tests read (means (H, 8)), most east-west first, with direction and axis units marked.
    """
    order = np.argsort(-analysis.axis_selectivity(means)[:, 0])
    fig = new_figure(7, 8)
    ax, flags = fig.subplots(1, 2, sharey=True, gridspec_kw={"width_ratios": [8, 1.5]})
    image = ax.imshow(means[order], aspect="auto", vmin=0, vmax=1, cmap=SEQUENTIAL, interpolation="nearest")
    ax.set_xticks(range(len(analysis.CELLS)), analysis.CELLS, rotation=45, ha="right")
    ax.set_ylabel("unit, sorted by east-west selectivity")
    flags.imshow(np.column_stack([direction, axis])[order].astype(float), aspect="auto", cmap="Greys", vmin=0, vmax=1,
                 interpolation="nearest")
    flags.set_xticks(range(2), ["direction", "axis"], rotation=45, ha="right")
    fig.colorbar(image, ax=[ax, flags], label="scaled activity", shrink=0.6)
    return fig


def distance_figure(means):
    """
    The distances between the 8 mean vectors (means (H, 8)) with the pairs of 8.4 outlined, and their three means.
    """
    vectors = means.T
    matrix = np.linalg.norm(vectors[:, None] - vectors[None], axis=2)
    distances = analysis.population_distances(means)
    fig = new_figure(10, 4.5)
    ax, bars = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1.4, 1]})
    image = ax.imshow(matrix, cmap=SEQUENTIAL)
    for _, pairs, colour in DISTANCE_GROUPS:
        for i, j in pairs:
            for row, column in ((i, j), (j, i)):
                ax.add_patch(Rectangle((column - 0.5, row - 0.5), 1, 1, fill=False, ec=colour, lw=2))
    ax.set_xticks(range(len(analysis.CELLS)), analysis.CELLS, rotation=45, ha="right")
    ax.set_yticks(range(len(analysis.CELLS)), analysis.CELLS)
    fig.colorbar(image, ax=ax, label="distance", shrink=0.8)
    bars.bar([name for name, _, _ in DISTANCE_GROUPS], [distances[name] for name, _, _ in DISTANCE_GROUPS],
             color=[colour for _, _, colour in DISTANCE_GROUPS])
    bars.set_ylabel("mean distance")
    bars.set_title(f"opposite / cross {distances['opposite_over_cross']:.2f}, "
                   f"parallel / cross {distances['parallel_over_cross']:.2f}")
    return fig


def pca_figure(h, pos, heading, speed, thr):
    """
    The first three PCs of the moving steps as PC1 against PC2 and PC3, coloured by heading and by segment of the loop.
    """
    pca = analysis.pca_scores(h, pos, heading, speed, thr)
    step = max(1, len(pca["scores"]) // PCA_POINTS)
    scores, angle, segment = (pca[key][::step] for key in ("scores", "heading", "segment"))
    fig = new_figure(10, 8)
    axes = fig.subplots(2, 2, sharex="col", sharey="col")
    for column, third in enumerate((1, 2)):
        image = heading_scatter(axes[0, column], scores[:, [0, third]], angle, s=3)
        axes[1, column].scatter(scores[:, 0], scores[:, third], c=[SEGMENT_COLOURS[s] for s in segment], s=3)
        axes[1, column].set_xlabel(f"PC1 ({pca['explained'][0]:.0%})")
        axes[1, column].set_ylabel(f"PC{third + 1} ({pca['explained'][third]:.0%})")
    fig.colorbar(image, ax=list(axes[0]), ticks=HEADING_TICKS, label="heading (deg)")
    segment_legend(axes[1, 1])
    return fig


def released_figure(values, minimum, reference):
    """
    Released axis units as a percent of units per seed (values[input set][group] a list of fractions), against the bar.
    """
    fig = new_figure(4.5 * len(values), 3.8)
    axes = fig.subplots(1, len(values), squeeze=False, sharey=True)[0]
    for ax, (input_set, groups) in zip(axes, values.items()):
        for k, (colour, fractions) in enumerate(zip((BLUE, ORANGE, GREEN), groups.values())):
            n = len(fractions)
            spread = (np.arange(n) - (n - 1) / 2) * 0.4 / max(n, 2)
            ax.scatter(k + spread, 100 * np.array(fractions), s=18, color=colour)
        ax.axhline(100 * minimum, color=INK, ls=":", label="minimum fraction of units")
        ax.axhline(100 * reference[input_set], color=GREEN, ls="--", label="95th percentile, untrained")
        ax.set_xticks(range(len(groups)), list(groups), rotation=20, ha="right")
        ax.set_title(input_set)
    axes[0].set_ylabel("released axis units (% of units)")
    axes[0].legend(fontsize="small")
    return fig


# ---------------------------------------------------------------------------
# the animation
# ---------------------------------------------------------------------------

def animate_session(path, pos, heading, speed, h, thr, n_steps=ANIMATION_STEPS, every=ANIMATION_EVERY):
    """
    Save a gif of the first n_steps of a loop session (h scaled) streamed through a frozen net; return the path.
    """
    units, selectivity = most_axis_like(h, pos, heading, speed, thr, ANIMATION_UNITS)
    scores = analysis.pca_scores(h, pos, heading, np.ones(len(h)), thr)["scores"]  # all steps, not only moving ones
    angle = degrees(heading)
    fig = new_figure(10, 3.4)
    ax_map, ax_pca, ax_units = fig.subplots(1, 3)

    draw_room(ax_map, "loop")
    ax_map.set_title("rat on the map")
    trail_map, = ax_map.plot([], [], lw=1, color="0.5")
    dot_map = ax_map.scatter(pos[:1, 0], pos[:1, 1], c=angle[:1], cmap=HEADING_CMAP, vmin=0, vmax=360, s=60,
                             edgecolor=INK, zorder=3)

    ax_pca.plot(scores[:n_steps, 0], scores[:n_steps, 1], lw=0.4, color="0.8")
    ax_pca.set_xlabel("PC1")
    ax_pca.set_ylabel("PC2")
    ax_pca.set_title("hidden state, coloured by heading")
    trail_pca, = ax_pca.plot([], [], lw=1, color="0.5")
    dot_pca = ax_pca.scatter(scores[:1, 0], scores[:1, 1], c=angle[:1], cmap=HEADING_CMAP, vmin=0, vmax=360, s=60,
                             edgecolor=INK, zorder=3)

    bars = ax_units.barh(range(len(units)), np.zeros(len(units)), color=[AXIS_COLOURS[int(s < 0)] for s in selectivity])
    ax_units.set_xlim(0, 1)
    ax_units.set_yticks(range(len(units)), [f"unit {u}" for u in units])
    ax_units.invert_yaxis()
    ax_units.set_xlabel("scaled activity")
    ax_units.set_title("largest axis selectivity\n(blue east-west, orange north-south)")

    def draw(t):
        past = slice(max(0, t - TRAIL), t + 1)
        trail_map.set_data(pos[past, 0], pos[past, 1])
        dot_map.set_offsets(pos[t:t + 1])
        dot_map.set_array(angle[t:t + 1])
        trail_pca.set_data(scores[past, 0], scores[past, 1])
        dot_pca.set_offsets(scores[t:t + 1, :2])
        dot_pca.set_array(angle[t:t + 1])
        for bar, activity in zip(bars, h[t, units]):
            bar.set_width(activity)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    movie = animation.FuncAnimation(fig, draw, frames=range(0, n_steps, every))
    movie.save(path, writer=animation.PillowWriter(fps=ANIMATION_FPS), dpi=ANIMATION_DPI)
    return path
