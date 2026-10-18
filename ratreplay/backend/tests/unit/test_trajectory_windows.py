"""
TrajectoryEngine.windows on the synthetic fixtures in parity with the old window logic, which is imported here as the oracle and nowhere else, and on scripted blocks for each rule alone.
"""

from pathlib import Path

import numpy as np
import pytest
from axis_of_travel_rnn import windows as old
from fixtures import S1, S6

from ratreplay_api.access.environment import EnvironmentAccess
from ratreplay_api.access.transformed import TransformedAccess
from ratreplay_api.engines.trajectory import RULES, SETTINGS, TrajectoryEngine
from ratreplay_api.engines.trajectory.labels import DWELL, OUTBOUND, PAUSE, RETURN
from ratreplay_api.engines.trajectory.windows import trip_extents

ENVIRONMENTS = Path(__file__).resolve().parents[4] / "configs" / "environments"
RATE_HZ = 60

# The settings the parity runs at: the defaults, a 5 s window, and a 10 s window every 2.5 s, which holds the complete trip
# of S1's track block in some windows.
PARITY = [{}, {"window_s": 5.0}, {"window_s": 10.0, "stride_s": 2.5}]

# A scripted block's trips (number, first, stop), runs (run, path_id, first, stop) and pauses (first, stop), all in frames:
# one complete trip over the whole block with an outbound run on path 1 and a return run on path 9.
TRIPS = ((1, 0, None),)
RUNS = ((1, 1, 100, 200), (2, 9, 300, 400))


@pytest.fixture
def built(transformed):
    """
    The blocks TrajectoryEngine.blocks makes of the two sessions of the synthetic folder that survive the funnel, S1 and S6.
    """
    environments = EnvironmentAccess(ENVIRONMENTS)
    environment = {name: environments.environment(name) for name in environments.environments()}
    made = []
    for sid in (S1, S6):
        found = TransformedAccess(transformed).session(sid)
        found = {**found, "arrays": {name: values.copy() for name, values in found["arrays"].items()}}
        made += TrajectoryEngine().blocks(found, None, environment, RULES)["blocks"]
    return made


def scripted(n_frames, kind="track", trips=TRIPS, runs=RUNS, pauses=(), lost=0):
    """
    A block of n_frames at a still finite position whose first lost frames have no heading, the trips, runs (with the phase their path gives) and pauses painted in as spans.
    """
    arrays = {name: np.zeros(n_frames) for name in ("x", "y", "heading")}
    arrays |= {"heading_filled": np.zeros(n_frames, bool), "heading_held": np.zeros(n_frames, bool), "trip": np.zeros(n_frames, np.int32),
               "run": np.zeros(n_frames, np.int32), "path_id": np.zeros(n_frames, np.int16), "phase": np.full(n_frames, DWELL, "U8")}
    arrays["heading"][:lost] = np.nan
    for number, first, stop in trips:
        arrays["trip"][first:stop] = number
    for number, path_id, first, stop in runs:
        arrays["run"][first:stop], arrays["path_id"][first:stop] = number, path_id
        arrays["phase"][first:stop] = OUTBOUND if path_id in RULES["outbound_paths"] else RETURN
    for first, stop in pauses:
        arrays["phase"][first:stop] = PAUSE
    return {"row": {"kind": kind, "n_frames": n_frames, "duration_s": n_frames / RATE_HZ}, "arrays": arrays}


def windows(block, **changes):
    """
    The engine's windows of the block at the default settings with the changes.
    """
    return TrajectoryEngine().windows(block, {**SETTINGS, **changes}, RULES)


def test_the_windows_of_the_fixture_blocks_equal_the_old_counts_rows_and_verdicts(built):
    seen = {"rows": 0, "trips": 0, "failing": 0, "reasons": set()}
    for changes in PARITY:
        settings = {**SETTINGS, **changes}
        for block in built:
            row, arrays = block["row"], block["arrays"]
            found, rows = TrajectoryEngine().windows(block, settings, RULES), old.window_rows(arrays, row, settings)
            assert found["count"] == old.window_count(row["n_frames"], old.rate_of(row), settings) == len(found["rows"]) == len(rows)
            for mine, theirs in zip(found["rows"], rows):
                assert {name: mine[name] for name in theirs} == theirs and (mine["reason"] is None) == mine["ok"]
            ok, reason = old.verdict(row, arrays, settings)
            assert found["verdict"]["ok"] == ok and found["verdict"]["reasons"][:1] == ([] if ok else [reason])
            seen["rows"] += len(rows)
            seen["trips"] += sum(theirs["trips_complete"] for theirs in rows)
            seen["failing"] += sum(not theirs["ok"] for theirs in rows)
            seen["reasons"].add(reason)
    assert seen["rows"] > 0 and seen["trips"] > 0 and seen["failing"] > 0
    assert seen["reasons"] == {None, "no window fits", "0 complete trips under 1"}


def test_a_block_exactly_one_window_plus_horizon_long_yields_one_window_and_one_frame_less_yields_none():
    exact = round((SETTINGS["window_s"] + SETTINGS["horizon_s"]) * RATE_HZ)
    assert windows(scripted(exact))["count"] == 1 and windows(scripted(exact))["verdict"] == {"ok": True, "reasons": []}
    short = windows(scripted(exact - 1))
    assert short["count"] == 0 and short["rows"] == [] and short["verdict"] == {"ok": False, "reasons": ["no window fits"]}
    # 16.3 s minus 16.1 s minus 0.2 s comes out just under zero in floats, the tolerance keeps the window.
    assert 978 / RATE_HZ - 16.1 - 0.2 < 0
    assert windows(scripted(978), window_s=16.1, horizon_s=0.2)["count"] == 1
    assert windows(scripted(977), window_s=16.1, horizon_s=0.2)["count"] == 0
    assert windows(scripted(exact + 10 * RATE_HZ))["count"] == 2 and windows(scripted(exact + 10 * RATE_HZ - 1))["count"] == 1


def test_heading_lost_on_more_than_the_allowed_share_fails_the_block_and_the_windows_it_covers_on_heading():
    settings = {"window_s": 5.0, "stride_s": 5.0, "horizon_s": 0.0}
    allowed = windows(scripted(1200, lost=240), **settings)
    assert allowed["count"] == 4 and allowed["verdict"]["ok"] and [row["ok"] for row in allowed["rows"]] == [False, True, True, True]
    assert allowed["rows"][0]["reason"] == "measured heading 20% under 80%"
    over = windows(scripted(1200, lost=360), **settings)
    assert over["verdict"] == {"ok": False, "reasons": ["measured heading 70% under 80%"]}
    assert [(row["ok"], row["reason"]) for row in over["rows"]] == [(False, "measured heading 0% under 80%"), (True, None), (True, None), (True, None)]


def test_a_window_with_a_frame_whose_position_is_not_finite_fails_on_position_and_the_block_verdict_does_not_read_it():
    block = scripted(1200)
    block["arrays"]["x"][700] = np.nan
    found = windows(block, window_s=5.0, stride_s=5.0, horizon_s=0.0)
    assert [row["reason"] for row in found["rows"]] == [None, None, "position not finite", None] and found["verdict"]["ok"]


def test_a_block_without_a_complete_trip_fails_on_trips_with_the_count_in_the_reason_on_the_track_only():
    cut = scripted(2430, trips=((-1, 0, None),))
    assert windows(cut)["verdict"] == {"ok": False, "reasons": ["0 complete trips under 1"]}
    assert windows(scripted(2430), min_complete_trips=2)["verdict"] == {"ok": False, "reasons": ["1 complete trips under 2"]}
    assert windows(scripted(2430, kind="arena", trips=()))["verdict"]["ok"]
    assert windows(scripted(100, trips=((-1, 0, None),)))["verdict"]["reasons"] == ["no window fits", "0 complete trips under 1"]


def test_a_trip_is_inside_a_window_when_its_outbound_start_and_its_return_end_both_are_a_pause_in_the_return_run_included():
    # Trip 1 returns on frames 900 to 1099 and stands still for its first 60 and its last 50 frames, trip 2 starts at 1500 and returns on 2100 to 2250.
    runs = ((1, 1, 100, 300), (2, 9, 900, 1100), (3, 1, 1600, 1800), (4, 9, 2100, 2251))
    trips = ((1, 0, 1500), (2, 1500, None))
    block = scripted(3000, trips=trips, runs=runs, pauses=((900, 960), (1050, 1100)))
    found = windows(block, window_s=18.0, stride_s=10.0, horizon_s=0.0)
    assert [(row["first"], row["stop"]) for row in found["rows"]] == [(0, 1080), (600, 1680), (1200, 2280), (1800, 2880)]
    # Window 0 stops inside trip 1's last pause, so the trip is not whole in it, window 2 holds trip 2 whole.
    assert [(row["trips_complete"], row["trips_partial"]) for row in found["rows"]] == [(0, 1), (0, 2), (1, 0), (0, 1)]


def test_the_end_of_a_trip_is_the_end_of_its_first_stretch_on_a_return_path_as_the_old_rule_finds_it():
    outbound = (1, 1, 100, 300)
    cases = [  # runs, pauses, the last frame of the trip's extent
        ((outbound, (2, 9, 900, 1100)), ((900, 960),), 1099),
        ((outbound, (2, 9, 900, 1100)), ((1050, 1100),), 1099),
        ((outbound, (2, 9, 900, 1000), (3, 10, 1300, 1500)), ((900, 1000),), 999),
        ((outbound, (2, 9, 900, 1000), (3, 10, 1000, 1100)), (), 1099),
        ((outbound, (2, 9, 900, 1100), (3, 2, 1000, 1050)), (), 999),
    ]
    for runs, pauses, end in cases:
        block = scripted(3000, runs=runs, pauses=pauses)
        assert trip_extents(block["arrays"], RULES["return_paths"]) == old.trip_extents(block["arrays"]) == [(True, 0, end)]
        assert windows(block)["count"] == 1


def test_a_changed_window_length_changes_the_count_and_the_rate_in_the_settings_changes_nothing():
    block = scripted(3000)
    assert [windows(block, window_s=seconds)["count"] for seconds in (40.0, 20.0, 10.0)] == [1, 3, 4]
    assert windows(block, stride_s=5.0, window_s=20.0)["count"] == 6
    first = windows(block, window_s=20.0)["rows"][0]
    assert (first["first"], first["burn_in_stop"], first["window_stop"], first["stop"], first["start_s"], first["stop_s"]) == (0, 60, 1200, 1230, 0.0, 20.5)
    assert windows(block, rate_hz=20) == windows(block, rate_hz=60) == windows(block)
