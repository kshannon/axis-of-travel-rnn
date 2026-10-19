"""
Registration: the pixel scale of each epoch kind, the track rotation and the offset that take a session from the camera to the room.
"""

import numpy as np
from scipy.signal import find_peaks

from .cuts import inside
from .kinematics import pixel_motion
from .room import FLIP, rotated, to_room, wrapped

# The epoch kinds, and the track's start site in the environment.
TRACK, ARENA, START_SITE = "track", "arena", "start"


def moving(frames, epoch, rules):
    """
    True on the frames of the epoch whose smoothed mashup speed is over running_px_per_s.
    """
    speed, _ = pixel_motion(frames, rules)
    return inside(frames, epoch) & (speed > rules["running_px_per_s"])


def led_distance_px(frames, epoch):
    """
    The median distance in pixels between the two LEDs over the epoch's frames with both lights.
    """
    here = inside(frames, epoch)
    return float(np.nanmedian(np.hypot(frames["front_x"][here] - frames["back_x"][here], frames["front_y"][here] - frames["back_y"][here])))


def centroid(counts, centres, at, rules):
    """
    The mean position of the counts in the peak_smooth_bins bins centred on this one.
    """
    window = slice(at - rules["peak_smooth_bins"] // 2, at + rules["peak_smooth_bins"] // 2 + 1)
    return float(np.average(centres[window], weights=counts[window]))


def outer_peaks(values, rules):
    """
    The first and the last peak of the histogram of these values, each placed at the centroid of its smoothing bins.
    """
    size, smooth_bins = rules["histogram_bin_px"], rules["peak_smooth_bins"]
    edges = np.arange(values.min() - smooth_bins * size, values.max() + smooth_bins * size + size, size)
    counts, _ = np.histogram(values, edges)
    smooth = np.convolve(counts, np.ones(smooth_bins) / smooth_bins, mode="same")
    peaks, _ = find_peaks(smooth, prominence=rules["peak_prominence"] * smooth.max())
    centres = edges[:-1] + size / 2
    return centroid(counts, centres, peaks[0], rules), centroid(counts, centres, peaks[-1], rules)


def peak_span(values, rules):
    """
    The distance between the first and the last peak of the histogram of these values.
    """
    low, high = outer_peaks(values, rules)
    return high - low


def running_axes(frames, epoch, rotation, rules):
    """
    The running frames of the epoch in pixels along the room axes, x to the east and y to the north, the camera's y flipped and the track rotation taken out.
    """
    here = moving(frames, epoch, rules)
    return rotated(frames["mashup_x"][here], -frames["mashup_y"][here], rotation)


def track_scale(axes, geometry, rules):
    """
    Pixels per metre of the track: the mean of the two axis estimates, the span of the outermost occupancy peaks of the running frames along each room axis over the centreline's extent, and then each.
    """
    points = np.array([segment[end] for segment in geometry["centerline"] for end in ("p0", "p1")])
    scale_x, scale_y = [float(peak_span(axis, rules) / extent) for axis, extent in zip(axes, points.max(axis=0) - points.min(axis=0))]
    return (scale_x + scale_y) / 2, scale_x, scale_y


def start_offset_measured(axes, start_px, rotation, scale, rules):
    """
    The distance in metres along the room's y axis from the start site up to the bottom outer corridor peak of the running frames, at the track scale, positive when the start lies above that corridor.
    """
    _, start_y = rotated(start_px[0], -start_px[1], rotation)
    return float((start_y - outer_peaks(axes[1], rules)[0]) / scale)


def arena_scale(track_scale_px_per_m, rules):
    """
    Pixels per metre of the arena: the track scale times the parallax ratio, the arena floor being nearer the camera.
    """
    return track_scale_px_per_m * (rules["camera_height_m"] - rules["track_height_m"]) / (rules["camera_height_m"] - rules["arena_height_m"])


def extent_ratio(frames, epoch, scale, geometry, rules):
    """
    The occupancy extent of the epoch's running frames between extent_percentiles, in metres at the scale, over the size of the environment's boundary: 1 when the rat covers it.
    """
    here = moving(frames, epoch, rules)
    low, high = np.nanpercentile([frames["mashup_x"][here], frames["mashup_y"][here]], rules["extent_percentiles"], axis=1)
    boundary = np.array(geometry["boundary"])
    return float(np.mean(high - low) / scale / np.mean(boundary.max(axis=0) - boundary.min(axis=0)))


def median_px(frames, numbers):
    """
    The median mashup position in pixels over these 1-based frame numbers, as a list.
    """
    at = np.searchsorted(frames["frame"], numbers)
    return np.nanmedian(np.column_stack([frames["mashup_x"][at], frames["mashup_y"][at]]), axis=0).tolist()


def sites_px(frames, runs, rules):
    """
    The start site and the goals in pixels: the median position at the outbound runs' first frame and at their last.
    """
    outbound = [r for r in runs if r["epoch"] == TRACK and r["path_id"] in rules["outbound_paths"]]
    return median_px(frames, [r["frame_start"] for r in outbound]), median_px(frames, [r["frame_end"] for r in outbound])


def track_rotation(frames, epoch, runs, rules):
    """
    The counterclockwise rotation that lays the track's corridors along the room axes with the start below the goals, and the four-fold concentration of the running directions.
    """
    speed, direction = pixel_motion(frames, rules)
    running = inside(frames, epoch) & (speed > rules["running_px_per_s"]) & np.isfinite(direction)
    z = np.exp(4j * -direction[running]).mean()
    start, goals = sites_px(frames, runs, rules)
    candidates = -np.angle(z) / 4 + np.arange(4) * np.pi / 2
    best = max(candidates, key=lambda angle: rotated(goals[0] - start[0], -(goals[1] - start[1]), angle)[1])
    return float(wrapped(best)), float(np.abs(z))


def epoch_parameters(frames, epoch, scale, rotation, concentration, start_px, geometry, rules):
    """
    One epoch's parameters: the scale, the LED separation it implies, the rotation, the flip and the offset that lands its anchor, and for the arena its extent ratio.
    """
    if epoch["epoch"] == TRACK:
        anchor_px, anchor_m = np.array(start_px), np.array(geometry["reward_sites"][START_SITE])
    else:
        here = inside(frames, epoch)
        anchor_px, anchor_m = np.nanmedian([frames["mashup_x"][here], frames["mashup_y"][here]], axis=1), np.array(geometry["room"]) / 2
    offset = anchor_m - np.array(to_room(anchor_px[0], anchor_px[1], scale, FLIP, rotation, (0.0, 0.0)))
    found = {"scale_px_per_m": scale, "led_separation_m": led_distance_px(frames, epoch) / scale, "rotation_rad": rotation,
             "rotation_concentration": concentration, "flip": FLIP, "offset_m": offset.tolist()}
    if epoch["epoch"] == ARENA:
        found["arena_extent_ratio"] = extent_ratio(frames, epoch, scale, geometry, rules)
    return found


def parameters(frames, epochs, runs, environment, rules):
    """
    The registration, JSON ready: the start and goal sites in pixels and per epoch kind the scale (the track's with its two axis estimates and the measured start offset), LED separation, rotation, flip and offset.
    """
    track = next(e for e in epochs if e["epoch"] == TRACK)
    rotation, concentration = track_rotation(frames, track, runs, rules)
    axes = running_axes(frames, track, rotation, rules)
    scale, scale_x, scale_y = track_scale(axes, environment[track["environment"]], rules)
    scales = {TRACK: scale, ARENA: arena_scale(scale, rules)}
    start_px, goals_px = sites_px(frames, runs, rules)
    found = {"start_px": start_px, "goals_px": goals_px}
    for epoch in epochs:
        found[epoch["epoch"]] = epoch_parameters(frames, epoch, scales[epoch["epoch"]], rotation, concentration, start_px,
                                                 environment[epoch["environment"]], rules)
    found[TRACK].update(scale_x_px_per_m=scale_x, scale_y_px_per_m=scale_y,
                        start_offset_measured_m=start_offset_measured(axes, start_px, rotation, scale, rules))
    return found
