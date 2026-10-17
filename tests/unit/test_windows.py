"""
The window logic on scripted blocks: the window count at its boundaries, the heading and trip shares, the checks of each window, each verdict rule alone, the totals and the settings file round trip.
"""

import numpy as np

from axis_of_travel_rnn import windows

RATE_HZ = 60
SETTINGS = windows.DEFAULTS
WINDOW_SETTINGS = {**SETTINGS, "window_s": 20.0, "stride_s": 10.0, "horizon_s": 0.0, "burn_in_s": 1.0, "min_heading_measured": 0.9}
ONE_WINDOW_FRAMES = int((windows.WINDOW_S + windows.HORIZON_S) * RATE_HZ)
STRIDE_FRAMES = int(windows.STRIDE_S * RATE_HZ)
MANIFEST = {"run": {"timestamp": "2026-10-16T10:00:00+00:00", "rules": {"select": {"JUMP_PX": 40.0, "MIN_BLOCK_S": 10.0}}}}


def scripted_block(n_frames, lost=0, filled=0, held=0, trips=(1,)):
    """
    A block of n_frames at a still, finite position whose first frames lose, then fill, then hold the heading in that order, with the trip numbers spread evenly over the frames and no return path.
    """
    heading = np.zeros(n_frames)
    heading[:lost] = np.nan
    heading_filled, heading_held = np.zeros(n_frames, bool), np.zeros(n_frames, bool)
    heading_filled[lost:lost + filled] = True
    heading_held[lost + filled:lost + filled + held] = True
    return {"x": np.zeros(n_frames), "y": np.zeros(n_frames), "heading": heading, "heading_filled": heading_filled,
            "heading_held": heading_held, "path_id": np.zeros(n_frames, np.int16),
            "trip": np.array(trips, np.int32)[np.arange(n_frames) * len(trips) // n_frames]}


def row(block_id, kind, n_frames):
    """
    The csv row fields the window logic reads.
    """
    return {"block_id": block_id, "kind": kind, "n_frames": n_frames, "duration_s": n_frames / RATE_HZ}


def rows_of(seconds, settings=WINDOW_SETTINGS, **columns):
    """
    The window rows of a scripted block of this many seconds without trips, the columns given replacing the scripted ones.
    """
    n_frames = seconds * RATE_HZ
    return windows.window_rows({**scripted_block(n_frames, trips=(0,)), **columns}, row("b", "track", n_frames), settings)


def test_window_count_at_the_boundaries_and_in_seconds_so_the_rate_does_not_matter():
    assert windows.window_count(ONE_WINDOW_FRAMES, RATE_HZ, SETTINGS) == 1
    assert windows.window_count(ONE_WINDOW_FRAMES - 1, RATE_HZ, SETTINGS) == 0
    assert windows.window_count(ONE_WINDOW_FRAMES + STRIDE_FRAMES, RATE_HZ, SETTINGS) == 2
    assert windows.window_count(ONE_WINDOW_FRAMES + STRIDE_FRAMES - 1, RATE_HZ, SETTINGS) == 1
    assert windows.window_count(ONE_WINDOW_FRAMES // 3, RATE_HZ / 3, SETTINGS) == 1
    assert np.array_equal(windows.window_starts(ONE_WINDOW_FRAMES + 2 * STRIDE_FRAMES, RATE_HZ, SETTINGS), [0.0, 10.0, 20.0])


def test_heading_shares_count_a_measured_heading_as_finite_and_neither_filled_nor_held_and_trip_shares_by_trip_number():
    block = scripted_block(100, lost=10, filled=20, held=10, trips=(1, 1, -2, 3))
    assert windows.heading_shares(block) == {"measured": 0.6, "filled": 0.2, "held": 0.1}
    assert windows.trip_shares(block) == {"complete": 2 / 3, "partial": 1 / 3}
    assert windows.trip_shares(scripted_block(100, trips=(0,))) == {"complete": 0.0, "partial": 0.0}


def test_windows_are_checked_one_by_one():
    heading, x = np.zeros(50 * RATE_HZ), np.zeros(50 * RATE_HZ)
    heading[1100:1300] = np.nan
    x[2500] = np.nan
    rows = rows_of(50, heading=heading, x=x)
    assert len(rows) == windows.window_count(50 * RATE_HZ, RATE_HZ, WINDOW_SETTINGS) == 4
    assert (rows[1]["first"], rows[1]["burn_in_stop"], rows[1]["window_stop"], rows[1]["stop"]) == (600, 660, 1800, 1800)
    assert [row["ok"] for row in rows] == [True, False, True, False]
    assert rows[1]["heading_measured"] == 1000 / 1200 and rows[3]["position_finite"] == 1199 / 1200


def test_a_window_is_ok_at_exactly_the_minimum_heading_share():
    heading = np.zeros(20 * RATE_HZ)
    heading[:120] = np.nan  # 1080 of 1200 frames measured, 0.9
    assert rows_of(20, heading=heading)[0]["ok"]


def test_the_horizon_extends_each_window_past_its_training_part_up_to_the_block_end():
    rows = rows_of(50, {**WINDOW_SETTINGS, "horizon_s": 5.0})
    assert [(row["window_stop"], row["stop"]) for row in rows] == [(1200, 1500), (1800, 2100), (2400, 2700)]
    (only,) = rows_of(25, {**WINDOW_SETTINGS, "horizon_s": 5.0})
    assert (only["window_stop"], only["stop"]) == (1200, 25 * RATE_HZ)


def test_a_trip_is_inside_a_window_when_its_outbound_start_and_return_end_both_are():
    trip, path_id = np.zeros(50 * RATE_HZ, np.int32), np.zeros(50 * RATE_HZ, np.int16)
    trip[0:600], trip[600:1500], trip[1500:] = 1, 2, -3  # trip 3 is partial, the block ends before it returns
    path_id[200:300], path_id[1100:1300] = 9, 10  # the return runs of trips 1 and 2
    rows = rows_of(50, trip=trip, path_id=path_id)
    assert [(row["first"], row["stop"]) for row in rows] == [(0, 1200), (600, 1800), (1200, 2400), (1800, 3000)]
    # Trip 2 starts inside the first window and returns past its end, so only the second window holds it whole.
    assert [(row["trips_complete"], row["trips_partial"]) for row in rows] == [(1, 1), (1, 1), (0, 2), (0, 1)]


def test_each_verdict_rule_fires_alone_and_a_fit_block_is_ok():
    good = scripted_block(ONE_WINDOW_FRAMES, trips=(1, -2, 3))
    assert windows.verdict(row("b", "track", ONE_WINDOW_FRAMES), good, SETTINGS) == (True, None)
    assert windows.verdict(row("b", "track", ONE_WINDOW_FRAMES - 1), good, SETTINGS) == (False, "no window fits")
    dark = scripted_block(ONE_WINDOW_FRAMES, lost=ONE_WINDOW_FRAMES // 2, trips=(1, -2, 3))
    assert windows.verdict(row("b", "track", ONE_WINDOW_FRAMES), dark, SETTINGS) == (False, "measured heading 50% under 80%")
    cut = scripted_block(ONE_WINDOW_FRAMES, trips=(-1, -2, -3))
    assert windows.verdict(row("b", "track", ONE_WINDOW_FRAMES), cut, SETTINGS) == (False, "0 complete trips under 1")
    one = scripted_block(ONE_WINDOW_FRAMES, trips=(-1, 2, -3))
    assert windows.verdict(row("b", "track", ONE_WINDOW_FRAMES), one, SETTINGS) == (True, None)
    assert windows.verdict(row("b", "arena", ONE_WINDOW_FRAMES), cut, SETTINGS) == (True, None)


def test_summarize_totals_the_ok_blocks_their_windows_and_hours_per_kind_and_overall():
    rows = [row("t1", "track", ONE_WINDOW_FRAMES + STRIDE_FRAMES), row("t2", "track", ONE_WINDOW_FRAMES - 1), row("a1", "arena", ONE_WINDOW_FRAMES)]
    blocks = {"t1": scripted_block(rows[0]["n_frames"]), "t2": scripted_block(rows[1]["n_frames"]), "a1": scripted_block(rows[2]["n_frames"], trips=(0,))}
    summary = windows.summarize(rows, blocks, SETTINGS)
    assert summary["track"] == {"blocks_ok": 1, "blocks_trouble": 1, "windows": 2, "hours_ok": rows[0]["duration_s"] / 3600}
    assert summary["arena"] == {"blocks_ok": 1, "blocks_trouble": 0, "windows": 1, "hours_ok": rows[2]["duration_s"] / 3600}
    assert summary["overall"] == {"blocks_ok": 2, "blocks_trouble": 1, "windows": 3, "hours_ok": (rows[0]["duration_s"] + rows[2]["duration_s"]) / 3600}


def test_write_settings_then_read_settings_round_trips_the_settings_the_manifest_facts_and_the_totals_as_plain_yaml(tmp_path):
    path = tmp_path / "configs" / "datasets" / "lab_blocks.yaml"
    summary = windows.summarize([row("a1", "arena", ONE_WINDOW_FRAMES)], {"a1": scripted_block(ONE_WINDOW_FRAMES, trips=(0,))}, SETTINGS)
    windows.write_settings(SETTINGS, MANIFEST, summary, path)
    text = path.read_text()
    assert "!!" not in text and "[" not in text and len(text.splitlines()) < 40
    read = windows.read_settings(path)
    assert list(read) == ["settings", "processed_manifest_timestamp", "rules", "totals", "written_at"]
    assert read["settings"] == SETTINGS and read["processed_manifest_timestamp"] == MANIFEST["run"]["timestamp"]
    assert read["rules"] == MANIFEST["run"]["rules"] and read["totals"] == summary
    assert windows.CONFIG.parts[-3:] == ("configs", "datasets", "lab_blocks.yaml")
