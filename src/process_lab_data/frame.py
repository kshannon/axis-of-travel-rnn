"""
Frame conversion: pixel scale, the LED offset, the track rotation and the translation that take one session from the camera to the room.
"""

import numpy as np
from scipy.signal import find_peaks

from environments import load_environment

from .select import RUNNING_FLOOR_M_PER_S, inside

# The track's scale in pixels per metre comes from its geometry. After the flip and the rotation, the running frames'
# positions along each room axis are histogrammed in bins of HISTOGRAM_BIN_PX and smoothed over PEAK_SMOOTH_BINS bins,
# and the outermost peaks with a prominence of at least PEAK_PROMINENCE of the highest bin are the outer corridor
# centrelines, the two side returns along x and the bottom and top corridors along y, each placed at the centroid of
# its PEAK_SMOOTH_BINS bins since the occupancy floor lies on its inner side only. Their distance over the config's
# centreline extent is that axis's estimate and the scale is the mean of the two, robust to how far the rat goes into
# the corners. The two estimates agree to about 1 percent when both pairs of peaks are the outer corridors, and a return
# side the rat rarely took loses its peak to the prominence floor and hands its axis an inner corridor instead: the goal
# connector 0.18 m in along x, 12 percent of the span, is the nearest. A session whose estimates differ by over
# AXIS_AGREE of their mean is reported as a missed peak. The arena floor sits ARENA_HEIGHT_M above the room floor
# against the track's TRACK_HEIGHT_M under a camera at CAMERA_HEIGHT_M (Olson 2017), so it is PARALLAX_RATIO times
# larger in pixels. The LED separation each scale implies is written to the manifest as a check: about 0.068 m for NS14
# and 0.06 m for the other rats, not the paper's NOMINAL_LED_SEPARATION_M, which only the still floor uses, since
# RatReplay calls still with the frames and the epochs alone, before any scale is fitted. The arena's occupancy extent
# between EXTENT_PERCENTILES of its moving positions over its boundary is a cross-check, not used. Speed and the
# direction of motion are the position difference over dt averaged over SPEED_SMOOTH_FRAMES frames, and a frame faster
# than RUNNING_PX_PER_S is running, as RatReplay computes them (data.SPEED_SMOOTH_FRAMES and data.RUNNING_SPEED), so the
# LED offset here equals the one it shows. The still floor averages over the same window but leaves out the steps across
# a light switch, where the mashup moves between the midpoint and the one good LED, about 3 cm on the real implants,
# without the rat moving: otherwise no one-LED loss inside a reward dwell would ever count as still.
HISTOGRAM_BIN_PX = 2.0
PEAK_SMOOTH_BINS = 5
PEAK_PROMINENCE = 0.1
AXIS_AGREE = 0.05
CAMERA_HEIGHT_M, TRACK_HEIGHT_M, ARENA_HEIGHT_M = 2.6, 0.2, 0.4
PARALLAX_RATIO = (CAMERA_HEIGHT_M - TRACK_HEIGHT_M) / (CAMERA_HEIGHT_M - ARENA_HEIGHT_M)
NOMINAL_LED_SEPARATION_M = 0.05
EXTENT_PERCENTILES = (1, 99)
SPEED_SMOOTH_FRAMES = 6
RUNNING_PX_PER_S = 20.0

# The epoch kinds and what anchors each in the room: the track's start site, the median position at the first frame
# of the outbound runs (the lab's paths 1 to 4), maps to the config's start reward site, the arena's median position
# to the centre of its room. The arena takes the track's rotation, having no orientation cue of its own. A session
# whose LED offset lies over OFFSET_WARN_DEG from its rat's median has its LEDs swapped (NS15_rec4).
TRACK = "track"
ARENA = "arena"
START_SITE = "start"
OUTBOUND_PATHS = (1, 2, 3, 4)
OFFSET_WARN_DEG = 30.0


def wrapped(angle):
    """
    An angle in radians wrapped to the interval from minus pi to pi.
    """
    return (angle + np.pi) % (2 * np.pi) - np.pi


def rotated(x, y, angle):
    """
    The points rotated counterclockwise by the angle about the origin.
    """
    return x * np.cos(angle) - y * np.sin(angle), x * np.sin(angle) + y * np.cos(angle)


def smoothed(steps):
    """
    A per-step series as a per-frame series, the first frame repeating the second, averaged over SPEED_SMOOTH_FRAMES frames.
    """
    kernel = np.ones(SPEED_SMOOTH_FRAMES) / SPEED_SMOOTH_FRAMES
    return np.convolve(np.concatenate([steps[:1], steps]), kernel, mode="same")


def motion(frames):
    """
    The smoothed speed in px/s and the direction of the smoothed velocity in camera coordinates (y down), from the mashup positions.
    """
    dt, dx, dy = np.diff(frames["t"]), np.diff(frames["mashup_x"]), np.diff(frames["mashup_y"])
    return smoothed(np.hypot(dx, dy) / dt), np.arctan2(smoothed(dy / dt), smoothed(dx / dt))


def moving(frames, epoch):
    """
    True on the frames of the epoch whose smoothed mashup speed is over RUNNING_PX_PER_S.
    """
    speed, _ = motion(frames)
    return inside(frames, epoch) & (speed > RUNNING_PX_PER_S)


def led_distance_px(frames, epoch):
    """
    The median distance in pixels between the two LEDs over the epoch's frames with both lights.
    """
    here = inside(frames, epoch)
    apart = np.hypot(frames["front_x"][here] - frames["back_x"][here], frames["front_y"][here] - frames["back_y"][here])
    return float(np.nanmedian(apart))


def led_separation_m(frames, epoch, scale):
    """
    The LED separation in metres the epoch's scale implies, the check on the implant against the paper's 0.05 m.
    """
    return led_distance_px(frames, epoch) / scale


def switched(frames):
    """
    True on each step between two frames whose lights differ, where the mashup moves between the midpoint and one LED.
    """
    front, back = frames["unfilled_front"], frames["unfilled_back"]
    return (front[1:] != front[:-1]) | (back[1:] != back[:-1])


def steady_speed(frames):
    """
    The mashup speed in px/s averaged over the steps of the SPEED_SMOOTH_FRAMES window that do not cross a light switch.
    """
    step = np.hypot(np.diff(frames["mashup_x"]), np.diff(frames["mashup_y"])) / np.diff(frames["t"])
    kept = ~switched(frames)
    return smoothed(np.where(kept, step, 0.0)) / smoothed(kept.astype(float))


def still(frames, epochs):
    """
    True on a frame of one of the epochs whose steady mashup speed is under RUNNING_FLOOR_M_PER_S at the epoch's nominal scale, its LED distance over NOMINAL_LED_SEPARATION_M.
    """
    speed = steady_speed(frames)
    floor_px = np.full(len(speed), np.nan)
    for epoch in epochs:
        floor_px[inside(frames, epoch)] = RUNNING_FLOOR_M_PER_S * led_distance_px(frames, epoch) / NOMINAL_LED_SEPARATION_M
    return speed < floor_px


def centroid(counts, centres, at):
    """
    The mean position of the counts in the PEAK_SMOOTH_BINS bins centred on this one.
    """
    window = slice(at - PEAK_SMOOTH_BINS // 2, at + PEAK_SMOOTH_BINS // 2 + 1)
    return float(np.average(centres[window], weights=counts[window]))


def peak_span(values):
    """
    The distance between the first and the last peak of the histogram of these values in HISTOGRAM_BIN_PX bins, found on the histogram smoothed over PEAK_SMOOTH_BINS bins with a prominence of at least PEAK_PROMINENCE of its highest bin and each placed at the centroid of its bins.
    """
    pad = PEAK_SMOOTH_BINS * HISTOGRAM_BIN_PX
    edges = np.arange(values.min() - pad, values.max() + pad + HISTOGRAM_BIN_PX, HISTOGRAM_BIN_PX)
    counts, _ = np.histogram(values, edges)
    smooth = np.convolve(counts, np.ones(PEAK_SMOOTH_BINS) / PEAK_SMOOTH_BINS, mode="same")
    peaks, _ = find_peaks(smooth, prominence=PEAK_PROMINENCE * smooth.max())
    centres = edges[:-1] + HISTOGRAM_BIN_PX / 2
    return centroid(counts, centres, peaks[-1]) - centroid(counts, centres, peaks[0])


def centreline_extent_m(spec):
    """
    The width and height in metres spanned by the environment's centreline, the outer corridor centrelines of the track: 1.52 by 1.17 for triple_t.
    """
    points = np.array([segment[end] for segment in spec.centerline for end in ("p0", "p1")])
    return points.max(axis=0) - points.min(axis=0)


def track_scale(frames, epoch, rotation_rad):
    """
    Pixels per metre of the track from its geometry, the mean of the two axis estimates and then each: the span of the outermost occupancy peaks of the running frames along each room axis after the flip and the rotation over the config's centreline extent.
    """
    here = moving(frames, epoch)
    axes = rotated(frames["mashup_x"][here], -frames["mashup_y"][here], rotation_rad)
    scale_x, scale_y = [float(peak_span(axis) / extent) for axis, extent in zip(axes, centreline_extent_m(load_environment(epoch["environment"])))]
    return (scale_x + scale_y) / 2, scale_x, scale_y


def axis_disagreement(track_parameters):
    """
    How far the track's x and y scale estimates lie apart as a fraction of their mean, over AXIS_AGREE when an outer corridor peak was missed.
    """
    return abs(track_parameters["scale_x_px_per_m"] - track_parameters["scale_y_px_per_m"]) / track_parameters["scale_px_per_m"]


def arena_scale(track_scale_px_per_m):
    """
    Pixels per metre of the arena: the same session's track scale times PARALLAX_RATIO, the arena floor being nearer the camera.
    """
    return track_scale_px_per_m * PARALLAX_RATIO


def boundary_size_m(spec):
    """
    The mean width and height in metres of the environment's boundary polygon, the arena's diameter.
    """
    points = np.array(spec.boundary)
    return float(np.mean(points.max(axis=0) - points.min(axis=0)))


def extent_ratio(frames, epoch, scale, spec):
    """
    The occupancy extent of the epoch's running frames between EXTENT_PERCENTILES along the camera axes, averaged and in metres at the scale, over the size of the environment's boundary: 1 when the rat covers it.
    """
    here = moving(frames, epoch)
    low, high = np.nanpercentile([frames["mashup_x"][here], frames["mashup_y"][here]], EXTENT_PERCENTILES, axis=1)
    return float(np.mean(high - low) / scale / boundary_size_m(spec))


def led_offset(frames):
    """
    The circular mean (rad) and concentration r of head_dir minus the motion direction over running frames in camera coordinates, and their count: the light bar's mounting angle.
    """
    speed, direction = motion(frames)
    heading = frames["head_dir"]
    running = (speed > RUNNING_PX_PER_S) & np.isfinite(heading) & np.isfinite(direction)
    z = np.exp(1j * (heading[running] - direction[running])).sum() / max(running.sum(), 1)
    return float(np.angle(z)), float(np.abs(z)), int(running.sum())


def positions_at(frames, frame_numbers):
    """
    The median mashup position in pixels over these 1-based frame numbers.
    """
    at = np.searchsorted(frames["frame"], frame_numbers)
    return np.nanmedian(np.column_stack([frames["mashup_x"][at], frames["mashup_y"][at]]), axis=0)


def sites_px(frames, runs):
    """
    The start site and the goals in pixels: the median position at the outbound runs' first frame and at their last.
    """
    outbound = [r for r in runs if r["epoch"] == TRACK and r["path_id"] in OUTBOUND_PATHS]
    start = positions_at(frames, [r["frame_start"] for r in outbound])
    goals = positions_at(frames, [r["frame_end"] for r in outbound])
    return start.tolist(), goals.tolist()


def rise(start_px, goals_px, rotation_rad):
    """
    How far the goals lie above the start in the room, y up, after the y flip and this rotation.
    """
    _, y = rotated(goals_px[0] - start_px[0], -(goals_px[1] - start_px[1]), rotation_rad)
    return y


def track_rotation(frames, epoch, runs):
    """
    The counterclockwise rotation (rad) that lays the track's corridors along the room axes with the start below the goals, and the four-fold concentration of the running directions.
    """
    speed, direction = motion(frames)
    running = inside(frames, epoch) & (speed > RUNNING_PX_PER_S) & np.isfinite(direction)
    z = np.exp(4j * -direction[running]).mean()
    candidates = -np.angle(z) / 4 + np.arange(4) * np.pi / 2
    start_px, goals_px = sites_px(frames, runs)
    best = max(candidates, key=lambda rotation: rise(start_px, goals_px, rotation))
    return float(wrapped(best)), float(np.abs(z))


def to_room(x_px, y_px, scale, flip, rotation, offset):
    """
    Pixels to room metres: y negated when flip (camera y points down, room north up), divided by the scale, rotated counterclockwise by rotation, then shifted by offset.
    """
    x, y = rotated(x_px / scale, (-y_px if flip else y_px) / scale, rotation)
    return x + offset[0], y + offset[1]


def heading_to_room(head_dir, led_offset_rad, rotation_rad):
    """
    Camera heading to room heading: negated for the y flip (clockwise in the image is counterclockwise with y up), the LED offset negated the same way and subtracted so 0 is the direction of travel on average, the track rotation added, wrapped to [-pi, pi).
    """
    return wrapped(-(head_dir - led_offset_rad) + rotation_rad)


def anchor(frames, epoch, spec, start_px):
    """
    The pixel point that pins the epoch to the room and where it lands: the start site on the config's start, the arena's median position on the room centre.
    """
    if epoch["epoch"] == TRACK:
        return np.array(start_px), np.array(spec.reward_sites[START_SITE])
    here = inside(frames, epoch)
    return np.nanmedian([frames["mashup_x"][here], frames["mashup_y"][here]], axis=1), np.array(spec.room) / 2


def epoch_parameters(frames, epoch, scale, rotation, concentration, start_px):
    """
    One epoch's frame parameters: the scale, the LED separation it implies, the rotation, the flip and the offset that lands its anchor, and for the arena its extent ratio.
    """
    spec = load_environment(epoch["environment"])
    anchor_px, anchor_m = anchor(frames, epoch, spec, start_px)
    offset = anchor_m - np.array(to_room(anchor_px[0], anchor_px[1], scale, True, rotation, (0.0, 0.0)))
    parameters = {"scale_px_per_m": scale, "led_separation_m": led_separation_m(frames, epoch, scale), "rotation_rad": rotation,
                  "rotation_concentration": concentration, "flip": True, "offset_m": offset.tolist()}
    if epoch["epoch"] == ARENA:
        parameters["arena_extent_ratio"] = extent_ratio(frames, epoch, scale, spec)
    return parameters


def frame_parameters(frames, epochs, runs):
    """
    The session's frame parameters, JSON ready: the LED offset, the start and goal sites in pixels, and per epoch kind the scale (the track's with its two axis estimates), the LED separation, rotation, flip and offset.
    """
    track = next(e for e in epochs if e["epoch"] == TRACK)
    rotation, concentration = track_rotation(frames, track, runs)
    scale, scale_x, scale_y = track_scale(frames, track, rotation)
    scales = {TRACK: scale, ARENA: arena_scale(scale)}
    offset_rad, r, n = led_offset(frames)
    start_px, goals_px = sites_px(frames, runs)
    parameters = {"led_offset_rad": offset_rad, "led_offset_r": r, "led_offset_n": n, "start_px": start_px, "goals_px": goals_px}
    for epoch in epochs:
        parameters[epoch["epoch"]] = epoch_parameters(frames, epoch, scales[epoch["epoch"]], rotation, concentration, start_px)
    parameters[TRACK].update(scale_x_px_per_m=scale_x, scale_y_px_per_m=scale_y)
    return parameters


def circular_median(angles):
    """
    The circular mean plus the median of the wrapped differences from it, a median that survives a cluster straddling pi.
    """
    angles = np.asarray(angles)
    mean = np.angle(np.exp(1j * angles).sum())
    return float(wrapped(mean + np.median(wrapped(angles - mean))))


def by_subject(values_by_session, subject_by_session):
    """
    Each rat's values over its sessions.
    """
    grouped = {}
    for session_id, value in values_by_session.items():
        grouped.setdefault(subject_by_session[session_id], []).append(value)
    return grouped


def offset_medians(offsets_by_session, subject_by_session):
    """
    Each rat's median LED offset in radians over its sessions.
    """
    return {subject: circular_median(offsets) for subject, offsets in by_subject(offsets_by_session, subject_by_session).items()}


def separation_medians(separations_by_session, subject_by_session):
    """
    Each rat's median LED separation in metres over its sessions.
    """
    return {subject: float(np.median(apart)) for subject, apart in by_subject(separations_by_session, subject_by_session).items()}


def offset_warnings(offsets_by_session, subject_by_session):
    """
    The (session_id, degrees from the rat's median) pairs of the sessions whose LED offset is over OFFSET_WARN_DEG away, the swapped LEDs.
    """
    medians = offset_medians(offsets_by_session, subject_by_session)
    away = {s: float(np.degrees(wrapped(offset - medians[subject_by_session[s]]))) for s, offset in offsets_by_session.items()}
    return [(s, degrees) for s, degrees in away.items() if abs(degrees) > OFFSET_WARN_DEG]
