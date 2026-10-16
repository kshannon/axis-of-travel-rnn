"""
The versioned kinematics on a known path: a constant-speed circle gives its speed and turn rate back, and a lost heading gives no turn rate.
"""

import numpy as np

from axis_of_travel_rnn import trajectory

RATE_HZ, N_FRAMES = 60, 600
RADIUS_M, ANGULAR_RATE = 0.3, 1.5
LOST = (200, 260)
ISLAND = ((300, 310), (315, 320))


def circle():
    """
    A circle of RADIUS_M run at ANGULAR_RATE with the heading along the tangent, as t, x, y and heading arrays.
    """
    t = np.arange(N_FRAMES) / RATE_HZ
    angle = ANGULAR_RATE * t
    heading = (angle + np.pi / 2 + np.pi) % (2 * np.pi) - np.pi
    return t, RADIUS_M * np.cos(angle), RADIUS_M * np.sin(angle), heading


def test_the_window_is_an_odd_number_of_samples_at_the_rate():
    assert trajectory.smooth_window(60) == 9 and trajectory.smooth_window(20) == 3 and trajectory.KINEMATICS_VERSION == 1


def test_a_constant_speed_circle_gives_its_speed_and_turn_rate_back_through_the_wrap():
    speed, turn_rate = trajectory.kinematics(*circle(), RATE_HZ)
    assert np.allclose(speed, RADIUS_M * ANGULAR_RATE, rtol=0.02) and np.allclose(turn_rate, ANGULAR_RATE, rtol=0.02)


def test_a_lost_heading_gives_no_turn_rate_there_and_an_island_shorter_than_the_window_none_either():
    t, x, y, heading = circle()
    heading[LOST[0]:LOST[1]] = np.nan
    for first, stop in ISLAND:
        heading[first:stop] = np.nan
    speed, turn_rate = trajectory.kinematics(t, x, y, heading, RATE_HZ)
    gone = np.zeros(N_FRAMES, bool)
    gone[LOST[0]:LOST[1]] = gone[ISLAND[0][0]:ISLAND[1][1]] = True
    assert np.array_equal(np.isnan(turn_rate), gone) and np.isfinite(speed).all()
    assert np.allclose(turn_rate[~gone], ANGULAR_RATE, rtol=0.02)
    assert list(trajectory.COLUMNS) == ["t", "x", "y", "heading", "speed", "turn_rate", "n_lights", "heading_filled", "heading_held",
                                        "filled_front", "filled_back", "phase", "trip", "run", "path_id", "clean"]
