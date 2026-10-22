"""
The axis of travel measures of hidden states, on numpy arrays: passes along the triple-T's corridors labelled by segment and direction of travel, the direction and axis tests, the arena test, the population distances, PCA and decoders.
"""

from pathlib import Path

import numpy as np
import yaml
from scipy import sparse

from .blocks.geometry import geometry

# A direction is 2 * axis + (1 when the travel runs against the axis), the axis 0 east-west (a corridor at 0 degrees) and
# 1 north-south (at 90 degrees). So 0 east, 1 west, 2 north, 3 south.
DIRECTIONS = ("E", "W", "N", "S")
AXES = ("east-west", "north-south")

# A pass is a maximal stretch of running frames (phase outbound or return, speed over the threshold) inside one corridor
# segment, one run and one trip. Its direction is the sign of its net displacement along the segment, from position.
RUNNING_PHASES = ("outbound", "return")
REACH_WIDTHS = 1.0  # a frame belongs to a segment within this many corridor widths of its centre line
CLEAR_WIDTHS = 1.0  # and further than this many corridor widths from either end, where corridors meet or end
MIN_SEGMENTS = 2  # an axis or a direction is general only when seen on at least this many segments

PCA_COMPONENTS = 3
RIDGE_ALPHA = 1.0  # penalty of the ridge decoders, small against the number of steps
MEASURES = ("direction", "axis", "arena", "distances", "decoders")


def load_thresholds(path):
    """
    The thresholds file as a plain dict.
    """
    return yaml.safe_load(Path(path).read_text())


# ---------------------------------------------------------------------------
# preparation
# ---------------------------------------------------------------------------

def fit_scaling(h):
    """
    The (low, span) that map each column of h (T, H) to [0, 1] over its finite rows, a column that never changes given span 1.
    """
    low = np.nanmin(h, axis=0).astype(float)
    span = np.nanmax(h, axis=0) - low
    return low, np.where(span > 0, span, 1.0)


def scale(h, scaling):
    """
    h scaled per column by a (low, span) pair.
    """
    low, span = scaling
    return (h - low) / span


# ---------------------------------------------------------------------------
# segments and passes on the triple-T
# ---------------------------------------------------------------------------

def track_segments(found):
    """
    The corridor segments of an environment's geometry: names, ends (S, 2), axis (S,) and the corridor width.
    """
    centerline = found["centerline"]
    return {"names": [s["name"] for s in centerline], "p0": np.array([s["p0"] for s in centerline], float),
            "p1": np.array([s["p1"] for s in centerline], float),
            "axis": np.array([int(round(s["axis_deg"]) % 180 == 90) for s in centerline]),
            "width": float(found["params"]["corridor_width"])}


def segment_of(pos, segments):
    """
    The segment of each row of pos (T, 2) as an index, -1 off every corridor, near a corridor's end or with no position.
    """
    d = segments["p1"] - segments["p0"]
    length = np.linalg.norm(d, axis=1)
    u = d / length[:, None]
    rel = pos[:, None, :] - segments["p0"][None]
    along = (rel * u).sum(axis=-1)
    across = np.abs(rel[..., 0] * u[:, 1] - rel[..., 1] * u[:, 0])
    clear, reach = CLEAR_WIDTHS * segments["width"], REACH_WIDTHS * segments["width"]
    inside = (across <= reach) & (along >= clear) & (along <= length - clear)
    found = np.argmin(np.where(inside, across, np.inf), axis=1)
    return np.where(inside.any(axis=1), found, -1)


def pass_labels(arrays, segments, thr):
    """
    The pass of each frame (T,) as an index or -1, and per pass its segment and direction.
    """
    pos = np.column_stack([arrays["x"], arrays["y"]])
    running = np.isin(arrays["phase"], RUNNING_PHASES) & (arrays["speed"] > thr["moving_speed_m_s"])
    key = np.where(running, segment_of(pos, segments), -1)
    change = (np.diff(key) != 0) | (np.diff(arrays["run"]) != 0) | (np.diff(arrays["trip"]) != 0)
    starts = np.concatenate([[0], np.flatnonzero(change) + 1])
    stops = np.append(starts[1:], len(key))
    pass_id, segment, direction = np.full(len(key), -1), [], []
    for start, stop in zip(starts, stops):
        if key[start] < 0:
            continue
        axis = segments["axis"][key[start]]
        step = pos[stop - 1, axis] - pos[start, axis]
        if step == 0:
            continue
        pass_id[start:stop] = len(segment)
        segment.append(key[start])
        direction.append(2 * axis + int(step < 0))
    return pass_id, np.array(segment, dtype=int), np.array(direction, dtype=int)


def pass_means(h, pass_id, n_pass):
    """
    The mean of h (T, H) over the frames of each pass with a finite hidden state, and those frame counts.
    """
    keep = (pass_id >= 0) & np.isfinite(h).all(axis=1)
    member = sparse.csr_matrix((np.ones(keep.sum()), (pass_id[keep], np.arange(keep.sum()))), shape=(n_pass, keep.sum()))
    steps = np.asarray(member.sum(axis=1)).ravel()
    return (member @ h[keep]) / np.maximum(steps, 1)[:, None], steps


def block_segments(block, cache):
    """
    The segments of the block's environment built with its session's start offset, from the cache when built before.
    """
    key = (block["row"]["environment"], block["start_offset_m"])
    if key not in cache:
        cache[key] = track_segments(geometry(*key))
    return cache[key]


def pool_passes(blocks, hidden, thr):
    """
    The passes of track blocks (each its row, arrays and start offset) with their hidden states (T, H) joined: means (P, H), segment, direction and steps (P,), and the segment names.
    """
    assert blocks, "no track blocks to pool passes from"
    cache, parts = {}, []
    for block, h in zip(blocks, hidden):
        segments = block_segments(block, cache)
        pass_id, segment, direction = pass_labels(block["arrays"], segments, thr)
        means, steps = pass_means(h, pass_id, len(segment))
        parts.append((means[steps > 0], segment[steps > 0], direction[steps > 0], steps[steps > 0]))
    means, segment, direction, steps = (np.concatenate(part) for part in zip(*parts))
    return {"means": means, "segment": segment, "direction": direction, "steps": steps,
            "names": segments["names"], "axis": segments["axis"]}


def frame_directions(blocks, thr):
    """
    The direction of travel of every frame of the track blocks joined, -1 for a frame in no pass.
    """
    cache, parts = {}, []
    for block in blocks:
        pass_id, _, direction = pass_labels(block["arrays"], block_segments(block, cache), thr)
        parts.append(np.append(direction, -1)[pass_id])  # pass -1 reads the appended -1
    return np.concatenate(parts)


# ---------------------------------------------------------------------------
# means by label
# ---------------------------------------------------------------------------

def mean_by(values, labels, n, weights):
    """
    The weighted mean of the rows of values (P, H) for each label 0 to n - 1 as (H, n), NaN for a label with no rows.
    """
    member = (labels[:, None] == np.arange(n)) * weights[:, None]
    total = member.sum(axis=0)
    return (member.T @ values / np.where(total > 0, total, np.nan)[:, None]).T


def direction_means(passes, direction=None):
    """
    The mean activity of each unit in each direction E, W, N, S as (H, 4), the pass directions given or the passes' own.
    """
    direction = passes["direction"] if direction is None else direction
    return mean_by(passes["means"], direction, len(DIRECTIONS), passes["steps"])


def cell_means(passes):
    """
    The mean activity of each unit per segment and sign of travel as (H, 2S): column 2 * segment + (1 against the axis).
    """
    cells = 2 * passes["segment"] + passes["direction"] % 2
    return mean_by(passes["means"], cells, 2 * len(passes["axis"]), passes["steps"])


def segment_means(passes):
    """
    The mean activity of each unit per segment, both directions pooled, as (H, S).
    """
    return mean_by(passes["means"], passes["segment"], len(passes["axis"]), passes["steps"])


# ---------------------------------------------------------------------------
# the direction and axis tests on the track
# ---------------------------------------------------------------------------

def direction_index(first, second):
    """
    abs(first - second) / (first + second), 0 where the sum is not positive.
    """
    total = first + second
    return np.divide(np.abs(first - second), total, out=np.zeros_like(total), where=total > 0)


def axis_indices(means):
    """
    (H, 2): the direction index on the east-west axis (E against W) and on the north-south axis (N against S).
    """
    return np.column_stack([direction_index(means[:, 0], means[:, 1]), direction_index(means[:, 2], means[:, 3])])


def axis_selectivity(means):
    """
    (H, 2): (mean of E and W - mean of N and S) / their sum, then its negative for the north-south axis.
    """
    east_west, north_south = means[:, :2].mean(axis=1), means[:, 2:].mean(axis=1)
    total = east_west + north_south
    selectivity = np.divide(east_west - north_south, total, out=np.zeros_like(total), where=total > 0)
    return np.column_stack([selectivity, -selectivity])


def axis_activity(means):
    """
    (H, 2): the mean activity in the two directions of each axis.
    """
    return np.column_stack([means[:, :2].mean(axis=1), means[:, 2:].mean(axis=1)])


def general(values, columns, thr):
    """
    (H,) booleans: the weakest of the columns is at least place_general_min of the strongest, False with fewer than MIN_SEGMENTS columns.
    """
    if len(columns) < MIN_SEGMENTS:
        return np.zeros(len(values), dtype=bool)
    chosen = values[:, columns]
    return chosen.min(axis=1) >= thr["place_general_min"] * chosen.max(axis=1)


def seen(values):
    """
    The columns of values (H, n) with data.
    """
    return np.flatnonzero(~np.isnan(values).all(axis=0))


def shuffle_within_axes(direction, rng):
    """
    The pass directions with the two directions of each axis reassigned among the passes of that axis.
    """
    shuffled = direction.copy()
    for axis in range(len(AXES)):
        group = np.flatnonzero(direction // 2 == axis)
        shuffled[group] = rng.permutation(direction[group])
    return shuffled


def direction_test(passes, thr, rng):
    """
    (H, 2) booleans, east-west then north-south: active, one preferred direction over the minimum and the null, and that direction general over its segments.
    """
    means = direction_means(passes)
    index = axis_indices(means)
    null = np.array([axis_indices(direction_means(passes, shuffle_within_axes(passes["direction"], rng)))
                     for _ in range(thr["n_permutations"])])
    cutoff = np.percentile(null, thr["null_percentile"], axis=0)
    cells = cell_means(passes)
    ok = np.zeros(index.shape, dtype=bool)
    for axis in range(len(AXES)):
        first, second = means[:, 2 * axis], means[:, 2 * axis + 1]
        prefer_second = second > first
        by_sign = [general(cells, [c for c in seen(cells) if passes["axis"][c // 2] == axis and c % 2 == sign], thr)
                   for sign in (0, 1)]
        is_general = np.where(prefer_second, by_sign[1], by_sign[0])
        active = (first + second) / 2 >= thr["activity_floor"]
        ok[:, axis] = active & is_general & (index[:, axis] > thr["direction_index_min"]) & (index[:, axis] > cutoff[:, axis])
    return ok


def axis_test(passes, thr, rng):
    """
    (H, 2) booleans, east-west then north-south: active, selective, balanced between its two directions, general over its segments and above the null.
    """
    means = direction_means(passes)
    selectivity = axis_selectivity(means)
    null = np.array([axis_selectivity(direction_means(passes, rng.permutation(passes["direction"])))
                     for _ in range(thr["n_permutations"])])
    cutoff = np.percentile(null, thr["null_percentile"], axis=0)
    segments = segment_means(passes)
    is_general = np.column_stack([general(segments, [s for s in seen(segments) if passes["axis"][s] == axis], thr)
                                  for axis in range(len(AXES))])
    active = axis_activity(means) >= thr["activity_floor"]
    balanced = axis_indices(means) < thr["balance_index_max"]
    return (selectivity > thr["axis_selectivity_min"]) & (selectivity > cutoff) & active & balanced & is_general


def axis_of(ok):
    """
    The axis of each unit of a test result (H, 2): 0 east-west, 1 north-south, -1 neither.
    """
    return np.where(ok.any(axis=1), ok.argmax(axis=1), -1)


# ---------------------------------------------------------------------------
# the arena test
# ---------------------------------------------------------------------------

def doubled_resultant(curve):
    """
    The resultant length on the doubled angles of heading tuning curves (n_bins, H), 0 for a curve that is all 0.
    """
    angle = 2 * np.pi * (np.arange(len(curve)) + 0.5) / len(curve)
    total = curve.sum(axis=0)
    return np.divide(np.abs(np.exp(2j * angle) @ curve), total, out=np.zeros_like(total), where=total > 0)


def arena_test(blocks, hidden, units, thr, rng):
    """
    (H,) booleans: of the flagged units, those whose doubled angle heading tuning in the arena beats circular shifts of the hidden state, else False.
    """
    chosen, n_bins = np.flatnonzero(units), thr["arena_bins"]
    persists = np.zeros(len(units), dtype=bool)
    rate_hz = blocks[0]["row"]["rate_hz"] if blocks else 1
    least = round(thr["min_shift_s"] * rate_hz)
    used = [(b["arrays"], h) for b, h in zip(blocks, hidden) if len(h) > 2 * least]
    if not len(chosen) or not used:
        return persists
    moving, binned, activity = [], [], []
    for arrays, h in used:
        step = np.flatnonzero((arrays["speed"] > thr["moving_speed_m_s"]) & np.isfinite(arrays["heading"])
                              & np.isfinite(h).all(axis=1))
        bins = np.floor(arrays["heading"][step] % (2 * np.pi) / (2 * np.pi) * n_bins).astype(int)
        moving.append(step)
        binned.append(sparse.csr_matrix((np.ones(len(step)), (bins, np.arange(len(step)))), shape=(n_bins, len(step))))
        activity.append(np.nan_to_num(h[:, chosen]))  # a shift landing on a frame with no hidden state reads 0
    occupancy = sum(np.asarray(b.sum(axis=1)).ravel() for b in binned)

    def resultant(shifts):
        sums = sum(b @ h[(step - shift) % len(h)] for b, h, step, shift in zip(binned, activity, moving, shifts))
        return doubled_resultant(sums / np.maximum(occupancy, 1)[:, None])

    null = np.array([resultant([rng.integers(least, len(h) - least + 1) for h in activity])
                     for _ in range(thr["n_shifts"])])
    persists[chosen] = resultant([0] * len(used)) > np.percentile(null, thr["null_percentile"], axis=0)
    return persists


# ---------------------------------------------------------------------------
# population distances, PCA, decoders, fractions
# ---------------------------------------------------------------------------

def population_distances(passes):
    """
    The mean distances between the segment and direction mean vectors: opposite directions on an axis, the same direction on two segments, two axes, and the ratios to the cross distance.
    """
    cells = cell_means(passes)
    columns = seen(cells)
    axis = passes["axis"][columns // 2]
    sign, segment = columns % 2, columns // 2
    groups = {"opposite": [], "parallel": [], "cross": []}
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            gap = float(np.linalg.norm(cells[:, columns[i]] - cells[:, columns[j]]))
            if axis[i] != axis[j]:
                groups["cross"].append(gap)
            elif sign[i] != sign[j]:
                groups["opposite"].append(gap)
            elif segment[i] != segment[j]:
                groups["parallel"].append(gap)
    found = {name: float(np.mean(gaps)) if gaps else float("nan") for name, gaps in groups.items()}
    return {**found, "opposite_over_cross": found["opposite"] / found["cross"],
            "parallel_over_cross": found["parallel"] / found["cross"]}


def pca_scores(h, keep):
    """
    The first PCA scores of the kept rows of h (T, H) with a finite hidden state, their variance shares and which rows they are.
    """
    rows = np.flatnonzero(keep & np.isfinite(h).all(axis=1))
    centred = h[rows] - h[rows].mean(axis=0)
    values, vectors = np.linalg.eigh(centred.T @ centred / (len(centred) - 1))
    top = np.argsort(values)[::-1][:PCA_COMPONENTS]
    return {"scores": centred @ vectors[:, top], "explained": values[top] / values.sum(), "rows": rows}


def ridge_r2(x_fit, y_fit, x_test, y_test, alpha=RIDGE_ALPHA):
    """
    The R-squared on the test arrays, averaged over the columns of y, of a ridge regression fitted on the fit arrays.
    """
    x_mean, y_mean = x_fit.mean(axis=0, dtype=float), y_fit.mean(axis=0)
    centred = x_fit - x_mean
    weights = np.linalg.solve(centred.T @ centred + alpha * np.eye(x_fit.shape[1]), centred.T @ (y_fit - y_mean))
    predicted = (x_test - x_mean) @ weights + y_mean
    residual = ((y_test - predicted) ** 2).sum(axis=0)
    total = ((y_test - y_test.mean(axis=0)) ** 2).sum(axis=0)
    return float(np.mean(1 - residual / total))


def decode(fit, test, target):
    """
    The test R-squared of a ridge decoder from hidden state to position (x, y) or heading (cos, sin), over the frames where both are finite.
    """
    def pairs(blocks):
        h = np.concatenate([b["hidden"] for b in blocks])
        arrays = {name: np.concatenate([b["arrays"][name] for b in blocks]) for name in ("x", "y", "heading")}
        y = (np.column_stack([arrays["x"], arrays["y"]]) if target == "position"
             else np.column_stack([np.cos(arrays["heading"]), np.sin(arrays["heading"])]))
        keep = np.isfinite(h).all(axis=1) & np.isfinite(y).all(axis=1)
        return h[keep], y[keep]
    return ridge_r2(*pairs(fit), *pairs(test))


def fractions(direction_ok, axis_ok, persists):
    """
    Fractions of units that are direction units, axis units and released axis units (of axis units and of all units).
    """
    is_axis = axis_ok.any(axis=1)
    released = is_axis & ~persists
    return {"direction": float(direction_ok.any(axis=1).mean()), "axis": float(is_axis.mean()),
            "released_of_axis": float(released.sum() / is_axis.sum()) if is_axis.any() else float("nan"),
            "released": float(released.mean())}


def measures(test, fit, thr, seed, which=MEASURES):
    """
    The chosen measures of the test blocks (each its row, arrays, start offset and hidden state), hidden states scaled to [0, 1] per unit over them, the decoders fitted on the fit blocks.
    """
    rng = np.random.default_rng(seed)
    scaling = fit_scaling(np.concatenate([b["hidden"] for b in test]))
    track = [b for b in test if b["row"]["kind"] == "track"]
    arena = [b for b in test if b["row"]["kind"] == "arena"]
    found = {"scaling": scaling}
    if set(which) & {"direction", "axis", "arena", "distances"}:
        passes = pool_passes(track, [scale(b["hidden"], scaling) for b in track], thr)
        found["passes"] = passes
        found["direction_means"] = direction_means(passes)
        found["direction"] = direction_test(passes, thr, rng)
        found["axis"] = axis_test(passes, thr, rng)
        if "arena" in which:
            found["persists"] = arena_test(arena, [scale(b["hidden"], scaling) for b in arena], found["axis"].any(axis=1),
                                           thr, rng)
            found["fractions"] = fractions(found["direction"], found["axis"], found["persists"])
        if "distances" in which:
            found["distances"] = population_distances(passes)
    if "decoders" in which:
        found["decoders"] = {target: decode(fit, test, target) for target in ("position", "heading")}
    return found
