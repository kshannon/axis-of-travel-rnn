"""
The window logic on scripted blocks: the window count at its boundaries, the heading and trip shares, each verdict rule alone, the totals and the settings file round trip.
"""

import numpy as np

from axis_of_travel_rnn import windows

RATE_HZ = 60
SETTINGS = windows.DEFAULTS
ONE_WINDOW_FRAMES = int((windows.WINDOW_S + windows.HORIZON_S) * RATE_HZ)
STRIDE_FRAMES = int(windows.STRIDE_S * RATE_HZ)
MANIFEST = {"run": {"timestamp": "2026-10-16T10:00:00+00:00", "rules": {"select": {"JUMP_PX": 40.0, "MIN_BLOCK_S": 10.0}}}}


def scripted_block(n_frames, lost=0, filled=0, held=0, trips=(1,)):
    """
    A block of n_frames whose first frames lose, then fill, then hold the heading in that order, with the trip numbers spread evenly over the frames.
    """
    heading = np.zeros(n_frames)
    heading[:lost] = np.nan
    heading_filled, heading_held = np.zeros(n_frames, bool), np.zeros(n_frames, bool)
    heading_filled[lost:lost + filled] = True
    heading_held[lost + filled:lost + filled + held] = True
    return {"heading": heading, "heading_filled": heading_filled, "heading_held": heading_held,
            "trip": np.array(trips, np.int32)[np.arange(n_frames) * len(trips) // n_frames]}


def row(block_id, kind, n_frames):
    """
    The csv row fields the window logic reads.
    """
    return {"block_id": block_id, "kind": kind, "n_frames": n_frames, "duration_s": n_frames / RATE_HZ}


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
