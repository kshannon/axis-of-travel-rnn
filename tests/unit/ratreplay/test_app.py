"""
The app on the synthetic session: the layout builds, the callbacks form no cycle, the sessions list, the tabs and the greyed
actions, the lanes carry the epochs, runs, the processor's rules as toggled layers and the blocks under their display names,
the summary and block tiles, a save needs every block decided, a bad setup exits 2.
"""

import pytest
from dash import no_update

from process_lab_data import select
from ratreplay import __main__ as main, app, data

from .conftest import GAP, JUMP, LONG_HEADING_GAP, MARGINS, PAUSE, RATE_HZ, SESSION, SHORT_HEADING_GAP, STAMP

KNOBS = {"window_s": 10, "stride_s": 5}
ALL_LAYERS = list(app.LAYERS)


def dependency_edges(dash_app):
    """
    The callback graph as input prop to the set of output props of every callback registered, as the renderer sees it.
    """
    edges = {}
    for outputs, callback in dash_app.callback_map.items():
        targets = {output.split("@")[0] for output in outputs.strip(".").split("...")}
        for i in callback["inputs"]:
            edges.setdefault(f"{i['id']}.{i['property']}", set()).update(targets)
    return edges


def reaches(edges, node, target, path=()):
    """
    Whether following the edges from the node arrives at the target.
    """
    return any(nxt == target or (nxt not in path and reaches(edges, nxt, target, path + (nxt,)))
               for nxt in edges.get(node, ()))


def test_the_callbacks_form_no_cycle_so_an_edit_from_the_browser_comes_back_to_the_lanes(transformed, processed):
    edges = dependency_edges(app.make_app(transformed, processed))
    assert not any(reaches(edges, node, node) for node in edges)
    assert reaches(edges, "keys.data", "action.data") and reaches(edges, "action.data", "lanes.figure")
    assert reaches(edges, "action.data", "notice.data") and reaches(edges, "notice.data", "lanes.figure")
    assert reaches(edges, "layers.value", "lanes.figure")


def test_the_app_builds_with_the_unreviewed_session_selected_and_lists_it_once_saved(transformed, processed):
    assert app.make_app(transformed, processed).layout is not None
    sessions = data.list_sessions(transformed, processed)
    assert app.session_options(sessions) == [{"label": f"{SESSION} (standard)", "value": SESSION}]
    assert app.first_unreviewed(sessions, None) == SESSION
    assert app.totals_values(sessions) == [("sessions reviewed", "0 of 1", ""), ("blocks confirmed", "0", ""),
                                           ("arena confirmed", "0.0 h", ""), ("track confirmed", "0.0 h", "")]
    assert app.state_line(None, 0) == app.AUTOMATIC_LINE
    session = data.load_session(transformed, SESSION)
    review = data.review_of(session, [{"op": "drop", "frame": 1000}, {"op": "accept"}], "shaky camera", STAMP)
    data.write_review(processed, review)
    sessions = data.list_sessions(transformed, processed)
    assert app.session_options(sessions)[0]["label"].startswith(f"{app.REVIEWED_MARK}{SESSION} (standard), saved ")
    assert app.first_unreviewed(sessions, "none left") == "none left"
    assert app.state_line(review, 0) == f"saved {review['reviewed_at']} by {review['reviewed_by']}, 2 edits"
    assert app.stale_count(session, review) == 0 and app.stale_count({"session_id": SESSION, "error": "x"}, review) == 0
    assert app.totals_values(sessions)[:2] == [("sessions reviewed", "1 of 1", ""), ("blocks confirmed", "3", "")]
    totals, table_card = app.sessions_list(sessions)
    cells = [td.children for td in table_card.children[1].children[1].children[0].children]
    assert cells[:7] == ["NS14", "2015-01-01", "standard", "2", "4", "3", review["reviewed_by"]]
    assert cells[7].startswith(review["reviewed_at"]) and cells[8] == "shaky camera"
    assert cells[9].id == {"type": "load", "index": SESSION}


def test_the_tab_chosen_shows_its_panel_and_hides_the_other():
    assert app.panel_styles("replay") == (app.SHOWN, app.HIDDEN)
    assert app.panel_styles("sessions") == (app.HIDDEN, app.SHOWN)


def test_the_reduced_buttons_grey_the_block_actions_without_a_selection_new_block_without_marks_and_undo_without_edits():
    assert set(app.ACTIONS) == {"confirm all", "new block from marks", "start to cursor", "end to cursor", "split at cursor",
                                "remove block", "undo"}
    greyed = {name for name, off in app.disabled_actions(False, False, 0).items() if off}
    assert greyed == {"start to cursor", "end to cursor", "split at cursor", "remove block", "new block from marks", "undo"}
    assert {name for name, off in app.disabled_actions(True, False, 1).items() if off} == {"new block from marks"}
    assert not any(app.disabled_actions(True, True, 1).values())
    assert all(key in app.KEY_LABELS for key in ("Enter", " ", "Escape"))


def test_the_marks_line_says_what_is_marked():
    session = {"rate_hz": RATE_HZ}
    assert app.marks_line([None, None], session) == app.NO_MARKS_LINE
    assert app.marks_line([None, 4100], session) == "one mark at frame 4100, the other mark sets the range"
    assert app.marks_line([5000, 4100], session) == "marked frames 4100 to 5000, 15.0 s, n makes the block"


def test_runs_are_shaded_by_path_id():
    assert [app.run_shade(path) for path in (1, 4, 9, 10, 7)] == ["outbound", "outbound", "return", "return", "other"]


def test_blocks_are_named_through_the_session_in_time_order_while_their_ids_keep_the_processors_numbering(transformed):
    session = data.load_session(transformed, SESSION)
    blocks = app.for_browser(data.apply_edits(session["blocks"], [{"op": "split", "frame": 3000}], session), session, KNOBS)
    assert [b["name"] for b in blocks] == [f"block {i}" for i in range(1, 6)]
    assert [b["block_id"].rsplit("_", 2)[-2:] for b in blocks] == [
        ["arena", "01"], ["track", "01"], ["track", "02"], ["track", "03"], ["track", "04"]]
    assert [b["frame_start"] for b in blocks] == sorted(b["frame_start"] for b in blocks)


def test_the_lanes_draw_epochs_runs_the_rules_and_blocks_each_on_its_own_axis(transformed):
    session = data.load_session(transformed, SESSION)
    edits = [{"op": "split", "frame": 3000}, {"op": "drop", "frame": 7000}, {"op": "flag", "run": 2}]
    blocks = app.for_browser(data.apply_edits(session["blocks"], edits, session), session, KNOBS)
    figure = app.lanes_figure(session, blocks, data.flagged_runs(edits), KNOBS, ALL_LAYERS)
    layout = figure["layout"]
    assert [layout[axis]["domain"] for axis in ("yaxis", "yaxis2", "yaxis3", "yaxis4")] == list(app.LANES.values())
    assert layout["xaxis"]["range"] == [0, 9000 / RATE_HZ / 60] and layout["meta"] == SESSION
    assert [(a["text"], a["textangle"], a["yref"]) for a in layout["annotations"]] == [
        ("session", app.LABEL_ANGLE, "y domain"), ("runs", app.LABEL_ANGLE, "y2 domain"),
        ("frames (px/s)", app.LABEL_ANGLE, "y3 domain"), ("blocks", app.LABEL_ANGLE, "y4 domain")]
    assert [(s["type"], s["yref"], s["line"]) for s in layout["shapes"]] == [("line", "paper", app.SEPARATOR)] * 3
    by_axis = {axis: [t for t in figure["data"] if t["yaxis"] == axis] for axis in app.AXES.values()}
    assert [t["text"] for t in by_axis["y"]] == [["arena"], ["track"]]
    runs = by_axis["y2"]
    assert [t["marker"]["pattern"]["shape"] for t in runs] == ["", app.DIRTY_PATTERN, ""]
    assert [t["marker"]["color"] for t in runs] == [app.RUN_SHADES[s] for s in ("outbound", "other", "outbound")]
    assert runs[1]["marker"]["line"] == app.FLAG_OUTLINE and "run 2, path 7 other, dirty, flagged" in runs[1]["hovertext"][0]
    assert all("showlegend" in t and not t["showlegend"] for t in figure["data"]) and "legend" not in layout
    assert [t.get("name") for t in by_axis["y3"]] == ["gaps", "margins", None, "heading_filled", "heading_held", "heading_lost",
                                                      "pauses", "jumps"]
    gaps, margins, speed, filled, held, lost, pauses, jumps = by_axis["y3"]
    top = layout["yaxis3"]["range"][1]
    assert speed["mode"] == "lines" and len(speed["x"]) == 9000 // (RATE_HZ // app.SPEED_TRACE_HZ) and speed["line"] == app.SPEED_LINE
    assert gaps["base"] == [app.minutes(GAP[0], RATE_HZ)] and gaps["y"] == [top / 2] and gaps["width"] == top
    assert margins["base"] == [app.minutes(first, RATE_HZ) for first, _ in MARGINS] and margins["marker"]["color"] == app.MARGIN_COLOUR
    assert pauses["x"] == [app.minutes(PAUSE, RATE_HZ)] and "t jumps 60.0 s" in pauses["hovertext"][0]
    assert jumps["x"] == [app.minutes(JUMP, RATE_HZ)] * 2 + [None] and jumps["y"] == [0, top, None]
    assert filled["hovertext"] == [f"heading filled over 50 frames, {GAP[0]} to {GAP[1]}",
                                   f"heading filled over 60 frames, {SHORT_HEADING_GAP[0]} to {SHORT_HEADING_GAP[1]}"]
    assert lost["hovertext"] == [f"heading lost for 300 frames, {LONG_HEADING_GAP[0]} to {LONG_HEADING_GAP[1]}"]
    assert filled["marker"]["color"] == app.HEADING_FILLED_COLOUR and lost["marker"]["color"] == app.HEADING_LOST_COLOUR
    assert held["marker"]["color"] == app.HEADING_HELD_COLOUR and held["x"] == []
    assert [b["windows"] for b in blocks] == [5, 0, 2, 4, 3]
    *bars, glyphs = by_axis["y4"]
    assert [t["marker"]["color"] for t in bars] == [
        app.STATUS_COLOURS[b["status"]] if b["windows"] else app.TOO_SHORT_COLOUR for b in blocks]
    assert [t["text"] for t in bars] == [[f"block {i}"] for i in range(1, 6)]
    assert [t["customdata"] for t in bars] == [[b["block_id"]] for b in blocks]
    assert glyphs["text"] == ["☐", "✎", "✎", "☐", "✕"] and glyphs["customdata"] == [{"glyph": b["block_id"]} for b in blocks]
    assert glyphs["hovertext"][0] == "block 1, auto, click to confirm" and glyphs["hovertext"][4] == "block 5, dropped"
    assert "block 1 (" in bars[0]["hovertext"][0] and "5 windows, heading 0.0 s lost and 0.0 s filled, auto" in bars[0]["hovertext"][0]
    assert "4 windows, heading 0.0 s lost and 1.0 s filled, auto" in bars[3]["hovertext"][0]
    assert "heading 5.0 s lost and 0.0 s filled, dropped" in bars[4]["hovertext"][0]


def test_the_toggles_only_change_which_layers_are_visible(transformed):
    session = data.load_session(transformed, SESSION)
    blocks = app.for_browser(data.apply_edits(session["blocks"], [], session), session, KNOBS)
    everything = app.lanes_figure(session, blocks, [], KNOBS, ALL_LAYERS)
    some = app.lanes_figure(session, blocks, [], KNOBS, ["pauses", "heading_lost"])
    layered = [t for t in everything["data"] if "name" in t]
    assert [t["name"] for t in layered] == ["gaps", "margins", "heading_filled", "heading_held", "heading_lost", "pauses", "jumps"]
    assert all(t["visible"] for t in layered)
    assert [t["visible"] for t in some["data"] if "name" in t] == [False, False, False, False, True, True, False]
    assert [t for t in some["data"] if "name" not in t] == [t for t in everything["data"] if "name" not in t]


def test_a_block_too_short_for_one_window_is_greyed_and_the_summary_and_block_tiles_say_so(transformed):
    session = data.load_session(transformed, SESSION)
    knobs = {"window_s": 40, "stride_s": 10}
    blocks = app.for_browser(data.apply_edits(session["blocks"], [{"op": "confirm", "frame": 1000}], session), session, knobs)
    figure = app.lanes_figure(session, blocks, [], knobs, ALL_LAYERS)
    bars = [t for t in figure["data"] if t["yaxis"] == app.AXES["blocks"] and t["type"] == "bar"]
    assert [b["windows"] for b in blocks] == [0, 0, 0, 0]
    assert bars[1]["marker"] == {"color": app.TOO_SHORT_COLOUR,
                                 "pattern": {"shape": app.TOO_SHORT_PATTERN, "fgcolor": app.STATUS_COLOURS["auto"], "solidity": 0.5}}
    assert "too short for one 40 s window" in bars[0]["hovertext"][0]
    assert app.summary_values(session, blocks, knobs) == [
        ("automatic", "3", ""), ("confirmed", "1", ""), ("edited", "0", ""), ("removed", "0", ""),
        ("kept", "1.7 of 2.5 min", "68% of arena and track"), ("windows", "0", "40 s at a 10 s stride"),
        ("cuts", "3", "1 pauses, 1 jumps, 1 gaps"), ("heading", "5 s lost", "2 s filled")]
    assert app.block_facts(blocks[2], session, knobs) == [
        ("block", "block 3", f"{SESSION}_track_02"), ("epoch", "track", "triple_t"), ("lab frames", "4050 to 5700", ""),
        ("minutes", "0.46", "27.5 s"), ("runs", "1", ""), ("windows", "0", "too short for one 40 s window"),
        ("heading", "0.0 s lost", "1.0 s filled"), ("status", "auto", "")]
    tiles = app.tiles(app.summary_values(session, blocks, knobs))
    assert [t.children[0].children for t in tiles.children][:2] == ["automatic", "confirmed"]


def test_a_selected_block_zooms_to_its_range_plus_the_margin():
    block = {"frame_start": 2701, "frame_end": 3999}
    x0, x1 = 2700 / RATE_HZ / 60, 3999 / RATE_HZ / 60
    margin = app.ZOOM_MARGIN * (x1 - x0)
    assert app.zoom_range(block, RATE_HZ) == pytest.approx([x0 - margin, x1 + margin])


def test_an_edit_is_appended_without_its_counter_and_undo_takes_the_last_back():
    edits = app.edited([], {"op": "split", "frame": 3000, "n": 3})
    assert edits == [{"op": "split", "frame": 3000}]
    assert app.edited(edits, {"op": "undo", "n": 4}) == []


def test_a_new_block_over_a_gap_is_refused_and_a_clean_one_goes_through(transformed):
    session = data.load_session(transformed, SESSION)
    edits = [{"op": "drop", "frame": 5000}]
    assert app.refused(session, edits, {"op": "new", "frame_start": 3990, "frame_end": 4100}) == data.CROSSES_MESSAGE
    assert app.refused(session, edits, {"op": "new", "frame_start": 4100, "frame_end": 5000}) is None
    assert app.refused(session, edits, {"op": "split", "frame": 3000}) is None
    refused = app.acted(session, edits, {"op": "new", "frame_start": 3990, "frame_end": 4100, "n": 1})
    assert refused[0] is no_update and refused[1] == data.CROSSES_MESSAGE
    assert app.acted(session, edits, {"op": "new", "frame_start": 4100, "frame_end": 5000, "n": 2}) == (
        edits + [{"op": "new", "frame_start": 4100, "frame_end": 5000}], "")


def test_a_save_is_refused_while_a_block_is_auto_then_writes_the_review_and_overwrites_it(transformed, processed):
    session = data.load_session(transformed, SESSION)
    sessions, message = app.saved(transformed, processed, STAMP, session, [{"op": "confirm", "frame": 1000}], "")
    assert sessions is None and message == app.STILL_AUTO_MESSAGE
    assert data.read_review(processed, SESSION) is None
    sessions, message = app.saved(transformed, processed, STAMP, session, [{"op": "accept"}], "first")
    assert sessions[0]["reviewed"] and sessions[0]["n_confirmed"] == 4 and message.startswith("saved")
    first = data.read_review(processed, SESSION)
    assert first["notes"] == "first" and {b["status"] for b in first["blocks"]} == {"confirmed"}
    app.saved(transformed, processed, STAMP, session, [{"op": "accept"}, {"op": "drop", "frame": 1000}], "second")
    second = data.read_review(processed, SESSION)
    assert second["notes"] == "second" and [b["status"] for b in second["blocks"]][0] == "dropped"
    assert app.saved(transformed, processed, STAMP, {"session_id": SESSION, "error": "x"}, [], "") == (None, app.NOT_LOADED_MESSAGE)


def test_a_review_saved_under_other_rules_still_draws_and_the_state_line_counts_the_edits_skipped(transformed, processed, monkeypatch):
    session = data.load_session(transformed, SESSION)
    edits = [{"op": "drop", "frame": 5000}, {"op": "new", "frame_start": 4100, "frame_end": 5000},
             {"op": "move", "frame": 2790, "edge": "start", "at": 2701}, {"op": "accept"}]
    data.write_review(processed, data.review_of(session, edits, "", STAMP))
    monkeypatch.setattr(select, "PAUSE_MARGIN_SEC", 8.0)
    session, review = data.load_session(transformed, SESSION), data.read_review(processed, SESSION)
    assert [b["frame_start"] for b in session["blocks"]] == [481, 2881, 4050, 6481] and review["rules"] != data.rules()
    blocks = app.for_browser(data.apply_edits(session["blocks"], review["edits"], session), session, KNOBS)
    assert [(b["frame_start"], b["frame_end"], b["status"]) for b in blocks] == [
        (481, 1920, "confirmed"), (2881, 3999, "confirmed"), (4050, 5520, "dropped"), (4100, 5000, "edited"),
        (6481, 7520, "confirmed")]
    assert app.lanes_figure(session, blocks, [], KNOBS, ALL_LAYERS)["layout"]["meta"] == SESSION
    assert app.stale_count(session, review) == 1
    assert app.state_line(review, 1).endswith(", 4 edits" + app.STALE_LINE.format(n=1))


@pytest.mark.parametrize("config, missing", [
    ({"PROCESSED_LAB_DATA": "x"}, "TRANSFORMED_LAB_DATA"),
    ({"TRANSFORMED_LAB_DATA": "{tmp}", "PROCESSED_LAB_DATA": "x"}, "sessions.csv"),
    ({"TRANSFORMED_LAB_DATA": "{no_manifest}", "PROCESSED_LAB_DATA": "x"}, "manifest.json"),
    ({"TRANSFORMED_LAB_DATA": "{transformed}"}, "PROCESSED_LAB_DATA"),
])
def test_a_missing_folder_key_or_manifest_exits_2(transformed, tmp_path, capsys, config, missing):
    no_manifest = tmp_path / "no_manifest"
    no_manifest.mkdir()
    for name in ("sessions.csv", "epochs.csv", "runs.csv", "frames"):
        (no_manifest / name).mkdir()
    config = {key: value.format(tmp=tmp_path, transformed=transformed, no_manifest=no_manifest)
              for key, value in config.items()}
    with pytest.raises(SystemExit) as exit_:
        main.main([], config)
    assert exit_.value.code == 2 and missing in capsys.readouterr().err
