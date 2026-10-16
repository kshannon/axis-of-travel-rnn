"""
The Dash app: the two tabs as cards, the callbacks that load a session, apply its edits, fill the block card and save its review, and the clientside playback.
"""

import math
from datetime import datetime, timezone

import numpy as np
from dash import ALL, ClientsideFunction, Dash, Input, Output, State, ctx, dcc, html, no_update

from process_lab_data import select

from . import data

TITLE = "RatReplay"

# Tailwind from its CDN lays the page out, assets/replay.css adds what its utilities cannot (the fading message, the
# segmented control, the toggles). Nothing else leaves the machine: the data stays in the local page. The classes are
# named here once: the grey page behind white cards, the stat tiles, the three button styles with a key badge, the ?
# popovers.
TAILWIND = "https://cdn.tailwindcss.com"
PAGE = "min-h-screen bg-gray-100 p-4 font-sans text-base text-gray-900 flex flex-col gap-4"
HEADER = "flex items-center gap-6"
ROW = "flex flex-wrap items-stretch gap-4"
PANEL = "flex flex-col gap-4"
CARD = "rounded-lg border border-gray-200 bg-white p-4 shadow-sm flex flex-col gap-3"
CARD_TITLE = "text-xs font-semibold uppercase tracking-wide text-gray-500"
TILES = "flex flex-wrap gap-2"
TILE = "rounded-md border border-gray-100 bg-gray-50 px-3 py-2 min-w-[6rem]"
TILE_LABEL = "text-[11px] uppercase tracking-wide text-gray-500"
TILE_VALUE = "text-base font-semibold tabular-nums"
TILE_NOTE = "text-xs text-gray-500"
BUTTON = "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
PRIMARY = f"{BUTTON} bg-blue-600 font-medium text-white hover:bg-blue-700"
NEUTRAL = f"{BUTTON} border border-gray-300 bg-white text-gray-800 hover:bg-gray-50"
DESTRUCTIVE = f"{BUTTON} border border-red-300 bg-white text-red-700 hover:bg-red-50"
BADGE = "rounded border border-gray-300 bg-gray-100 px-1 font-mono text-[10px] text-gray-600"
HELP_BUTTON = "rounded-full border px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100"
POPOVER = "hidden absolute z-10 mt-1 w-[28rem] rounded-md border bg-white p-3 text-sm leading-6 shadow-lg"
BUTTONS = "flex flex-wrap items-center gap-2"
FOOTER = "flex flex-wrap items-center gap-x-6 gap-y-2"
GROUP = "flex flex-col gap-1"
GROUP_LABEL = "flex items-center gap-2 text-xs text-gray-500"
NUMBER_INPUT = "w-16 rounded border px-1 text-sm"
TEXT = "text-sm"
MUTED = "text-sm text-gray-500"
CAPTION = "text-sm text-gray-600"
MESSAGE = "message rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm text-amber-900"
NOTES = "flex-1 min-h-[4rem] rounded-md border p-2 text-sm"
TABLE = "w-full border-collapse text-sm"
CELL = "px-2 py-1.5 whitespace-nowrap"
HEAD_CELL = "px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
MAP_HEIGHT = "52vh"
LANES_HEIGHT_PX = 560

# The two tabs: both panels stay mounted, since the clientside tick needs its outputs present, and the one not chosen
# gets display none.
TABS = {"replay": "Replay", "sessions": "Sessions"}
HIDDEN = {"display": "none"}
SHOWN = {}

# The sessions table and the dropdown's mark for a reviewed session.
REVIEWED_MARK = "✓ "
TABLE_COLUMNS = ("rat", "date", "protocol", "minutes", "automatic blocks", "confirmed blocks", "reviewed by",
                 "reviewed at", "notes", "")
NOTES_EXCERPT = 60

# The state line in the Session card: the automatic blocks, a saved review (with how many of its edits no longer
# apply, when the processor's rules changed since the save), or the automatic blocks after a reset while a review file
# still sits on disk.
AUTOMATIC_LINE = "automatic"
RESET_LINE = "automatic (saved review on disk not loaded)"
STALE_LINE = ", {n} of them no longer apply under the current rules and were skipped"

# Playback: the speed slider's stops, the browser interval that draws the frame the wall clock asks for, the live tiles
# the browser fills, and the occupancy views beside the epochs by name.
SPEEDS = (0.25, 0.5, 1, 2, 4, 8)
INTERVAL_MS = 1000 // 30
LIVE_TILES = (("time", "time"), ("lab frame", "frame"), ("speed", "speed-now"), ("lights", "lights"), ("run", "run-now"))
OCCUPANCY_VIEWS = {"current": "current epoch", "all": "all"}

# The windows calculator's defaults, display only: the training config owns the real values.
WINDOW_S = 40
STRIDE_S = 10

# The actions in their groups, each button carrying the key the browser maps to the same operation, its style and a
# one-line help. The block actions are greyed without a selected block, new block without both marks, undo without
# edits. The badge shows the key, these three spelled out. Confirming one block, marking a range and flagging a run
# have keys and clicks on the lanes, no button: the hint under the lanes says so.
ACTION_GROUPS = (
    ("review", "confirm all keeps every block still automatic. One block is confirmed by a click on its glyph on the "
               "bar, or Enter once it is selected, and the same again takes it back. A save needs every block confirmed, "
               "edited or removed.",
     (("confirm all", "a", PRIMARY),)),
    ("range", "i and o mark a range at the cursor, new block makes a block of it. The range cannot cross a pause, a "
              f"gap, a jump or an epoch bound, must last {select.MIN_BLOCK_S:g} s and stay clear of the blocks kept.",
     (("new block from marks", "n", NEUTRAL),)),
    ("edit", "start and end to cursor move the selected block's edge to the cursor, snapping to a run edge within "
             f"{data.SNAP_S:g} s and never crossing a cut. split cuts the selected block in two at the cursor. remove "
             "drops the block, or takes a removed block back.",
     (("start to cursor", ",", NEUTRAL), ("end to cursor", ".", NEUTRAL), ("split at cursor", "s", NEUTRAL),
      ("remove block", "d", DESTRUCTIVE))),
    ("undo", "undo takes the last edit back, one at a time.", (("undo", "z", NEUTRAL),)),
)
ACTIONS = tuple(name for _, _, buttons in ACTION_GROUPS for name, _, _ in buttons)
BLOCK_ACTIONS = ("start to cursor", "end to cursor", "split at cursor", "remove block")
MARKS_ACTIONS = ("new block from marks",)
EDITS_ACTIONS = ("undo",)
KEY_LABELS = {"Enter": "enter", " ": "space", "Escape": "esc"}
BLOCK_PLACEHOLDER = "no block selected, click a block bar"
NO_MARKS_LINE = "no range marked"
LANES_HINT = ("i and o mark a range, n or the button makes a block. Click a block to select it, its glyph to confirm "
              "it. f or a right click on a run bar flags the run.")

# The messages a save leaves in the message area when nothing was written.
NOT_LOADED_MESSAGE = "nothing to save, the session did not load"
STILL_AUTO_MESSAGE = "some blocks are still auto: confirm them (the glyph, Enter, or a for all) before saving"

# The lanes: four bands of one figure sharing the time axis in minutes of recording (a pause is a mark, not a stretch),
# each the y axis named here over its share of the height, the runs and blocks lanes the tallest, a thin separator in
# each gap between them and the lane's name as an angled label at the left. Bars sit at y 0.5 of their lane. A
# selected block zooms the axis to the block plus this fraction of its length on each side. The speed trace is the mean
# over bins of this rate, thin and grey, and the frames lane shows speeds up to this percentile. Runs are shaded by the
# lab's path id, outbound or return. A block too short for one window is grey with its status colour dotted through,
# its glyph a marker above its name that a click toggles between auto and confirmed.
MINUTE_S = 60
LANES = {"session": (0.95, 1.0), "runs": (0.66, 0.92), "frames": (0.36, 0.60), "blocks": (0.0, 0.30)}
AXES = {"session": "y", "runs": "y2", "frames": "y3", "blocks": "y4"}
LABEL_ANGLE = -30
LABEL_SHIFT_PX = -56
FONT_SIZE = 13
SEPARATOR = {"color": "#d1d5db", "width": 1}
BAR_HEIGHT = 0.8
ZOOM_MARGIN = 0.05
SPEED_TRACE_HZ = 4
SPEED_SCALE_PERCENTILE = 95
EPOCH_COLOURS = {"arena": "#aec7e8", "track": "#98df8a", "other": "#d9d9d9"}
OUTBOUND_PATHS = (1, 2, 3, 4)
RETURN_PATHS = (9, 10)
RUN_SHADES = {"outbound": "#3f78ad", "return": "#9dbfdc", "other": "#bdbdbd"}
DIRTY_PATTERN = "/"
FLAG_OUTLINE = {"color": "#d62728", "width": 2}
SPEED_LINE = {"color": "#9ca3af", "width": 1}
STATUS_COLOURS = {"auto": "#9ecae1", "confirmed": "#2ca02c", "edited": "#ff7f0e", "dropped": "#d9d9d9"}
STATUS_GLYPHS = {"auto": "☐", "confirmed": "☑", "edited": "✎", "dropped": "✕"}
GLYPH_Y = 0.74
GLYPH_MARKER = {"symbol": "square", "size": 20, "color": "white", "line": {"color": "#6b7280", "width": 1}}
GLYPH_FONT = {"size": 15, "color": "#111827"}
TOO_SHORT_COLOUR = "#e5e7eb"
TOO_SHORT_PATTERN = "."

# The frames lane draws the processor's rules, each a display layer the Timeline footer toggles: the margins trimmed
# as black bands, the cut points red (the pauses as ticks at the top, the jumps as lines across the lane, so a jump
# shows through the black band around it), the both-lights gaps light grey, the heading still lost after the fill as
# an orange band at the bottom, the heading held while the rat was still a middle orange and the heading filled a
# lighter orange beside them. Every layer is on to start.
LAYERS = {"margins": "margins", "jumps": "jumps", "gaps": "gaps", "heading_lost": "heading loss",
          "heading_held": "heading held", "heading_filled": "heading filled", "pauses": "pauses"}
MARGIN_COLOUR = "#111827"
JUMP_LINE = {"color": "#d62728", "width": 2}
GAP_COLOUR = "rgba(0,0,0,0.12)"
PAUSE_MARKER = {"symbol": "line-ns", "size": 12, "color": "#d62728", "line": {"color": "#d62728", "width": 2}}
TICKS_Y = 0.94
HEADING_LOST_COLOUR = "#f97316"
HEADING_HELD_COLOUR = "#fb923c"
HEADING_FILLED_COLOUR = "#fdba74"
HEADING_Y = 0.05
HEADING_HEIGHT = 0.1


def make_app(transformed, processed):
    """
    The app over the converter's folder and the processed root the review files go under.
    """
    sessions = data.list_sessions(transformed, processed)
    stamp = data.manifest_timestamp(transformed)
    app = Dash(__name__, title=TITLE, external_scripts=[TAILWIND])
    app.layout = layout(sessions)

    @app.callback(
        Output("session-data", "data"), Output("edits", "data"), Output("session-line", "children"),
        Output("state-line", "children"), Output("facts", "children"), Output("notes", "value"),
        Output("notice", "data"), Output("map-caption", "children"), Output("lanes-caption", "children"),
        Output("occupancy", "options"), Output("occupancy", "value"),
        Input("session", "value"), Input("action", "data"), Input("reset", "n_clicks"),
        State("edits", "data"), State("session-data", "data"))
    def load_or_edit(session_id, action, n_reset, edits, session):
        """
        Load the session chosen, apply an action from the browser to the edits, or reset the edits to the automatic blocks.
        """
        if ctx.triggered_id == "action":
            edits, message = acted(session, edits, action)
            notice = {"text": message, "n": action["n"]} if message else no_update
            return no_update, edits, no_update, no_update, no_update, no_update, notice, no_update, no_update, no_update, no_update
        if ctx.triggered_id == "reset":
            line = RESET_LINE if data.read_review(processed, session["session_id"]) else AUTOMATIC_LINE
            return no_update, [], no_update, line, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        session = session_payload(transformed, session_id)
        review = data.read_review(processed, session_id)
        loaded = review or {"edits": [], "notes": ""}
        return (session, loaded["edits"], session_line(session), state_line(review, stale_count(session, review)), facts(session, stamp),
                loaded["notes"], no_update, map_caption(session_id), lanes_caption(session), occupancy_options(session),
                "current")

    @app.callback(Output("blocks", "data"), Output("lanes-base", "data"), Output("summary", "children"),
                  Input("edits", "data"), Input("session-data", "data"), Input("knobs", "data"), Input("layers", "value"))
    def redraw(edits, session, knobs, layers):
        """
        The blocks as they stand after the edits, the lanes drawn over them with the layers chosen, and the summary tiles.
        """
        if "error" in session:
            return [], error_figure(session), ""
        blocks = for_browser(data.apply_edits(session["blocks"], edits, session), session, knobs)
        return (blocks, lanes_figure(session, blocks, data.flagged_runs(edits), knobs, layers),
                tiles(summary_values(session, blocks, knobs)))

    @app.callback(Output("block-facts", "children"), Output({"type": "act", "index": ALL}, "disabled"),
                  Input("ui", "data"), Input("blocks", "data"), State("edits", "data"), State("session-data", "data"),
                  State("knobs", "data"))
    def fill_block_card(ui, blocks, edits, session, knobs):
        """
        The Block card for the block the browser selected, the marks line and the greyed actions, after a selection, a mark or an edit.
        """
        block = next((b for b in blocks if b["block_id"] == ui["selected"]), None)
        marked = None not in ui["marks"]
        disabled = disabled_actions(block is not None, marked, len(edits))
        card_body = tiles(block_facts(block, session, knobs)) if block else html.Div(BLOCK_PLACEHOLDER, className=MUTED)
        marks = html.Div(marks_line(ui["marks"], session), className=MUTED)
        return [card_body, marks], [disabled[output["id"]["index"]] for output in ctx.outputs_list[1]]

    @app.callback(
        Output("session", "options"), Output("session", "value"), Output("notice", "data", allow_duplicate=True),
        Output("tabs", "value"), Output("sessions-list", "children"),
        Input("save", "n_clicks"), Input({"type": "load", "index": ALL}, "n_clicks"),
        State("session-data", "data"), State("edits", "data"), State("notes", "value"), prevent_initial_call=True)
    def save_or_load(n_save, n_loads, session, edits, notes):
        """
        Save the session's review and open the next unreviewed one, or open the session whose load button was pressed.
        """
        if ctx.triggered_id != "save":
            return no_update, ctx.triggered_id["index"], no_update, "replay", no_update
        sessions, message = saved(transformed, processed, stamp, session, edits, notes)
        notice = {"text": message, "n": n_save}
        if sessions is None:
            return no_update, no_update, notice, no_update, no_update
        return (session_options(sessions), first_unreviewed(sessions, session["session_id"]), notice, no_update,
                sessions_list(sessions))

    @app.callback(Output("replay-panel", "style"), Output("sessions-panel", "style"), Input("tabs", "value"))
    def show_tab(tab):
        """
        Show the panel of the tab chosen and hide the other.
        """
        return panel_styles(tab)

    app.clientside_callback(
        f"(window_s, stride_s) => ({{window_s: window_s > 0 ? window_s : {WINDOW_S}, "
        f"stride_s: stride_s > 0 ? stride_s : {STRIDE_S}}})",
        Output("knobs", "data"), Input("window-s", "value"), Input("stride-s", "value"))
    app.clientside_callback(
        ClientsideFunction("replay", "act"), Output("action", "data"), Input("keys", "data"), prevent_initial_call=True)
    app.clientside_callback(
        ClientsideFunction("replay", "tick"),
        Output("map", "figure"), Output("lanes", "figure"), *[Output(value_id, "children") for _, value_id in LIVE_TILES],
        Output("play-label", "children"), Output("interval", "disabled"), Output("ui", "data"),
        Input("interval", "n_intervals"), Input("keys", "data"), Input("lanes", "clickData"), Input("speed", "value"),
        Input("occupancy", "value"), Input("knobs", "data"), Input("session-data", "data"),
        Input("lanes-base", "data"), Input("blocks", "data"), Input("notice", "data"))
    return app


def panel_styles(tab):
    """
    The styles of the replay and sessions panels: the tab chosen shown, the other display none.
    """
    return SHOWN if tab == "replay" else HIDDEN, SHOWN if tab == "sessions" else HIDDEN


def disabled_actions(selected, marked, n_edits):
    """
    Which action is greyed: the block actions without a selected block, new block without both marks, undo without edits.
    """
    return {name: (name in BLOCK_ACTIONS and not selected) or (name in MARKS_ACTIONS and not marked)
            or (name in EDITS_ACTIONS and not n_edits) for name in ACTIONS}


def refused(session, edits, action):
    """
    The message refusing a new block from the browser, or None for every action that goes through.
    """
    if action["op"] != "new":
        return None
    return data.refusal(data.apply_edits(session["blocks"], edits, session), action, session)


def acted(session, edits, action):
    """
    The edits and the message after an action from the browser: a refused new block leaves the edits as they are.
    """
    problem = refused(session, edits, action)
    if problem:
        return no_update, problem
    return edited(edits, action), ""


def saved(transformed, processed, stamp, session, edits, notes):
    """
    The sessions listed again and the message after a save, or None and the message saying why nothing was written.
    """
    if "error" in session:
        return None, NOT_LOADED_MESSAGE
    review = data.review_of(session, edits, notes or "", stamp)
    if any(b["status"] == "auto" for b in review["blocks"]):
        return None, STILL_AUTO_MESSAGE
    path = data.write_review(processed, review)
    data.AUTOMATIC_COUNTS.pop(session["session_id"], None)
    return data.list_sessions(transformed, processed), f"saved {path.name} at {review['reviewed_at']}"


def edited(edits, action):
    """
    The edits after an action from the browser: undo takes the last one back, anything else is appended without its counter.
    """
    if action["op"] == "undo":
        return edits[:-1]
    return edits + [{key: value for key, value in action.items() if key != "n"}]


def session_payload(transformed, session_id):
    """
    What the browser needs for one session, or the error that stopped the load.
    """
    try:
        return data.load_session(transformed, session_id)
    except Exception as error:
        return {"session_id": session_id, "error": f"{type(error).__name__}: {error}"}


def first_unreviewed(sessions, fallback):
    """
    The first session without a review file, or the fallback when every session has one.
    """
    return next((s["session_id"] for s in sessions if not s["reviewed"]), fallback)


def session_options(sessions):
    """
    The dropdown's options in the list's order, each with its protocol and, when reviewed, the mark and the time since the save.
    """
    now = datetime.now(timezone.utc)
    return [{"label": f"{REVIEWED_MARK}{s['session_id']} ({s['protocol']}), saved {data.time_since(s['reviewed_at'], now)}"
             if s["reviewed"] else f"{s['session_id']} ({s['protocol']})", "value": s["session_id"]} for s in sessions]


def card(title, children, className=""):
    """
    A white card with a small uppercase title over its children.
    """
    return html.Div([html.Div(title, className=CARD_TITLE), *children], className=f"{CARD} {className}".strip())


def tile(label, value, note):
    """
    One stat tile: a small label over a value, with a note under it.
    """
    return html.Div([html.Div(label, className=TILE_LABEL), html.Div(value, className=TILE_VALUE),
                     html.Div(note, className=TILE_NOTE)], className=TILE)


def live_tile(label, value_id):
    """
    One stat tile whose value the browser fills every frame.
    """
    return html.Div([html.Div(label, className=TILE_LABEL), html.Div("", id=value_id, className=TILE_VALUE)], className=TILE)


def tiles(values):
    """
    A row of stat tiles from (label, value, note) triples.
    """
    return html.Div([tile(*value) for value in values], className=TILES)


def help_popover(popover_id, children):
    """
    A ? button that toggles the popover beside it, holding these children.
    """
    return html.Div([html.Button("?", className=HELP_BUTTON, **{"data-toggle": popover_id}),
                     html.Div(children, id=popover_id, className=POPOVER)], className="relative inline-block")


def key_button(name, key, style, **props):
    """
    A button for an action, its key as a small badge, carrying the key the browser maps to the action.
    """
    return html.Button([name, html.Kbd(KEY_LABELS.get(key, key), className=BADGE)], className=style,
                       **{"data-key": key}, **props)


def totals_values(sessions):
    """
    The tiles above the sessions table: sessions reviewed of all, blocks confirmed, hours of confirmed block time per epoch kind.
    """
    reviewed = [s for s in sessions if s["reviewed"]]
    return [("sessions reviewed", f"{len(reviewed)} of {len(sessions)}", ""),
            ("blocks confirmed", str(sum(s["n_confirmed"] for s in reviewed)), ""),
            *[(f"{epoch} confirmed", f"{sum(s['confirmed_s'][epoch] for s in reviewed) / 3600:.1f} h", "")
              for epoch in select.EPOCHS]]


def session_row(s, now):
    """
    One row of the sessions table with its load button.
    """
    reviewed_at = f"{s['reviewed_at']} ({data.time_since(s['reviewed_at'], now)})" if s["reviewed"] else ""
    cells = [s["subject_id"], s["date"], s["protocol"], f"{s['n_frames'] / s['rate_hz'] / MINUTE_S:.0f}", s["n_automatic"],
             s["n_confirmed"] if s["reviewed"] else "", s["reviewed_by"] or "", reviewed_at, s["notes"][:NOTES_EXCERPT]]
    button = html.Button("load", id={"type": "load", "index": s["session_id"]}, n_clicks=0, className=NEUTRAL)
    return html.Tr([html.Td(str(cell), className=CELL) for cell in cells] + [html.Td(button, className=CELL)],
                   title=s["session_id"], className="border-t hover:bg-gray-50")


def sessions_list(sessions):
    """
    The Sessions tab's content: the totals tiles and the table in a card, unreviewed first then the oldest review first.
    """
    now = datetime.now(timezone.utc)
    head = html.Thead(html.Tr([html.Th(name, className=HEAD_CELL) for name in TABLE_COLUMNS]))
    table = html.Table([head, html.Tbody([session_row(s, now) for s in sessions])], className=TABLE)
    return [tiles(totals_values(sessions)), card("Sessions", [table])]


def minutes(frame, rate_hz):
    """
    A lab frame as minutes of recording along the lanes.
    """
    return (frame - 1) / rate_hz / MINUTE_S


def degrees(radians):
    """
    Radians as a rounded degree string.
    """
    return f"{math.degrees(radians):.0f} deg"


def runs_in(block, session):
    """
    How many runs start inside the block.
    """
    return sum(1 for r in session["runs"] if block["frame_start"] <= r["frame_start"] <= block["frame_end"])


def run_shade(path_id):
    """
    Which shade a run takes from its path id: outbound, return or other.
    """
    if path_id in OUTBOUND_PATHS:
        return "outbound"
    return "return" if path_id in RETURN_PATHS else "other"


def session_line(session):
    """
    The Session card's line under the dropdown: the rat, the date and the protocol, or the error that stopped the load.
    """
    if "error" in session:
        return html.Span(f"{session['session_id']} failed to load: {session['error']}", className="text-red-700")
    return f"rat {session['subject_id']}, {session['date']}, {session['protocol']}"


def stale_count(session, review):
    """
    How many of a saved review's edits no longer apply to the session's automatic blocks, 0 without a review or a loaded session.
    """
    if review is None or "error" in session:
        return 0
    return len(data.replayed(session["blocks"], review["edits"], session)[1])


def state_line(review, n_stale):
    """
    Which state is on screen after a load: the automatic blocks, or the saved review with its edit count and the edits skipped.
    """
    if review is None:
        return AUTOMATIC_LINE
    line = f"saved {review['reviewed_at']} by {review['reviewed_by']}, {len(review['edits'])} edits"
    return line + (STALE_LINE.format(n=n_stale) if n_stale else "")


def marks_line(marks, session):
    """
    The Block card's line on the marked range: no mark, one mark waiting for the other, or both with the length in seconds.
    """
    if marks == [None, None]:
        return NO_MARKS_LINE
    if None in marks:
        return f"one mark at frame {next(m for m in marks if m is not None)}, the other mark sets the range"
    first, last = sorted(marks)
    return f"marked frames {first} to {last}, {(last - first + 1) / session['rate_hz']:.1f} s, n makes the block"


def occupancy_options(session):
    """
    The occupancy control's options: the current epoch, all, and each of the session's epochs by name.
    """
    names = [e["epoch"] for e in session.get("epochs", [])]
    return [{"label": label, "value": value} for value, label in OCCUPANCY_VIEWS.items()] + \
        [{"label": name, "value": name} for name in names]


def facts(session, stamp):
    """
    The ? popover's facts: the group, the epochs, the runs, the cut points, the heading fill, the LED offset and the converter run.
    """
    if "error" in session:
        return html.Div(session["error"], className="text-red-700")
    epochs = ", ".join(f"{e['epoch']} {e['duration_s'] / MINUTE_S:.1f} min (frames {e['frame_start']} to {e['frame_end']})"
                       for e in session["epochs"])
    cuts, heading, offset = session["cuts"], data.heading_in(session, 1, session["n_frames"]), session["led_offset"]
    lines = [("group", session["group"]), ("epochs", epochs),
             ("runs", f"{len(session['runs'])}, {sum(1 for r in session['runs'] if r['clean'])} clean"),
             ("cuts", f"{len(cuts['pauses'])} pauses, {len(cuts['jumps'])} jumps over {select.JUMP_PX:g} px, "
                      f"{len(cuts['gaps'])} gaps, {len(cuts['margins'])} margins of {select.PAUSE_MARGIN_SEC:g} s trimmed"),
             ("heading", f"{heading['heading_filled_s']:.1f} s filled over gaps up to {select.HEADING_FILL_SEC:g} s, "
                         f"{heading['heading_lost_s']:.1f} s still lost"),
             ("LED offset", f"{degrees(offset['rad'])}, concentration {offset['r']:.2f}, taken off the LED axis to give "
                            "the heading arrow"),
             ("converter run", stamp)]
    return [html.Div([html.Span(f"{name}: ", className="text-gray-500"), html.Span(str(value))]) for name, value in lines]


def summary_values(session, blocks, knobs):
    """
    The Summary card's tiles as (label, value, note): blocks by status, minutes kept and percent, windows at the knobs, cuts, heading.
    """
    s = data.summary(session, blocks, knobs["window_s"], knobs["stride_s"])
    st, cuts = s["statuses"], s["cuts"]
    return [("automatic", str(st["auto"]), ""), ("confirmed", str(st["confirmed"]), ""),
            ("edited", str(st["edited"]), ""), ("removed", str(st["dropped"]), ""),
            ("kept", f"{s['kept_s'] / MINUTE_S:.1f} of {s['epoch_s'] / MINUTE_S:.1f} min",
             f"{100 * s['kept_s'] / s['epoch_s']:.0f}% of arena and track"),
            ("windows", str(s["windows"]), f"{knobs['window_s']:g} s at a {knobs['stride_s']:g} s stride"),
            ("cuts", str(cuts["pauses"] + cuts["jumps"] + cuts["gaps"]),
             f"{cuts['pauses']} pauses, {cuts['jumps']} jumps, {cuts['gaps']} gaps"),
            ("heading", f"{s['heading_lost_s']:.0f} s lost", f"{s['heading_filled_s']:.0f} s filled")]


def block_facts(block, session, knobs):
    """
    The Block card's tiles as (label, value, note): name and id, epoch, lab frames, minutes, runs, windows, heading, status.
    """
    seconds = data.length_s(block, session["rate_hz"])
    windows = f"{knobs['window_s']:g} s at a {knobs['stride_s']:g} s stride" if block["windows"] else \
        f"too short for one {knobs['window_s']:g} s window"
    return [("block", block["name"], block["block_id"]), ("epoch", block["epoch"], block["environment"]),
            ("lab frames", f"{block['frame_start']} to {block['frame_end']}", ""),
            ("minutes", f"{seconds / MINUTE_S:.2f}", f"{seconds:.1f} s"), ("runs", str(runs_in(block, session)), ""),
            ("windows", str(block["windows"]), windows),
            ("heading", f"{block['heading_lost_s']:.1f} s lost", f"{block['heading_filled_s']:.1f} s filled"),
            ("status", block["status"], block["note"])]


def map_caption(session_id):
    """
    The line under the map: how to read it and which session it shows.
    """
    return (f"Session {session_id}. Grey shading is where the animal spent time in the epoch chosen under occupancy, "
            "the current epoch by default (log occupancy, darker is more). The epochs are drawn apart because the arena, "
            "the track and a rotated track overlap in the camera frame. The dots are the last 2 s of the path at 20 Hz "
            "coloured by speed, the large red dot the current position from the lab's mashup light in camera pixels "
            "with y down, the red arrow the corrected heading after the processor's fill, the LED axis minus the "
            "session's offset (in the Session card's ? popover). The thin grey line is the path of the selected block.")


def lanes_caption(session):
    """
    The line under the lanes: how to read them, how the automatic blocks were cut, and the ? popover with the constants.
    """
    if "error" in session:
        return ""
    max_gap_s = session["max_gap"] / session["rate_hz"]
    details = [
        f"A pause is a step in t over {select.PAUSE_STEP_S:g} s, where the lab stopped the camera.",
        f"A gap is {select.GAP_LIGHTS} LEDs lost for more than the session's max_gap of {session['max_gap']} frames "
        f"({max_gap_s:g} s). A shorter loss was filled by the lab and is not a cut. Position is never interpolated.",
        f"A jump is the position moving over {select.JUMP_PX:g} px in one frame, a tracking teleport.",
        f"A block is cut at every pause, jump, gap and epoch bound, {select.PAUSE_MARGIN_SEC:g} s is trimmed on each side "
        f"of a pause, a jump and an epoch bound, and a block under {select.MIN_BLOCK_S:g} s is dropped.",
        f"Heading never cuts: a loss up to {select.HEADING_FILL_SEC:g} s is filled along the shortest arc and flagged, "
        f"a longer one is held at the last heading while the rat stays under {select.RUNNING_FLOOR_M_PER_S * 100:g} cm/s throughout "
        "(the head in a reward well) and flagged, and any other stays NaN.",
        "The cuts, margins and the fill come from the processor's own functions, process_lab_data.select, so a confirmed "
        "block is the block the processor builds.",
        "The toggles only change what is drawn, never what is computed.",
        "The windows count is display only: a window of the length set is laid at the block's start and moved by the "
        "stride while it fits. The training config owns the real values.",
    ]
    return [
        html.Span(f"Session {session['session_id']}: the epochs, the lab's runs (dark blue outbound, paths 1 to 4, light "
                  "blue return, paths 9 and 10, grey any other path, hatched when dirty, outlined red when flagged), the "
                  "frames (speed in px per s as the grey trace, black bands the margins trimmed, red ticks the pauses, "
                  "red lines the jumps, grey the gaps with both LEDs lost, the orange band at the bottom heading still "
                  "lost after the fill, the middle orange heading held while still, the lighter orange heading filled) "
                  "and the blocks numbered through the session "
                  "and coloured by status (auto blue, confirmed green, edited orange, removed grey). A block too short "
                  "for one window is grey with its status dotted through. Click a block to select it: it gets a dark "
                  "outline, lines up to the frames it covers, its first windows as faint bars and the Block card. Click "
                  "its glyph to confirm it. "),
        help_popover("cuts-help", [html.P(line) for line in details]),
    ]


def zoom_range(block, rate_hz):
    """
    The x range in minutes a selected block zooms the lanes to: the block plus ZOOM_MARGIN of its length each side.
    """
    x0, x1 = minutes(block["frame_start"], rate_hz), minutes(block["frame_end"] + 1, rate_hz)
    margin = ZOOM_MARGIN * (x1 - x0)
    return [x0 - margin, x1 + margin]


def for_browser(blocks, session, knobs):
    """
    The blocks for the browser in time order, each with its display name, the x range it zooms to, its windows at the knobs and its heading seconds.
    """
    return [{**b, "name": f"block {i}", "zoom": zoom_range(b, session["rate_hz"]),
             "windows": data.windows_in(data.length_s(b, session["rate_hz"]), knobs["window_s"], knobs["stride_s"]),
             **data.heading_in(session, b["frame_start"], b["frame_end"])} for i, b in enumerate(blocks, 1)]


def bar(frame_start, frame_end, lane, rate_hz, marker, **extra):
    """
    One horizontal bar of a lane from one lab frame to another.
    """
    return {"type": "bar", "orientation": "h", "y": [0.5], "base": [minutes(frame_start, rate_hz)],
            "x": [(frame_end - frame_start + 1) / rate_hz / MINUTE_S], "width": BAR_HEIGHT, "marker": marker,
            "yaxis": AXES[lane], "hovertemplate": "%{hovertext}<extra></extra>", "showlegend": False, **extra}


def speed_trace(session):
    """
    The frames lane's speed trace: the mean speed over bins of SPEED_TRACE_HZ, with no value where no frame was tracked.
    """
    rate, size = session["rate_hz"], session["rate_hz"] // SPEED_TRACE_HZ
    speed = np.array(session["speed"], dtype=float)
    n_bins = math.ceil(len(speed) / size)
    padded = np.full(n_bins * size, np.nan)
    padded[:len(speed)] = speed
    valid = np.isfinite(padded).reshape(n_bins, size)
    counts = valid.sum(axis=1)
    sums = np.where(valid, padded.reshape(n_bins, size), 0).sum(axis=1)
    means = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
    centres = [minutes(i * size + 1 + size / 2, rate) for i in range(n_bins)]
    return {"type": "scatter", "mode": "lines", "x": centres, "y": data.floats(means), "line": SPEED_LINE,
            "yaxis": AXES["frames"], "connectgaps": False, "showlegend": False,
            "hovertemplate": "%{y:.0f} px/s<extra></extra>"}


def markers(frames, y, marker, hovertext, rate_hz):
    """
    One marker per lab frame at a height of the frames lane, each with its hover text.
    """
    return {"type": "scatter", "mode": "markers", "x": [minutes(f, rate_hz) for f in frames], "y": [y] * len(frames),
            "marker": marker, "yaxis": AXES["frames"], "hovertext": hovertext,
            "hovertemplate": "%{hovertext}<extra></extra>", "showlegend": False}


def verticals(frames, top, line, hovertext, rate_hz):
    """
    One line per lab frame across the frames lane, the lines of one trace parted by None, each with its hover text.
    """
    return {"type": "scatter", "mode": "lines", "x": [x for f in frames for x in (minutes(f, rate_hz), minutes(f, rate_hz), None)],
            "y": [0, top, None] * len(frames), "line": line, "yaxis": AXES["frames"],
            "hovertext": [text for text in hovertext for _ in range(3)], "hovertemplate": "%{hovertext}<extra></extra>",
            "connectgaps": False, "showlegend": False}


def bands(ranges, y, height, colour, hovertext, rate_hz):
    """
    One bar per frame range at a height of the frames lane, each with its hover text.
    """
    return {"type": "bar", "orientation": "h", "y": [y] * len(ranges), "width": height,
            "base": [minutes(first, rate_hz) for first, last in ranges],
            "x": [(last - first + 1) / rate_hz / MINUTE_S for first, last in ranges], "marker": {"color": colour},
            "yaxis": AXES["frames"], "hovertext": hovertext, "hovertemplate": "%{hovertext}<extra></extra>",
            "showlegend": False}


def layer_traces(session, top):
    """
    The frames lane's rule traces by layer name, in drawing order: gaps and margins behind, the three heading bands, pauses and jumps in front.
    """
    rate, t, cuts = session["rate_hz"], session["t"], session["cuts"]
    return {
        "gaps": bands(cuts["gaps"], top / 2, top, GAP_COLOUR,
                      [f"gap, both LEDs lost for {last - first + 1} frames, {first} to {last}" for first, last in cuts["gaps"]], rate),
        "margins": bands(cuts["margins"], top / 2, top, MARGIN_COLOUR,
                         [f"margin trimmed, frames {first} to {last}" for first, last in cuts["margins"]], rate),
        "heading_filled": bands(session["heading_filled"], HEADING_Y * top, HEADING_HEIGHT * top, HEADING_FILLED_COLOUR,
                                [f"heading filled over {last - first + 1} frames, {first} to {last}"
                                 for first, last in session["heading_filled"]], rate),
        "heading_held": bands(session["heading_held"], HEADING_Y * top, HEADING_HEIGHT * top, HEADING_HELD_COLOUR,
                              [f"heading held over {last - first + 1} frames while still, {first} to {last}"
                               for first, last in session["heading_held"]], rate),
        "heading_lost": bands(session["heading_lost"], HEADING_Y * top, HEADING_HEIGHT * top, HEADING_LOST_COLOUR,
                              [f"heading lost for {last - first + 1} frames, {first} to {last}"
                               for first, last in session["heading_lost"]], rate),
        "pauses": markers(cuts["pauses"], TICKS_Y * top, PAUSE_MARKER,
                          [f"pause at frame {f}, t jumps {t[f - 1] - t[f - 2]:.1f} s" for f in cuts["pauses"]], rate),
        "jumps": verticals(cuts["jumps"], top, JUMP_LINE, [f"jump at frame {f}, cut with margins" for f in cuts["jumps"]], rate),
    }


def lane_axis(lane, **extra):
    """
    A lane's y axis over its share of the height, its label an annotation rather than a title.
    """
    return {"domain": LANES[lane], "range": [0, 1], "anchor": "x", "showticklabels": False, "showgrid": False,
            "zeroline": False, "fixedrange": True, **extra}


def lane_label(lane, text):
    """
    A lane's name at the left of its axis, angled.
    """
    return {"xref": "paper", "x": 0, "xanchor": "right", "xshift": LABEL_SHIFT_PX, "yref": f"{AXES[lane]} domain",
            "y": 0.5, "yanchor": "middle", "text": text, "textangle": LABEL_ANGLE, "showarrow": False,
            "font": {"size": FONT_SIZE}}


def separators():
    """
    A thin line across the figure in each gap between two lanes.
    """
    bounds = sorted(LANES.values())
    return [{"type": "line", "xref": "paper", "yref": "paper", "x0": 0, "x1": 1, "y0": (below[1] + above[0]) / 2,
             "y1": (below[1] + above[0]) / 2, "line": SEPARATOR} for below, above in zip(bounds, bounds[1:])]


def block_marker(block):
    """
    A block bar's fill: its status colour, dotted through grey when the block is too short for one window.
    """
    colour = STATUS_COLOURS[block["status"]]
    if block["windows"]:
        return {"color": colour}
    return {"color": TOO_SHORT_COLOUR, "pattern": {"shape": TOO_SHORT_PATTERN, "fgcolor": colour, "solidity": 0.5}}


def block_hover(block, session, knobs):
    """
    A block bar's hover: its name and id, frames, length, runs, windows or why none, heading, status and note.
    """
    windows = f"{block['windows']} windows" if block["windows"] else f"too short for one {knobs['window_s']:g} s window"
    return (f"{block['name']} ({block['block_id']}), frames {block['frame_start']} to {block['frame_end']}, "
            f"{data.length_s(block, session['rate_hz']):.1f} s, {runs_in(block, session)} runs, {windows}, "
            f"heading {block['heading_lost_s']:.1f} s lost and {block['heading_filled_s']:.1f} s filled, {block['status']}"
            f"{', ' + block['note'] if block['note'] else ''}")


def glyph_hover(block):
    """
    A glyph's hover: the block's name and status, and what a click does to an auto or confirmed block.
    """
    clicks = {"auto": ", click to confirm", "confirmed": ", click to take the confirmation back"}
    return f"{block['name']}, {block['status']}{clicks.get(block['status'], '')}"


def glyphs(blocks, rate_hz):
    """
    The status glyph of every block as a marker with text above the bar's middle, a click on it toggling the block's confirmation.
    """
    return {"type": "scatter", "mode": "markers+text", "yaxis": AXES["blocks"], "marker": GLYPH_MARKER,
            "x": [minutes((b["frame_start"] + b["frame_end"] + 1) / 2, rate_hz) for b in blocks], "y": [GLYPH_Y] * len(blocks),
            "text": [STATUS_GLYPHS[b["status"]] for b in blocks], "textposition": "middle center", "textfont": GLYPH_FONT,
            "customdata": [{"glyph": b["block_id"]} for b in blocks], "hovertext": [glyph_hover(b) for b in blocks],
            "hovertemplate": "%{hovertext}<extra></extra>", "showlegend": False}


def lanes_figure(session, blocks, flagged, knobs, layers):
    """
    The four lanes of the session with the blocks as they stand after the edits: epochs, runs, frames with the layers chosen, and blocks.
    """
    rate = session["rate_hz"]
    traces = []
    for e in session["epochs"]:
        colour = EPOCH_COLOURS.get(e["epoch"], EPOCH_COLOURS["other"])
        traces.append(bar(e["frame_start"], e["frame_end"], "session", rate, {"color": colour}, text=[e["epoch"]],
                          textposition="inside", insidetextanchor="middle",
                          hovertext=[f"{e['epoch']}, {e['environment']}, {e['condition']}, "
                                     f"frames {e['frame_start']} to {e['frame_end']}, {e['duration_s'] / MINUTE_S:.1f} min"]))
    for r in session["runs"]:
        shade = run_shade(r["path_id"])
        marker = {"color": RUN_SHADES[shade], "line": FLAG_OUTLINE if r["run"] in flagged else {"width": 0},
                  "pattern": {"shape": "" if r["clean"] else DIRTY_PATTERN, "fgcolor": "white", "solidity": 0.4}}
        traces.append(bar(r["frame_start"], r["frame_end"], "runs", rate, marker,
                          hovertext=[f"run {r['run']}, path {r['path_id']} {shade}, {'clean' if r['clean'] else 'dirty'}"
                                     f"{', flagged' if r['run'] in flagged else ''}, "
                                     f"{r['frame_end'] - r['frame_start'] + 1} frames ({r['frame_start']} to {r['frame_end']})"]))
    top = float(np.nanpercentile(np.array(session["speed"], dtype=float), SPEED_SCALE_PERCENTILE))
    layered = layer_traces(session, top)
    for name in ("gaps", "margins"):
        traces.append({**layered[name], "name": name, "visible": name in layers})
    traces.append(speed_trace(session))
    for name in ("heading_filled", "heading_held", "heading_lost", "pauses", "jumps"):
        traces.append({**layered[name], "name": name, "visible": name in layers})
    for b in blocks:
        traces.append(bar(b["frame_start"], b["frame_end"], "blocks", rate, block_marker(b), text=[b["name"]],
                          textposition="inside", insidetextanchor="middle", textfont={"size": FONT_SIZE},
                          customdata=[b["block_id"]], hovertext=[block_hover(b, session, knobs)]))
    traces.append(glyphs(blocks, rate))
    layout = {"title": {"text": f"the lanes of {session['session_id']}: epochs, runs, frames and blocks",
                        "font": {"size": FONT_SIZE + 2}, "x": 0},
              "meta": session["session_id"], "font": {"size": FONT_SIZE},
              "xaxis": {"domain": [0, 1], "anchor": AXES["blocks"], "range": [0, minutes(session["n_frames"] + 1, rate)],
                        "title": {"text": "time in session (min of recording, a pause is a mark)"}},
              "yaxis": lane_axis("session"), "yaxis2": lane_axis("runs"),
              "yaxis3": lane_axis("frames", range=[0, top], showticklabels=True),
              "yaxis4": lane_axis("blocks"),
              "annotations": [lane_label("session", "session"), lane_label("runs", "runs"),
                              lane_label("frames", "frames (px/s)"), lane_label("blocks", "blocks")],
              "barmode": "overlay", "dragmode": False, "hovermode": "closest", "shapes": separators(),
              "margin": {"l": 156, "r": 20, "t": 40, "b": 50}}
    return {"data": traces, "layout": layout}


def error_figure(session):
    """
    An empty figure whose title names the session and the error that stopped its load.
    """
    return {"data": [], "layout": {"title": {"text": f"{session['session_id']} failed to load: {session['error']}"},
                                   "meta": session["session_id"]}}


def session_card(sessions):
    """
    The Session card: the dropdown, the rat, date and protocol, the state line, whole session, reset and the facts popover.
    """
    return card("Session", [
        dcc.Dropdown(id="session", options=session_options(sessions), clearable=False, className=TEXT,
                     value=first_unreviewed(sessions, sessions[0]["session_id"] if sessions else None)),
        html.Div(id="session-line", className=TEXT),
        html.Div(id="state-line", className=MUTED),
        html.Div([key_button("whole session", "Escape", NEUTRAL),
                  html.Button("reset to automatic", id="reset", n_clicks=0, className=DESTRUCTIVE),
                  help_popover("facts", [])], className=BUTTONS),
    ], "flex-1 min-w-[24rem]")


def playback_card():
    """
    The Playback card: play and pause, the live tiles, the speed slider and the occupancy control.
    """
    return card("Playback", [
        html.Button([html.Span("play", id="play-label"), html.Kbd(KEY_LABELS[" "], className=BADGE)], id="play",
                    n_clicks=0, className=PRIMARY, **{"data-key": " "}),
        html.Div([live_tile(label, value_id) for label, value_id in LIVE_TILES], className=TILES),
        html.Div([html.Div("speed", className=TILE_LABEL),
                  dcc.Slider(id="speed", min=0, max=len(SPEEDS) - 1, step=None, value=SPEEDS.index(1),
                             marks={i: f"{speed:g}x" for i, speed in enumerate(SPEEDS)})]),
        html.Div([html.Div("occupancy", className=TILE_LABEL),
                  dcc.RadioItems(id="occupancy", options=occupancy_options({}), value="current", className="segmented")]),
    ], "w-80")


def timeline_card():
    """
    The Timeline card: the four lanes, then the layer toggles, the windows knobs, the hint and the cut note with its popover.
    """
    toggles = html.Div([
        html.Span("show", className=TILE_LABEL),
        dcc.Checklist(id="layers", options=[{"label": label, "value": value} for value, label in LAYERS.items()],
                      value=list(LAYERS), inline=True, className="toggles"),
    ], className=BUTTONS)
    knobs = html.Div([
        html.Span("windows", className=TILE_LABEL),
        html.Label("length s", className=TEXT), dcc.Input(id="window-s", type="number", min=1, value=WINDOW_S, className=NUMBER_INPUT),
        html.Label("stride s", className=TEXT), dcc.Input(id="stride-s", type="number", min=1, value=STRIDE_S, className=NUMBER_INPUT),
        html.Span("display only, the training config owns the real values", className=MUTED),
    ], className=BUTTONS)
    return card("Timeline", [
        dcc.Graph(id="lanes", config={"displayModeBar": False}, style={"height": f"{LANES_HEIGHT_PX}px"}),
        html.Div([toggles, knobs], className=FOOTER),
        html.Div(LANES_HINT, className=MUTED),
        html.Div(id="lanes-caption", className=CAPTION),
    ])


def action_group(label, help_text, buttons):
    """
    One group of action buttons under its small label and ? popover, the block, marks and undo buttons greyed to start.
    """
    disabled = disabled_actions(False, False, 0)
    return html.Div([
        html.Div([html.Span(label), help_popover(f"help-{label}", html.P(help_text))], className=GROUP_LABEL),
        html.Div([key_button(name, key, style, id={"type": "act", "index": name}, disabled=disabled[name])
                  for name, key, style in buttons], className=BUTTONS),
    ], className=GROUP)


def actions_card():
    """
    The Actions card: the grouped buttons, the notes and save, and the message area that shows a hint and fades.
    """
    return card("Actions", [
        html.Div([action_group(*group) for group in ACTION_GROUPS], className="flex flex-wrap gap-5"),
        html.Div([dcc.Textarea(id="notes", placeholder="notes on the session", className=NOTES),
                  html.Button("save session", id="save", n_clicks=0, className=PRIMARY)],
                 className="flex items-start gap-3"),
        html.Div(id="message", className=MESSAGE),
    ], "flex-[2] min-w-[30rem]")


def replay_panel(sessions):
    """
    The Replay tab: the Session and Summary cards, the Map and Playback cards, the Timeline card, the Block and Actions cards.
    """
    block_card = card("Block", [html.Div([html.Div(BLOCK_PLACEHOLDER, className=MUTED), html.Div(NO_MARKS_LINE, className=MUTED)],
                                         id="block-facts", className="flex flex-col gap-2")], "flex-1 min-w-[20rem]")
    return html.Div([
        html.Div([session_card(sessions), card("Summary", [html.Div(id="summary")], "flex-1 min-w-[24rem]")], className=ROW),
        html.Div([card("Map", [dcc.Graph(id="map", config={"displayModeBar": False}, style={"height": MAP_HEIGHT}),
                               html.Div(id="map-caption", className=CAPTION)], "flex-1 min-w-[30rem]"),
                  playback_card()], className=ROW),
        timeline_card(),
        html.Div([block_card, actions_card()], className=ROW),
    ], id="replay-panel", className=PANEL, style=SHOWN)


def layout(sessions):
    """
    The page: the title and the tab strip, the two panels, and the hidden stores.
    """
    return html.Div([
        html.Div([html.H1(TITLE, className="text-xl font-semibold"),
                  dcc.Tabs(id="tabs", value="replay", className="w-64 text-sm",
                           children=[dcc.Tab(label=label, value=value) for value, label in TABS.items()])],
                 className=HEADER),
        replay_panel(sessions),
        html.Div(html.Div(sessions_list(sessions), id="sessions-list", className=PANEL),
                 id="sessions-panel", className=PANEL, style=HIDDEN),
        dcc.Store(id="session-data"), dcc.Store(id="edits", data=[]), dcc.Store(id="blocks", data=[]),
        dcc.Store(id="lanes-base"), dcc.Store(id="keys"), dcc.Store(id="action"), dcc.Store(id="knobs"),
        dcc.Store(id="notice"), dcc.Store(id="ui", data={"selected": None, "marks": [None, None]}),
        dcc.Interval(id="interval", interval=INTERVAL_MS, disabled=True),
    ], className=PAGE)
