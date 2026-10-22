"""
The direction and axis analysis (brief section 8) of hidden states and input channels as pseudo-units, on numpy arrays.
"""

from pathlib import Path

import numpy as np
import yaml
from scipy import sparse

from .config import ALONG_DEG
from .worlds import classify_segment, travel_direction

THRESHOLDS = Path(__file__).with_name("thresholds.yaml")  # the pre-registered numbers, never edited

# The 8 segment and direction cells, in this order everywhere: cell 2 * segment + (0 for E or N, 1 for W or S), with the
# segments in the order of worlds.SEGMENTS (bottom, top, left, right): 0 and 1 run east-west, 2 and 3 north-south.
CELLS = ("bottom_E", "bottom_W", "top_E", "top_W", "left_N", "left_S", "right_N", "right_S")

# Cell pairs of the population measure 8.4.
OPPOSITE = ((0, 1), (2, 3), (4, 5), (6, 7))  # the two directions on the same segment
PARALLEL = ((0, 2), (1, 3), (4, 6), (5, 7))  # the same direction on the two parallel segments
CROSS = tuple((i, j) for i in range(4) for j in range(4, 8))  # an east-west cell against a north-south cell

PCA_COMPONENTS = 3
RIDGE_ALPHA = 1.0  # penalty of the ridge decoders, small against the number of steps


def load_thresholds(path=THRESHOLDS):
    """
    The thresholds file as a plain dict.
    """
    return yaml.safe_load(Path(path).read_text())


# ---------------------------------------------------------------------------
# preparation
# ---------------------------------------------------------------------------

def fit_scaling(h):
    """
    The (low, span) that map each column of h (T, H) to [0, 1]; a column that never changes gets span 1.
    """
    low = h.min(axis=0).astype(float)
    span = h.max(axis=0) - low
    return low, np.where(span > 0, span, 1.0)


def scale(h, scaling):
    """
    h scaled per column by a (low, span) pair, so hidden states and input channels can share one treatment.
    """
    low, span = scaling
    return (h - low) / span


# ---------------------------------------------------------------------------
# segment and direction cells, passes
# ---------------------------------------------------------------------------

def cell_masks(pos, heading, speed, thr):
    """
    (T, 8) booleans: a moving step in a segment with heading within the tolerance of one corridor direction.
    """
    assert thr["heading_tolerance_deg"] == ALONG_DEG  # worlds.travel_direction reads its own copy of this number
    segment = classify_segment(pos)
    direction = travel_direction(heading, segment)
    valid = (direction != 0) & (speed > thr["moving_speed_m_s"])
    cell = 2 * segment + (direction < 0)
    return valid[:, None] & (cell[:, None] == np.arange(len(CELLS)))


def cell_labels(masks):
    """
    The cell index of each step of masks (T, 8), or -1 for a step in no cell.
    """
    return np.where(masks.any(axis=1), masks.argmax(axis=1), -1)


def mean_by_cell(values, cells, weights):
    """
    The weighted mean of the rows of values (N, H) in each of the 8 cells as (H, 8), NaN for an empty cell.
    """
    member = (cells[:, None] == np.arange(len(CELLS))) * weights[:, None]
    total = member.sum(axis=0)
    return (member.T @ values / np.where(total > 0, total, np.nan)[:, None]).T


def cell_means(h, masks):
    """
    The mean activity of each unit of h (T, H) in each cell of masks (T, 8), as (H, 8), NaN for an empty cell.
    """
    return mean_by_cell(h, cell_labels(masks), np.ones(len(h)))


def session_passes(h, masks):
    """
    The passes of one session (maximal runs of steps in one cell) as mean activity (n_pass, H), cell and step count.
    """
    cells = cell_labels(masks)
    starts = np.flatnonzero(np.diff(cells, prepend=-2) != 0)
    steps = np.diff(starts, append=len(cells))
    keep = cells[starts] >= 0
    means = np.add.reduceat(h, starts, axis=0) / steps[:, None]
    return means[keep], cells[starts][keep], steps[keep]


def pool_passes(sessions, hidden, thr):
    """
    The passes of the sessions of one world joined: (means (n_pass, H), cell (n_pass,), steps (n_pass,)).
    """
    parts = [session_passes(h, cell_masks(s.pos, s.heading, s.speed, thr)) for s, h in zip(sessions, hidden)]
    return tuple(np.concatenate(part) for part in zip(*parts))


# ---------------------------------------------------------------------------
# direction test 8.1 and axis test 8.2, on the loop
# ---------------------------------------------------------------------------

def by_segment(means):
    """
    (H, 4) each: the mean activity of the first direction (E or N) and of the second (W or S) in the 4 segments.
    """
    return means[:, 0::2], means[:, 1::2]


def axis_pairs(x):
    """
    A per segment array (H, 4) as (H, 2, 2): the axis, then its two parallel segments (bottom and top, left and right).
    """
    return x.reshape(len(x), 2, 2)


def direction_index(first, second):
    """
    abs(first - second) / (first + second), 0 where both are 0.
    """
    total = first + second
    return np.divide(np.abs(first - second), total, out=np.zeros_like(total), where=total > 0)


def smaller_index(means):
    """
    (H, 2): for each axis the smaller of the direction indices of its two parallel segments.
    """
    return axis_pairs(direction_index(*by_segment(means))).min(axis=2)


def axis_selectivity(means):
    """
    (H, 2): (mean of the axis' four cells - mean of the other axis' four) / their sum, east-west then north-south.
    """
    east_west, north_south = means[:, :4].mean(axis=1), means[:, 4:].mean(axis=1)
    total = east_west + north_south
    selectivity = np.divide(east_west - north_south, total, out=np.zeros_like(total), where=total > 0)
    return np.column_stack([selectivity, -selectivity])


def shuffle_within_segments(cells, rng):
    """
    The cell labels of the passes with the two directions reassigned among the passes of each segment.
    """
    shuffled = cells.copy()
    for segment in range(4):
        group = np.flatnonzero(cells // 2 == segment)
        shuffled[group] = rng.permutation(cells[group])
    return shuffled


def direction_null(passes, thr, rng):
    """
    The smaller direction index (H, 2) of the passes and its null_percentile cutoff over direction label permutations.
    """
    means, cells, steps = passes
    observed = smaller_index(mean_by_cell(means, cells, steps))
    null = np.array([smaller_index(mean_by_cell(means, shuffle_within_segments(cells, rng), steps))
                     for _ in range(thr["n_permutations"])])
    return observed, np.percentile(null, thr["null_percentile"], axis=0)


def selectivity_null(passes, thr, rng):
    """
    The axis selectivity (H, 2) of the passes and its null_percentile cutoff over permutations of all pass labels.
    """
    means, cells, steps = passes
    observed = axis_selectivity(mean_by_cell(means, cells, steps))
    null = np.array([axis_selectivity(mean_by_cell(means, rng.permutation(cells), steps))
                     for _ in range(thr["n_permutations"])])
    return observed, np.percentile(null, thr["null_percentile"], axis=0)


def direction_test(passes, thr, rng):
    """
    (H, 2) booleans, east-west then north-south: one preferred direction on both segments, over the minimum and null.
    """
    means, cells, steps = passes
    smaller, cutoff = direction_null(passes, thr, rng)
    first, second = by_segment(mean_by_cell(means, cells, steps))
    sign = axis_pairs(np.sign(first - second))
    eligible = (axis_pairs((first + second) / 2) >= thr["activity_floor"]).all(axis=2)
    return eligible & (sign[..., 0] == sign[..., 1]) & (smaller > thr["direction_index_min"]) & (smaller > cutoff)


def axis_test(passes, thr, rng):
    """
    (H, 2) booleans, east-west then north-south: selective, balanced, general over both segments and above the null.
    """
    means, cells, steps = passes
    selectivity, cutoff = selectivity_null(passes, thr, rng)
    first, second = by_segment(mean_by_cell(means, cells, steps))
    activity = axis_pairs((first + second) / 2)
    eligible = (activity >= thr["activity_floor"]).all(axis=2)
    balanced = eligible & (axis_pairs(direction_index(first, second)) < thr["balance_index_max"]).all(axis=2)
    general = activity.min(axis=2) >= thr["place_general_min"] * activity.max(axis=2)
    return (selectivity > thr["axis_selectivity_min"]) & balanced & general & (selectivity > cutoff)


def axis_of(ok):
    """
    The axis of each unit of a test result (H, 2): 0 east-west, 1 north-south, -1 neither.
    """
    return np.where(ok.any(axis=1), ok.argmax(axis=1), -1)


# ---------------------------------------------------------------------------
# arena test 8.3, on the open field
# ---------------------------------------------------------------------------

def doubled_resultant(curve):
    """
    The resultant length on the doubled angles of heading tuning curves (n_bins, H), 0 for a curve that is all 0.
    """
    angle = 2 * np.pi * (np.arange(len(curve)) + 0.5) / len(curve)
    total = curve.sum(axis=0)
    return np.divide(np.abs(np.exp(2j * angle) @ curve), total, out=np.zeros_like(total), where=total > 0)


def arena_test(sessions, hidden, units, thr, rng):
    """
    (H,) booleans: of the flagged units, those whose doubled angle heading tuning beats circular shifts; else False.
    """
    chosen = np.flatnonzero(units)
    n_bins = thr["arena_bins"]
    moving, binned = [], []
    for s in sessions:
        step = np.flatnonzero(s.speed > thr["moving_speed_m_s"])
        bins = np.floor(s.heading[step] % (2 * np.pi) / (2 * np.pi) * n_bins).astype(int)
        moving.append(step)
        binned.append(sparse.csr_matrix((np.ones(len(step)), (bins, np.arange(len(step)))), shape=(n_bins, len(step))))
    activity = [h[:, chosen] for h in hidden]
    occupancy = sum(np.asarray(b.sum(axis=1)).ravel() for b in binned)

    def resultant(shifts):
        sums = sum(b @ h[(step - shift) % len(h)] for b, h, step, shift in zip(binned, activity, moving, shifts))
        return doubled_resultant(sums / np.maximum(occupancy, 1)[:, None])

    dt = sessions[0].t[1] - sessions[0].t[0]
    least = round(thr["min_shift_s"] / dt)
    null = np.array([resultant([rng.integers(least, len(h) - least + 1) for h in activity])
                     for _ in range(thr["n_shifts"])])
    persists = np.zeros(len(units), dtype=bool)
    persists[chosen] = resultant([0] * len(sessions)) > np.percentile(null, thr["null_percentile"], axis=0)
    return persists


# ---------------------------------------------------------------------------
# population measure 8.4
# ---------------------------------------------------------------------------

def mean_distance(vectors, pairs):
    """
    The mean Euclidean distance between the listed pairs of rows of vectors.
    """
    return float(np.mean([np.linalg.norm(vectors[i] - vectors[j]) for i, j in pairs]))


def population_distances(means):
    """
    Opposite, parallel and cross distances between the 8 mean vectors (columns of means (H, 8)) and the ratios to cross.
    """
    opposite, parallel, cross = (mean_distance(means.T, pairs) for pairs in (OPPOSITE, PARALLEL, CROSS))
    return {"opposite": opposite, "parallel": parallel, "cross": cross,
            "opposite_over_cross": opposite / cross, "parallel_over_cross": parallel / cross}


def pca_scores(h, pos, heading, speed, thr):
    """
    The first PCA scores of the moving steps of h (T, H), their variance shares, and those steps' heading and segment.
    """
    moving = speed > thr["moving_speed_m_s"]
    centred = h[moving] - h[moving].mean(axis=0)
    values, vectors = np.linalg.eigh(centred.T @ centred / (len(centred) - 1))
    top = np.argsort(values)[::-1][:PCA_COMPONENTS]
    return {"scores": centred @ vectors[:, top], "explained": values[top] / values.sum(),
            "heading": heading[moving], "segment": classify_segment(pos[moving])}


# ---------------------------------------------------------------------------
# decoders
# ---------------------------------------------------------------------------

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


def decode_position(h_fit, pos_fit, h_test, pos_test):
    """
    The test R-squared of a ridge decoder from the states h to position (x, y).
    """
    return ridge_r2(h_fit, pos_fit, h_test, pos_test)


def decode_heading(h_fit, heading_fit, h_test, heading_test):
    """
    The test R-squared of a ridge decoder from the states h to heading as (cos, sin).
    """
    return ridge_r2(h_fit, np.column_stack([np.cos(heading_fit), np.sin(heading_fit)]),
                    h_test, np.column_stack([np.cos(heading_test), np.sin(heading_test)]))


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def fractions(direction_ok, axis_ok, persists):
    """
    Fractions of units that are direction units, axis units and released axis units (of axis units and of all units).
    """
    is_axis = axis_ok.any(axis=1)
    released = is_axis & ~persists
    return {"direction": float(direction_ok.any(axis=1).mean()), "axis": float(is_axis.mean()),
            "released_of_axis": float(released.sum() / is_axis.sum()) if is_axis.any() else float("nan"),
            "released": float(released.mean())}


def analyse_units(loop_sessions, loop_hidden, field_sessions, field_hidden, thr, rng):
    """
    Sections 8.1 to 8.4 and the fractions for hidden states (lists of (T, H), one per test session) of both worlds.
    """
    scaling = fit_scaling(np.concatenate(loop_hidden + field_hidden))
    loop_hidden = [scale(h, scaling) for h in loop_hidden]
    field_hidden = [scale(h, scaling) for h in field_hidden]
    passes = pool_passes(loop_sessions, loop_hidden, thr)
    direction = direction_test(passes, thr, rng)
    axis = axis_test(passes, thr, rng)
    persists = arena_test(field_sessions, field_hidden, axis.any(axis=1), thr, rng)
    return {"scaling": scaling, "direction": direction, "axis": axis, "persists": persists,
            "fractions": fractions(direction, axis, persists),
            "distances": population_distances(mean_by_cell(*passes))}
