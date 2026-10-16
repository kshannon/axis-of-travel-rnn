"""
The Blocks tab on a processed dataset the processor built from its tests' synthetic sessions: the table rows and totals with every
block read once, the verdicts following the window setting, the environment under a track and an arena block, the block lanes,
the settings file, and the tab without a manifest.
"""

from axis_of_travel_rnn import trajectory, windows
from ratreplay import app, blocks
from tests.unit.process_lab_data.conftest import S1, S6

from .test_app import dependency_edges, reaches

S1_TRACK, S6_TRACK, S1_ARENA = f"{S1}_track_01", f"{S6}_track_01", f"{S1}_arena_01"
SHORT = {**windows.DEFAULTS, "window_s": 10.0, "stride_s": 5.0}
BACK_LOST = [699, 818]


def cells(table):
    """
    Every row of the blocks table as its cell texts, the load button's id last.
    """
    return [[td.children if isinstance(td.children, str) else td.children.id for td in tr.children] for tr in table.children[1].children]


def test_the_table_and_totals_come_from_the_processed_folder_each_block_read_once_and_the_verdicts_follow_the_window_setting(built, monkeypatch):
    rows, shares = blocks.load_all(built)
    assert [row["block_id"] for row in rows] == [S1_TRACK, S6_TRACK, S1_ARENA] and set(blocks.CACHE) == set(shares)
    reads = []
    monkeypatch.setattr(trajectory, "load_block", lambda path: reads.append(path))
    assert blocks.load_all(built)[1].keys() == shares.keys() and reads == []
    at_defaults = cells(app.blocks_table(rows, shares, windows.DEFAULTS))
    assert [row[-2] for row in at_defaults] == [f"trouble, {windows.NO_WINDOW}"] * 3
    assert at_defaults[0][:-2] == [S1, "track", "automatic", "0.3", "3", "1", "2", "90%", "10%", "0%", "0"]
    assert at_defaults[0][-1] == {"type": "load-block", "index": S1_TRACK}
    short = cells(app.blocks_table(rows, shares, SHORT))
    assert [row[-2] for row in short] == ["ok", "trouble, 0 complete trips under 1", "ok"]
    assert [row[-3] for row in short] == ["2", "2", "2"]
    assert app.block_totals_values(windows.summarize(rows, shares, SHORT), SHORT) == [
        ("track blocks", "1 ok", "1 trouble"), ("track windows", "2", "10 s at a 5 s stride"), ("track hours", "0.01 h", "of the ok blocks"),
        ("arena blocks", "1 ok", "0 trouble"), ("arena windows", "2", "10 s at a 5 s stride"), ("arena hours", "0.01 h", "of the ok blocks")]
    assert app.tested_line(SHORT).startswith("verdicts at a 10 s window plus a 0.5 s horizon every 5 s")


def test_a_block_payload_carries_the_environment_the_spans_and_the_room_and_its_lanes_draw_runs_frames_trips_and_windows(built):
    track = blocks.payload_of(built, S1_TRACK)
    assert (track["kind"], track["rate_hz"], track["frame_start"], track["room"]) == ("track", 60, 2101, [1.8, 1.8])
    assert len(track["x"]) == track["n_frames"] == 1200 and track["one_light"] == [BACK_LOST] and track["heading_filled"] == [BACK_LOST]
    assert blocks.rate_of({"n_frames": 1100, "duration_s": 1100 / 60}) == 60 and 1100 / (1100 / 60) != 60
    assert [(r["run"], r["path_id"], r["clean"], r["first"], r["last"]) for r in track["runs"]] == [
        (1, 1, True, 99, 199), (2, 9, False, 299, 399), (3, 2, True, 499, 599)]
    assert [(t["trip"], t["partial"]) for t in track["trips"]] == [(1, True), (2, False), (3, True)]
    assert [p["phase"] for p in track["phases"]][:4] == ["dwell", "outbound", "dwell", "return"]
    walls, centerline, sites = track["environment_traces"]
    assert walls["line"] == blocks.WALL_LINE and None in walls["x"] and centerline["line"] == blocks.CENTERLINE
    assert sites["mode"] == "markers" and "start" in sites["hovertext"] and len(sites["x"]) == 5
    arena = blocks.payload_of(built, S1_ARENA)
    (ring,) = arena["environment_traces"]
    assert ring["x"][0] == ring["x"][-1] and len(ring["x"]) == 33 and arena["trips"] == [] and arena["runs"] == []
    figure = app.block_lanes_figure(track, SHORT)
    layout = figure["layout"]
    assert [layout[axis]["domain"] for axis in ("yaxis", "yaxis2", "yaxis3", "yaxis4")] == list(app.BLOCK_LANES.values())
    assert layout["xaxis"]["range"] == [0, 20.0] and layout["meta"] == S1_TRACK
    assert [a["text"] for a in layout["annotations"]] == ["runs", "frames (cm/s)", "trips", "windows"]
    by_axis = {axis: [t for t in figure["data"] if t["yaxis"] == axis] for axis in app.BLOCK_AXES.values()}
    assert [t["marker"]["color"] for t in by_axis["y"]] == [app.RUN_SHADES[s] for s in ("outbound", "return", "outbound")]
    assert [t["marker"]["pattern"]["shape"] for t in by_axis["y"]] == ["", app.DIRTY_PATTERN, ""]
    one_light, filled, held, speed = by_axis["y2"]
    assert one_light["base"] == [699 / 60] and filled["base"] == [699 / 60] and held["x"] == [] and speed["mode"] == "lines"
    assert [t["marker"]["pattern"]["shape"] for t in by_axis["y3"]] == [app.PARTIAL_PATTERN, "", app.PARTIAL_PATTERN]
    body, burn_in, horizon = by_axis["y4"]
    assert body["base"] == [1.0, 6.0] and body["x"] == [9.0, 9.0] and burn_in["base"] == [0.0, 5.0] and horizon["base"] == [10.0, 15.0]
    assert app.window_rows(SHORT) == 3 and body["y"] == [1 - 0.5 / 3, 1 - 1.5 / 3]
    ok, reason = windows.verdict(track, blocks.shares_for(built, track), SHORT)
    assert app.block_header(track, ok, reason) == f"{S1_TRACK}: session {S1}, track, automatic, 0.3 min, ok"


def test_save_settings_writes_the_yaml_at_windows_config_with_the_settings_the_manifest_facts_and_the_totals(built, tmp_path, monkeypatch):
    path = tmp_path / "configs" / "datasets" / "lab_blocks.yaml"
    monkeypatch.setattr(windows, "CONFIG", path)
    line = app.saved_settings(built, SHORT)
    read = windows.read_settings(path)
    assert line == f"saved {path} at {read['written_at']}"
    assert list(read) == ["settings", "processed_manifest_timestamp", "rules", "totals", "written_at"]
    assert read["settings"] == SHORT and read["processed_manifest_timestamp"] == trajectory.read_manifest(built)["run"]["timestamp"]
    assert read["totals"]["overall"] == {"blocks_ok": 2, "blocks_trouble": 1, "windows": 4, "hours_ok": 40 / 3600}


def test_without_a_manifest_the_blocks_tab_says_so_and_with_one_its_callbacks_form_no_cycle(transformed, processed, built):
    panel = app.blocks_panel(processed)
    assert panel.id == "blocks-panel" and panel.style == app.HIDDEN
    assert panel.children.children[1].children.startswith(f"no processed dataset under {processed}")
    assert "test.n_clicks" not in dependency_edges(app.make_app(transformed, processed))
    edges = dependency_edges(app.make_app(transformed, built))
    assert not any(reaches(edges, node, node) for node in edges)
    assert reaches(edges, "settings.data", "block-lanes.figure") and reaches(edges, "setting-window_s.value", "block-header.children")
    assert reaches(edges, "test.n_clicks", "blocks-table.children") and reaches(edges, "block-data.data", "block-map.figure")
    assert app.panel_styles("blocks") == (app.HIDDEN, app.HIDDEN, app.SHOWN)
    assert app.settings_of([None, 0, 2, 0, 20, 0, 1]) == {
        **windows.DEFAULTS, "burn_in_s": 2, "horizon_s": 0, "min_heading_measured": 0, "min_complete_trips": 1}
