"""
The figures: loss curves, rate maps, heading tuning, the direction heatmap and PCA, each with its title on top and its caption and data id below.
"""

import numpy as np
from matplotlib import colormaps
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from . import analysis

# Colours are slots 1 to 3 of the data-viz reference palette. Hue carries the axis (blue east-west, orange north-south),
# lightness the direction against it.
BLUE, ORANGE, GREEN, INK = "#2a78d6", "#eb6834", "#1baf7a", "0.2"
AXIS_COLOURS = (BLUE, ORANGE)
DIRECTION_COLOURS = {0: BLUE, 1: "#8fbaf0", 2: ORANGE, 3: "#f5a785", -1: "0.8"}  # E, W, N, S, none
SEQUENTIAL = colormaps["Blues"].with_extremes(bad="0.9")  # magnitude in one hue, an unvisited bin grey
HEADING_CMAP = "twilight"  # cyclic, for heading in degrees
HEADING_TICKS = [0, 90, 180, 270, 360]
COMPASS = ["E", "N", "W", "S", "E"]

CAPTION_SPACE = 0.12  # the share of the figure's height below the panels kept for the caption
CAPTION_SIZE = 9
DATA_LINE = "Data: {}."
PCA_POINTS = 4000  # points drawn per PCA scatter
RATE_BINS_PER_M = 30  # position bins per metre of a rate map
TUNING_BINS = 36  # heading bins of a tuning curve


def new_figure(width, height):
    """
    An empty figure outside pyplot, with room kept below the panels for the caption.
    """
    fig = Figure(figsize=(width, height), layout="constrained")
    fig.get_layout_engine().set(rect=(0, CAPTION_SPACE, 1, 1 - CAPTION_SPACE))
    return fig


def finish(fig, title, caption, data_id):
    """
    Write the title on top and the caption with the data id below as figure text, and return the figure.
    """
    fig.suptitle(title)
    fig.text(0.01, CAPTION_SPACE * 0.9, f"{caption} {DATA_LINE.format(data_id)}", ha="left", va="top", wrap=True,
             fontsize=CAPTION_SIZE)
    return fig


def degrees(heading):
    """
    Heading in radians as degrees in [0, 360).
    """
    return np.degrees(heading) % 360


def draw_walls(ax, found):
    """
    The environment's walls over the room, the axes squared to it.
    """
    for (x0, y0), (x1, y1) in found["walls"]:
        ax.plot([x0, x1], [y0, y1], color="0.4", lw=0.6)
    ax.set_xlim(0, found["room"][0])
    ax.set_ylim(0, found["room"][1])
    ax.set_aspect("equal")


def loss_figure(rows, title, caption, data_id, persistence=None):
    """
    Training (solid) and validation (dashed) loss per epoch from the Trainer's rows, the persistence loss dotted, log scale.
    """
    fig = new_figure(6, 4)
    ax = fig.subplots()
    epochs = [row["epoch"] for row in rows]
    ax.plot(epochs, [row["train_loss"] for row in rows], color=BLUE, lw=1.2, label="train")
    ax.plot(epochs, [row["val_loss"] for row in rows], color=BLUE, lw=1.2, ls="--", label="validation")
    if persistence is not None:
        ax.axhline(persistence, color="0.5", ls=":", label="persistence, validation")
    ax.legend(fontsize="small")
    ax.set_yscale("log")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.set_xlabel("epoch")
    ax.set_ylabel("masked MSE (scaled position)")
    return finish(fig, title, caption, data_id)


def rate_map_figure(h, pos, units, found, title, caption, data_id):
    """
    Mean scaled activity of the chosen units by position over every frame, one panel each, with the environment's walls.
    """
    room = found["room"]
    bins = (round(RATE_BINS_PER_M * room[0]), round(RATE_BINS_PER_M * room[1]))
    span = [[0, room[0]], [0, room[1]]]
    keep = np.isfinite(pos).all(axis=1) & np.isfinite(h).all(axis=1)
    count = np.histogram2d(pos[keep, 0], pos[keep, 1], bins=bins, range=span)[0]
    fig = new_figure(3 * len(units) + 1, 3.8)
    axes = fig.subplots(1, len(units), squeeze=False)[0]
    for ax, unit in zip(axes, units):
        total = np.histogram2d(pos[keep, 0], pos[keep, 1], bins=bins, range=span, weights=h[keep, unit])[0]
        rate = np.divide(total, count, out=np.full(total.shape, np.nan), where=count > 0)
        image = ax.imshow(rate.T, origin="lower", extent=[0, room[0], 0, room[1]], vmin=0, vmax=1, cmap=SEQUENTIAL)
        draw_walls(ax, found)
        ax.set_title(f"unit {unit}")
    fig.colorbar(image, ax=list(axes), label="scaled activity")
    return finish(fig, title, caption, data_id)


def heading_tuning_figure(h, heading, axis, keep, units, title, caption, data_id):
    """
    Mean scaled activity of the chosen units by heading on the kept frames, east-west corridors left and north-south right, a row per unit.
    """
    bins = np.floor(np.nan_to_num(heading) % (2 * np.pi) / (2 * np.pi) * TUNING_BINS).astype(int)
    centres = (np.arange(TUNING_BINS) + 0.5) * 360 / TUNING_BINS
    keep = keep & np.isfinite(heading) & np.isfinite(h).all(axis=1)
    fig = new_figure(9, 1.9 * len(units) + 1.4)
    axes = fig.subplots(len(units), 2, squeeze=False, sharex=True, sharey=True)
    for a, name in enumerate(analysis.AXES):
        on = keep & (axis == a)
        count = np.bincount(bins[on], minlength=TUNING_BINS)
        for row, unit in zip(axes, units):
            total = np.bincount(bins[on], weights=h[on, unit], minlength=TUNING_BINS)
            row[a].plot(centres, np.divide(total, count, out=np.full(TUNING_BINS, np.nan), where=count > 0),
                        "o-", ms=3, lw=1, color=AXIS_COLOURS[a])
        axes[0, a].set_title(f"{name} corridors")
    for row, unit in zip(axes, units):
        row[0].set_ylabel(f"unit {unit}")
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].set_xticks(HEADING_TICKS, COMPASS)
    return finish(fig, title, caption, data_id)


def cell_heatmap_figure(means, direction, axis, title, caption, data_id):
    """
    The mean scaled activity per unit in each direction (means (H, 4)), most east-west selective first, direction and axis units marked.
    """
    order = np.argsort(-analysis.axis_selectivity(means)[:, 0])
    fig = new_figure(6, 8)
    ax, flags = fig.subplots(1, 2, sharey=True, gridspec_kw={"width_ratios": [4, 2]})
    image = ax.imshow(means[order], aspect="auto", vmin=0, vmax=1, cmap=SEQUENTIAL, interpolation="nearest")
    ax.set_xticks(range(len(analysis.DIRECTIONS)), analysis.DIRECTIONS)
    ax.set_ylabel("unit, sorted by east-west selectivity")
    marks = np.column_stack([direction, axis])[order].astype(float)
    flags.imshow(marks, aspect="auto", cmap="Greys", vmin=0, vmax=1, interpolation="nearest")
    flags.set_xticks(range(4), ["dir E-W", "dir N-S", "axis E-W", "axis N-S"], rotation=45, ha="right")
    fig.colorbar(image, ax=[ax, flags], label="scaled activity", shrink=0.6)
    return finish(fig, title, caption, data_id)


def pca_figure(pca, heading, direction, title, caption, data_id):
    """
    PC1 against PC2 and PC3 of the scores of analysis.pca_scores, coloured by heading on top and by direction of travel below.
    """
    step = max(1, len(pca["scores"]) // PCA_POINTS)
    scores, angle, label = pca["scores"][::step], heading[pca["rows"]][::step], direction[pca["rows"]][::step]
    fig = new_figure(10, 8)
    axes = fig.subplots(2, 2, sharex="col", sharey="col")
    for column, third in enumerate((1, 2)):
        image = axes[0, column].scatter(scores[:, 0], scores[:, third], c=degrees(angle), cmap=HEADING_CMAP, vmin=0,
                                        vmax=360, s=3)
        axes[1, column].scatter(scores[:, 0], scores[:, third], c=[DIRECTION_COLOURS[d] for d in label], s=3)
        axes[1, column].set_xlabel(f"PC1 ({pca['explained'][0]:.0%})")
        for row in (0, 1):
            axes[row, column].set_ylabel(f"PC{third + 1} ({pca['explained'][third]:.0%})")
    fig.colorbar(image, ax=list(axes[0]), ticks=HEADING_TICKS, label="heading (deg)")
    axes[1, 1].legend(handles=[Line2D([], [], marker="o", ls="", color=DIRECTION_COLOURS[d],
                                      label=analysis.DIRECTIONS[d] if d >= 0 else "no pass")
                               for d in DIRECTION_COLOURS], fontsize="small")
    return finish(fig, title, caption, data_id)
