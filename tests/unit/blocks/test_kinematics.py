"""
The kinematics on a known path: a constant speed circle gives its speed and turn rate back, and a lost heading gives no turn rate.
"""

import numpy as np

from axis_of_travel_rnn.blocks import RULES
from axis_of_travel_rnn.blocks import kinematics

RATE_HZ, N_FRAMES = 60, 600
RADIUS_M, ANGULAR_RATE = 0.3, 1.5
LOST = (200, 260)
ISLAND = ((300, 310), (315, 320))
NO_BREAKS = np.zeros(N_FRAMES, bool)


def circle():
    """
    A circle of RADIUS_M run at ANGULAR_RATE with the heading along the tangent, as x, y and heading arrays.
    """
    angle = ANGULAR_RATE * np.arange(N_FRAMES) / RATE_HZ
    heading = (angle + np.pi / 2 + np.pi) % (2 * np.pi) - np.pi
    return RADIUS_M * np.cos(angle), RADIUS_M * np.sin(angle), heading


def test_the_window_is_an_odd_number_of_samples_at_the_rate():
    assert kinematics.smooth_window(60, RULES) == 9 and kinematics.smooth_window(20, RULES) == 3


def test_a_constant_speed_circle_gives_its_speed_and_turn_rate_back_through_the_wrap():
    speed, _, turn_rate = kinematics.kinematics(*circle(), NO_BREAKS, RATE_HZ, RULES)
    assert np.allclose(speed, RADIUS_M * ANGULAR_RATE, rtol=0.02) and np.allclose(turn_rate, ANGULAR_RATE, rtol=0.02)


def test_a_lost_heading_gives_no_turn_rate_there_and_an_island_shorter_than_the_window_none_either():
    x, y, heading = circle()
    heading[LOST[0]:LOST[1]] = np.nan
    for first, stop in ISLAND:
        heading[first:stop] = np.nan
    speed, _, turn_rate = kinematics.kinematics(x, y, heading, NO_BREAKS, RATE_HZ, RULES)
    gone = np.zeros(N_FRAMES, bool)
    gone[LOST[0]:LOST[1]] = gone[ISLAND[0][0]:ISLAND[1][1]] = True
    assert np.array_equal(np.isnan(turn_rate), gone) and np.isfinite(speed).all()
    assert np.allclose(turn_rate[~gone], ANGULAR_RATE, rtol=0.02)
