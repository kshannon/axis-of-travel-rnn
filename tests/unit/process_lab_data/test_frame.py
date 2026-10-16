"""
Frame conversion on a scripted session with a known scale, track orientation and LED mounting angle, seen by a camera with y down.
"""

import numpy as np
import pytest

from environments import load_environment
from process_lab_data import frame, select
from ratreplay import data

from .conftest import RATE_HZ

# The scripted session: an arena epoch of ARENA_FRAMES then a track epoch, both drawn in room metres from the configs and
# projected into a camera whose y points down. The room is rotated ROTATION_DEG counterclockwise against the camera's
# flipped axes, the track's start site sits at START_PX and the arena's centre at ARENA_PX, each epoch with its own
# pixel scale (parallax). The LEDs sit LED_APART_M apart, as on the real implants rather than the paper's 5 cm, and
# MOUNT_DEG from the direction of travel in camera convention, and the back LED is lost over BACK_LOST frames of the
# track. On the track the rat holds the start and makes the TRIPS, each a route (its path id), a hold at the goal and a
# return side (its path id), at RUN_SPEED_M_S along the exact corridor centrelines: route ee then east, route ww then
# west. The LOPSIDED_TRIPS take the west return once in twelve, so its corridor's occupancy peak falls under the
# prominence floor and the x estimate of the scale spans the stem to the east side instead.
ARENA_FRAMES = 1200
TRIPS = (("ee", 1, "east", 9), ("ww", 3, "west", 10))
LOPSIDED_TRIPS = TRIPS[:1] * 11 + TRIPS[1:]
SCALE_TRACK, SCALE_ARENA = 400.0, 440.0
LED_APART_M = 0.065
ROTATION_DEG, MOUNT_DEG = 20.0, 110.0
START_PX, ARENA_PX = np.array([500.0, 600.0]), np.array([1100.0, 250.0])
ARENA_RADIUS_M, ARENA_RATES = 0.22, (0.9, 1.3)
RUN_SPEED_M_S = 0.4
HOLD_FRAMES = {"start": 300, "goal": 180, "between": 120}
BACK_LOST = (400, 460)
PLANTED_OFFSETS = {"a_rec1": 110.0, "a_rec2": 108.0, "a_rec3": 112.0, "a_rec4": -70.0, "b_rec1": 170.0, "b_rec2": -175.0}
PLANTED_SUBJECTS = {"a_rec1": "a", "a_rec2": "a", "a_rec3": "a", "a_rec4": "a", "b_rec1": "b", "b_rec2": "b"}
# A creep in px/s that is over the running floor at SCALE_TRACK and under it at SCALE_ARENA.
CREEP_PX_PER_S = 13.0


def samples(waypoints):
    """
    Positions along the waypoints at RUN_SPEED_M_S and RATE_HZ, the last point excluded.
    """
    legs = [np.linspace(a, b, round(np.hypot(*np.subtract(b, a)) / RUN_SPEED_M_S * RATE_HZ), endpoint=False)
            for a, b in zip(waypoints[:-1], waypoints[1:])]
    return np.concatenate(legs)


def track_in_room(spec, trips):
    """
    The track epoch in room metres over these trips, positions per frame and the runs rows numbered from the first track frame.
    """
    start, top = spec.reward_sites["start"], spec.returns["east"][0][1]
    legs = [("hold", start, HOLD_FRAMES["start"])]
    for route, path, side, back in trips:
        goal = spec.reward_sites[f"g_{route}"]
        legs += [("run", path, spec.routes[route]), ("hold", goal, HOLD_FRAMES["goal"]),
                 ("run", back, [goal, [goal[0], top]] + spec.returns[side]), ("hold", start, HOLD_FRAMES["between"])]
    legs[-1] = ("hold", start, HOLD_FRAMES["start"])
    positions, runs = [], []
    for kind, what, detail in legs:
        if kind == "hold":
            positions.append(np.repeat([what], detail, axis=0))
            continue
        first = sum(len(p) for p in positions) + 1
        positions.append(samples(detail))
        runs.append({"run": len(runs) + 1, "epoch": "track", "path_id": what, "frame_start": first + ARENA_FRAMES,
                     "frame_end": sum(len(p) for p in positions) + ARENA_FRAMES, "clean": True})
    return np.concatenate(positions), runs


def arena_in_room(spec):
    """
    The arena epoch in room metres: a spiralling path about the room centre whose radius breathes up to ARENA_RADIUS_M.
    """
    seconds = np.arange(ARENA_FRAMES) / RATE_HZ
    radius = ARENA_RADIUS_M * (0.6 + 0.4 * np.cos(ARENA_RATES[0] * seconds))
    angle = ARENA_RATES[1] * seconds
    return np.array(spec.room) / 2 + np.column_stack([radius * np.cos(angle), radius * np.sin(angle)])


def to_camera(points_m, anchor_m, anchor_px, scale):
    """
    Room metres to camera pixels: un-rotate about the anchor, scale, flip y, place the anchor at anchor_px.
    """
    x, y = frame.rotated(points_m[:, 0] - anchor_m[0], points_m[:, 1] - anchor_m[1], -np.radians(ROTATION_DEG))
    return np.column_stack([anchor_px[0] + scale * x, anchor_px[1] - scale * y])


def camera_heading(px):
    """
    The camera heading per frame: the direction of the next step, held through the holds, plus the mounting angle.
    """
    dx, dy = np.diff(px[:, 0], append=px[-1, 0]), np.diff(px[:, 1], append=px[-1, 1])
    moving = np.hypot(dx, dy) > 0
    last = np.maximum.accumulate(np.where(moving, np.arange(len(px)), 0))
    return frame.wrapped(np.arctan2(dy, dx)[last] + np.radians(MOUNT_DEG))


def scripted_session(trips=TRIPS):
    """
    The scripted session as the frames dict, the epochs and the runs.
    """
    track, arena = load_environment("triple_t"), load_environment("open_arena")
    track_m, runs = track_in_room(track, trips)
    px = np.concatenate([to_camera(arena_in_room(arena), np.array(arena.room) / 2, ARENA_PX, SCALE_ARENA),
                         to_camera(track_m, track.reward_sites["start"], START_PX, SCALE_TRACK)])
    n = len(px)
    heading = camera_heading(px)
    half = np.where(np.arange(n) < ARENA_FRAMES, SCALE_ARENA, SCALE_TRACK) * LED_APART_M / 2
    along = np.column_stack([np.cos(heading), np.sin(heading)]) * half[:, None]
    front, back = px + along, px - along
    lost = np.zeros(n, bool)
    lost[ARENA_FRAMES + BACK_LOST[0]:ARENA_FRAMES + BACK_LOST[1]] = True
    back[lost] = np.nan
    frames = {"frame": np.arange(1, n + 1), "t": np.arange(n) / RATE_HZ,
              "front_x": front[:, 0], "front_y": front[:, 1], "back_x": back[:, 0], "back_y": back[:, 1],
              "head_dir": np.where(lost, np.nan, heading), "unfilled_front": np.zeros(n, bool), "unfilled_back": lost,
              "mashup_x": np.where(lost, front[:, 0], px[:, 0]), "mashup_y": np.where(lost, front[:, 1], px[:, 1])}
    epochs = [{"epoch": "arena", "environment": "open_arena", "frame_start": 1, "frame_end": ARENA_FRAMES},
              {"epoch": "track", "environment": "triple_t", "frame_start": ARENA_FRAMES + 1, "frame_end": n}]
    return frames, epochs, runs


def circular_mean(angles):
    """
    The mean angle and the concentration of a set of angles.
    """
    z = np.exp(1j * angles).mean()
    return float(np.angle(z)), float(np.abs(z))


def test_track_scale_recovers_the_planted_scale_on_both_axes_from_the_geometry_while_the_leds_read_their_planted_separation():
    frames, epochs, _ = scripted_session()
    scale, scale_x, scale_y = frame.track_scale(frames, epochs[1], np.radians(ROTATION_DEG))
    assert scale_x == pytest.approx(SCALE_TRACK, rel=0.01) and scale_y == pytest.approx(SCALE_TRACK, rel=0.01)
    assert scale == (scale_x + scale_y) / 2
    assert frame.centreline_extent_m(load_environment("triple_t")) == pytest.approx([1.52, 1.17])
    assert frame.arena_scale(SCALE_TRACK) == pytest.approx(SCALE_TRACK * 2.4 / 2.2)
    assert frame.led_separation_m(frames, epochs[1], SCALE_TRACK) == pytest.approx(LED_APART_M, rel=0.01)
    assert frame.led_separation_m(frames, epochs[0], SCALE_ARENA) == pytest.approx(LED_APART_M, rel=0.01)


def test_a_rarely_taken_return_side_loses_its_peak_and_the_axis_estimates_disagree_by_over_the_tolerance():
    frames, epochs, runs = scripted_session(LOPSIDED_TRIPS)
    assert sum(r["path_id"] == 10 for r in runs) == 1 and sum(r["path_id"] == 9 for r in runs) == 11
    p = frame.frame_parameters(frames, epochs, runs)["track"]
    assert p["scale_y_px_per_m"] == pytest.approx(SCALE_TRACK, rel=0.01) and p["scale_x_px_per_m"] < 0.9 * SCALE_TRACK
    assert frame.axis_disagreement(p) > frame.AXIS_AGREE
    both = frame.frame_parameters(*scripted_session())["track"]
    assert frame.axis_disagreement(both) < 0.01 < frame.AXIS_AGREE


def test_the_led_offset_recovers_the_mounting_angle_as_ratreplay_computes_it():
    frames, _, _ = scripted_session()
    offset_rad, r, n = frame.led_offset(frames)
    assert np.degrees(offset_rad) == pytest.approx(MOUNT_DEG, abs=1.0) and r > 0.9 and n > 1000
    t, x, y = frames["t"], frames["mashup_x"], frames["mashup_y"]
    theirs = data.led_offset(frames["head_dir"], data.motion_direction(t, x, y), data.speed_from_positions(t, x, y))
    assert (offset_rad, r) == (theirs["rad"], theirs["r"]) and frame.RUNNING_PX_PER_S == data.RUNNING_SPEED


def test_still_is_speed_under_the_running_floor_at_each_epochs_own_scale_and_never_outside_an_epoch():
    frames, epochs, runs = scripted_session()
    still = frame.still(frames, epochs)
    hold = slice(ARENA_FRAMES + 5, ARENA_FRAMES + HOLD_FRAMES["start"] - 5)
    assert still[hold].all() and not still[:ARENA_FRAMES].any()
    assert not still[runs[0]["frame_start"] + 5:runs[0]["frame_end"] - 5].any()
    n, t = 600, np.arange(600) / RATE_HZ
    x, y = CREEP_PX_PER_S * t, np.zeros(n)
    apart = np.where(np.arange(n) < 300, SCALE_TRACK, SCALE_ARENA) * frame.NOMINAL_LED_SEPARATION_M
    creep = {"frame": np.arange(1, n + 1), "t": t, "front_x": x + apart, "front_y": y, "back_x": x, "back_y": y,
             "mashup_x": x, "mashup_y": y, "unfilled_front": np.zeros(n, bool), "unfilled_back": np.zeros(n, bool)}
    two = [{"epoch": "track", "frame_start": 1, "frame_end": 300}, {"epoch": "arena", "frame_start": 301, "frame_end": 540}]
    assert CREEP_PX_PER_S / SCALE_TRACK > select.RUNNING_FLOOR_M_PER_S > CREEP_PX_PER_S / SCALE_ARENA
    still = frame.still(creep, two)
    assert not still[5:300].any() and still[300:540].all() and not still[540:].any()


def test_track_rotation_recovers_the_orientation_with_the_start_below_the_goals():
    frames, epochs, runs = scripted_session()
    rotation, concentration = frame.track_rotation(frames, epochs[1], runs)
    assert np.degrees(rotation) == pytest.approx(ROTATION_DEG, abs=1.0) and concentration > 0.8
    start_px, goals_px = frame.sites_px(frames, runs)
    assert frame.rise(start_px, goals_px, rotation) > 0.5 * SCALE_TRACK


def test_frame_parameters_land_the_sites_on_the_configs_lay_the_corridors_along_the_axes_and_turn_heading_onto_motion():
    frames, epochs, runs = scripted_session()
    track, arena = load_environment("triple_t"), load_environment("open_arena")
    p = frame.frame_parameters(frames, epochs, runs)
    kinds = {kind: (p[kind]["scale_px_per_m"], p[kind]["flip"], p[kind]["rotation_rad"], p[kind]["offset_m"]) for kind in ("track", "arena")}
    x, y = frame.to_room(frames["mashup_x"], frames["mashup_y"], *kinds["track"])
    assert frame.to_room(*p["start_px"], *kinds["track"]) == pytest.approx(track.reward_sites["start"], abs=0.01)
    assert frame.to_room(*p["goals_px"], *kinds["track"])[1] == pytest.approx(track.reward_sites["g_ee"][1], abs=0.01)
    assert p["track"]["scale_px_per_m"] == pytest.approx(SCALE_TRACK, rel=0.01)
    assert p["track"]["scale_x_px_per_m"] == pytest.approx(SCALE_TRACK, rel=0.01) and p["track"]["scale_y_px_per_m"] == pytest.approx(SCALE_TRACK, rel=0.01)
    assert p["arena"]["scale_px_per_m"] == p["track"]["scale_px_per_m"] * frame.PARALLAX_RATIO
    assert p["track"]["led_separation_m"] == pytest.approx(LED_APART_M, rel=0.01) and p["arena"]["led_separation_m"] == pytest.approx(LED_APART_M, rel=0.02)
    assert p["arena"]["arena_extent_ratio"] == pytest.approx(2 * ARENA_RADIUS_M / arena.params["diameter"], abs=0.05)
    assert "arena_extent_ratio" not in p["track"] and "scale_x_px_per_m" not in p["arena"]
    stem = slice(runs[0]["frame_start"] - 1, runs[0]["frame_start"] + 60)
    assert x[stem] == pytest.approx(track.reward_sites["start"][0], abs=0.01) and (np.diff(y[stem]) > 0).all()
    speed, _ = frame.motion(frames)
    running = select.inside(frames, epochs[1]) & (speed > frame.RUNNING_PX_PER_S) & np.isfinite(frames["head_dir"])
    motion_room = data.motion_direction(frames["t"], x, y)
    assert np.median(np.abs(frame.wrapped(4 * motion_room[running]))) < 0.02
    heading_room = frame.heading_to_room(frames["head_dir"], p["led_offset_rad"], p["track"]["rotation_rad"])
    mean, r = circular_mean(heading_room[running] - motion_room[running])
    assert abs(np.degrees(mean)) < 1.0 and r > 0.95
    ax, ay = frame.to_room(frames["mashup_x"][:ARENA_FRAMES], frames["mashup_y"][:ARENA_FRAMES], *kinds["arena"])
    assert np.hypot(ax - 0.9, ay - 0.9).max() == pytest.approx(ARENA_RADIUS_M, abs=0.01)
    assert p["arena"]["rotation_rad"] == p["track"]["rotation_rad"]


def test_offset_warnings_flag_the_session_180_degrees_from_its_rats_median():
    offsets = {s: np.radians(d) for s, d in PLANTED_OFFSETS.items()}
    warnings = frame.offset_warnings(offsets, PLANTED_SUBJECTS)
    assert [s for s, _ in warnings] == ["a_rec4"] and abs(warnings[0][1]) == pytest.approx(180.0, abs=3.0)
    medians = frame.offset_medians(offsets, PLANTED_SUBJECTS)
    assert np.degrees(medians["a"]) == pytest.approx(110.0, abs=3.0) and np.degrees(medians["b"]) == pytest.approx(177.5)
