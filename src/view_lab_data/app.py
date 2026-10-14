"""
The Dash app: the layout, the selection callback that loads a block, the save callback and the clientside playback.
"""

import numpy as np
from dash import ClientsideFunction, Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate

from . import data

TITLE = "View lab data"

# Tailwind from its CDN lays the page out. Nothing else leaves the machine: the data stays in the local page.
TAILWIND = "https://cdn.tailwindcss.com"
BUTTON = "px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 text-sm"
FIGURE_HEIGHT = "68vh"

# The occupancy background is a 2D histogram of the whole block on this many bins per axis, log scaled.
OCCUPANCY_BINS = 80

# Playback: the speed slider's stops, the browser interval, which schedules frames from the wall clock, and the
# timeline marks every so many seconds.
SPEEDS = (0.25, 0.5, 1, 2, 4, 8)
INTERVAL_MS = 1000 // 60
TIMELINE_MARK_S = 60

# The heading arrow's sources: the processed heading is already corrected, so the raw LED axis is only offered on the
# transformed data.
ARROW_SOURCES = {"corrected": "corrected heading", "raw": "raw LED axis", "motion": "motion direction"}
PROCESSED_ARROW_SOURCES = ("corrected", "motion")

# The run strip under the timeline: a point to hover and click every so many Hz, the bars coloured by path id from
# this cycle (Plotly's category colours), dirty runs hatched.
STRIP_HZ = 10
STRIP_HEIGHT_PX = 150
PATH_COLOURS = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22",
                "#17becf")
DIRTY_PATTERN = "/"

# The bottom table, one row per block and one per run, in the order prev and next walk through.
TABLE_COLUMNS = ("session", "block", "epoch", "run", "path", "clean", "duration_s", "n_runs", "tag", "comment")


def make_app(root, transformed):
    """
    The app over one data folder: every block and run is listed at start, a block's arrays load when selected.
    """
    blocks = data.list_blocks(root, transformed)
    by_id = {block["block_id"]: block for block in blocks}
    runs = {block["block_id"]: block_runs(root, transformed, block) for block in blocks}
    stamp = data.manifest_timestamp(root, transformed)
    targets = [(block["block_id"], run) for block in blocks for run in [None] + [r["run"] for r in runs[block["block_id"]]]]

    app = Dash(__name__, title=TITLE, external_scripts=[TAILWIND])
    app.layout = layout(blocks, table_rows(blocks, runs, data.latest_verdicts(root)), transformed)

    @app.callback(
        Output("session", "value"), Output("block", "options"), Output("block", "value"),
        Output("run", "options"), Output("run", "value"), Output("block-data", "data"), Output("loaded-block", "data"),
        Output("run-span", "data"), Output("labels", "children"), Output("caption", "children"),
        Output("timeline", "max"), Output("timeline", "marks"),
        Input("session", "value"), Input("block", "value"), Input("run", "value"), Input("prev-run", "n_clicks"),
        Input("next-run", "n_clicks"), Input("run-keys", "data"), Input("table", "active_cell"),
        State("loaded-block", "data"))
    def select(session, block_id, run, prev, next_, run_keys, cell, loaded):
        if ctx.triggered_id is None:
            target = first_unreviewed(targets, data.latest_verdicts(root))
        else:
            step = {"prev-run": -1, "next-run": 1, "run-keys": (run_keys or {}).get("step", 0)}.get(ctx.triggered_id, 0)
            target = choose(ctx.triggered_id, session, block_id, run, step, cell, blocks, runs, targets)
        if target is None:
            raise PreventUpdate
        block_id, run = target
        block = by_id[block_id]
        span = run_span(block, runs[block_id], run)
        payload = no_update if loaded == block_id else block_payload(root, transformed, block, runs[block_id])
        n = block["frame_end"] - block["frame_start"] + 1
        marks = {f: f"{f // data.RATE_HZ} s" for f in range(0, n, TIMELINE_MARK_S * data.RATE_HZ)}
        return (block["session_id"], block_options(blocks, block["session_id"]), block_id, run_options(runs[block_id]),
                run, payload, block_id, span, labels(block, span), caption(transformed, root, block, run), n - 1, marks)

    @app.callback(Output("saved", "children"), Output("table", "data"), Input("save", "n_clicks"),
                  State("block", "value"), State("run", "value"), State("tag", "value"), State("comment", "value"),
                  prevent_initial_call=True)
    def save(n_clicks, block_id, run, tag, comment):
        if not tag:
            return "choose a tag first", no_update
        row = data.append_verdict(root, block_id, by_id[block_id]["session_id"], run, tag, comment or "", stamp)
        rows = table_rows(blocks, runs, data.latest_verdicts(root))
        return f"saved {tag} for {block_id} {'whole block' if run is None else f'run {run}'} at {row['saved_at']}", rows

    app.clientside_callback(
        ClientsideFunction("viewer", "tick"),
        Output("figure", "figure"), Output("strip", "figure"), Output("timeline", "value"), Output("clock", "children"),
        Output("live", "children"), Output("offset", "children"), Output("play", "children"),
        Output("interval", "disabled"),
        Input("interval", "n_intervals"), Input("play", "n_clicks"), Input("timeline", "value"), Input("speed", "value"),
        Input("keys", "data"), Input("arrow", "value"), Input("strip", "clickData"), Input("block-data", "data"),
        Input("run-span", "data"))
    return app


def block_runs(root, transformed, block):
    """
    The block's runs, or none when the block cannot be read, so the error shows in the figure when it is selected.
    """
    try:
        return data.list_runs(root, transformed, block)
    except Exception:
        return []


def first_unreviewed(targets, verdicts):
    """
    The first block or run without a verdict, or the first target when everything has one.
    """
    return next((target for target in targets if target not in verdicts), targets[0])


def choose(trigger, session, block_id, run, step, cell, blocks, runs, targets):
    """
    The (block_id, run) to show after a control changed, run None for the whole block, or None when nothing was chosen
    (the table pager clears the active cell).
    """
    if trigger == "session":
        block_id = next(block["block_id"] for block in blocks if block["session_id"] == session)
    if trigger in ("session", "block"):
        return block_id, runs[block_id][0]["run"] if runs[block_id] else None
    if trigger == "table":
        return row_target(cell["row_id"]) if cell else None
    if step:
        index = min(max(targets.index((block_id, run)) + step, 0), len(targets) - 1)
        return targets[index]
    return block_id, run


def run_span(block, block_runs, run):
    """
    The frame index range the playback covers: the run's, or the whole block's, with the run's labels.
    """
    if run is None:
        return {"run": None, "start": 0, "end": block["frame_end"] - block["frame_start"], "path_id": None, "clean": None}
    return next(r for r in block_runs if r["run"] == run)


def block_payload(root, transformed, block, block_runs):
    """
    What the browser needs for one block: its ids, arrays, occupancy and run strip, or the error that stopped the load.
    """
    try:
        arrays = data.load_block(root, transformed, block)
    except Exception as error:
        return {"block_id": block["block_id"], "error": f"{type(error).__name__}: {error}"}
    return {"block_id": block["block_id"], "session_id": block["session_id"], "epoch": block["epoch"],
            "frame_start": block["frame_start"], **arrays, "occupancy": occupancy(arrays["x"], arrays["y"]),
            "strip": strip_figure(block_runs, len(arrays["t"]))}


def occupancy(x, y):
    """
    The log counts of the block's positions on a square grid, as heatmap x and y bin centres and z rows per y.
    """
    x, y = np.array(x, dtype=float), np.array(y, dtype=float)
    keep = np.isfinite(x) & np.isfinite(y)
    counts, xedges, yedges = np.histogram2d(x[keep], y[keep], bins=OCCUPANCY_BINS)
    return {"x": ((xedges[:-1] + xedges[1:]) / 2).tolist(), "y": ((yedges[:-1] + yedges[1:]) / 2).tolist(),
            "z": np.log1p(counts).T.tolist()}


def frame_label(block_runs, frame):
    """
    What a frame of the block is: its run, path and cleanliness, or between runs.
    """
    return next((f"run {r['run']}, path {r['path_id']}, {'clean' if r['clean'] else 'dirty'}"
                 for r in block_runs if r["start"] <= frame <= r["end"]), "between runs")


def strip_figure(block_runs, n_frames):
    """
    The run strip: one horizontal bar per run window in seconds along the block, coloured by path id with one legend
    entry per path and hatched when dirty, over an invisible point every STRIP_HZ carrying the label to hover and click.
    """
    rate = data.RATE_HZ
    frames = range(0, n_frames, rate // STRIP_HZ)
    hover = {"type": "scatter", "mode": "markers", "x": [f / rate for f in frames], "y": [0] * len(frames),
             "text": [frame_label(block_runs, f) for f in frames], "marker": {"opacity": 0}, "showlegend": False,
             "hovertemplate": "%{x:.1f} s, %{text}<extra></extra>"}
    bars, seen = [], set()
    for r in block_runs:
        bars.append({"type": "bar", "orientation": "h", "y": [0], "base": [r["start"] / rate], "x": [r["duration_s"]],
                     "width": 1, "name": f"path {r['path_id']}", "legendgroup": str(r["path_id"]),
                     "legendrank": r["path_id"], "showlegend": r["path_id"] not in seen, "hoverinfo": "skip",
                     "marker": {"color": PATH_COLOURS[r["path_id"] % len(PATH_COLOURS)], "line": {"width": 0},
                                "pattern": {"shape": "" if r["clean"] else DIRTY_PATTERN, "fgcolor": "white",
                                            "solidity": 0.4}}})
        seen.add(r["path_id"])
    layout = {"title": {"text": "run windows along the block, coloured by path id, hatched when dirty",
                        "font": {"size": 13}, "x": 0},
              "xaxis": {"range": [0, n_frames / rate], "title": {"text": "time in block (s)"}},
              "yaxis": {"visible": False, "range": [-0.5, 0.5]}, "hovermode": "x", "hoverdistance": -1,
              "barmode": "overlay", "legend": {"orientation": "h", "x": 1, "xanchor": "right", "y": 1, "yanchor": "bottom"},
              "margin": {"l": 60, "r": 20, "t": 40, "b": 36}}
    return {"data": [hover, *bars], "layout": layout}


def row_id(block_id, run):
    """
    The table row id of a block (run None) or a run.
    """
    return f"{block_id}|{'' if run is None else run}"


def row_target(row_id):
    """
    The (block_id, run) a table row id names.
    """
    block_id, run = row_id.rsplit("|", 1)
    return block_id, int(run) if run else None


def table_rows(blocks, runs, verdicts):
    """
    One row per block followed by one per run, with the latest tag and comment or blanks when unreviewed.
    """
    rows = []
    for block in blocks:
        verdict = verdicts.get((block["block_id"], None), {})
        rows.append({"id": row_id(block["block_id"], None), "session": block["session_id"], "block": block["block_id"],
                     "epoch": block["epoch"], "run": "", "path": "", "clean": "",
                     "duration_s": round(block["duration_s"], 1), "n_runs": block["n_runs"],
                     "tag": verdict.get("tag", ""), "comment": verdict.get("comment", "")})
        for run in runs[block["block_id"]]:
            verdict = verdicts.get((block["block_id"], run["run"]), {})
            rows.append({"id": row_id(block["block_id"], run["run"]), "session": block["session_id"],
                         "block": block["block_id"], "epoch": block["epoch"], "run": run["run"], "path": run["path_id"],
                         "clean": "yes" if run["clean"] else "no", "duration_s": round(run["duration_s"], 1), "n_runs": "",
                         "tag": verdict.get("tag", ""), "comment": verdict.get("comment", "")})
    return rows


def block_options(blocks, session_id):
    """
    The block dropdown's options for one session.
    """
    return [{"label": f"{block['epoch']} {block['block_id']} ({block['duration_s']:.0f} s, {block['n_runs']} runs)",
             "value": block["block_id"]} for block in blocks if block["session_id"] == session_id]


def run_options(block_runs):
    """
    The run dropdown's options for one block, the whole block being the cleared dropdown.
    """
    return [{"label": f"run {r['run']}, path {r['path_id']}, {'clean' if r['clean'] else 'dirty'} ({r['duration_s']:.1f} s)",
             "value": r["run"]} for r in block_runs]


def arrow_options(transformed):
    """
    The heading arrow's radio options for the data source.
    """
    sources = ARROW_SOURCES if transformed else {key: ARROW_SOURCES[key] for key in PROCESSED_ARROW_SOURCES}
    return [{"label": label, "value": value} for value, label in sources.items()]


def labels(block, span):
    """
    The left panel's lines about what is on screen, with the lab frame numbers of the play window.
    """
    lines = [("subject", block["subject_id"]), ("date", block["date"]), ("group", block["group"]),
             ("epoch", f"{block['epoch']} ({block['environment']})"), ("block duration", f"{block['duration_s']:.1f} s"),
             ("block lab frames", f"{block['frame_start']} to {block['frame_end']}"),
             ("run", "whole block" if span["run"] is None else span["run"]),
             ("run lab frames", f"{block['frame_start'] + span['start']} to {block['frame_start'] + span['end']}"),
             ("path_id", "" if span["path_id"] is None else span["path_id"]),
             ("clean", "" if span["clean"] is None else ("yes" if span["clean"] else "no"))]
    return [html.Div([html.Span(f"{name}: ", className="text-gray-500"), html.Span(str(value))]) for name, value in lines]


def caption(transformed, root, block, run):
    """
    The text under the figure: how to read it, what a verdict means and which data made it.
    """
    source = ("the transformed lab data in pixels, camera frame, y down, position from the lab's mashup light (the "
              "average of the two lights, or the one light present)" if transformed
              else "the processed lab data in metres, room frame, north up")
    return [
        html.P("How to read it: the grey shading is where the animal spent time over the whole block (log occupancy, "
               "darker is more). The dots are the last 2 s of the path at 20 Hz, coloured by speed on the colour bar "
               "and joined by the grey line. The large red dot is the current position and the arrow the heading from "
               "the chosen source: corrected is the LED axis minus the session's offset, raw LED axis the direction "
               "from the back light to the front light, motion the direction of the smoothed velocity."),
        html.P("The strip under the timeline shows the lab's run windows along the block, coloured by path id and "
               "hatched when the labeler called the run dirty. The plain stretches between them are returns and "
               "dwells. The black line is the current frame. Click the strip to jump there."),
        html.P("A verdict marks a tracking or labelling problem, never a behaviour: a rat that slows, stops or scans "
               "is data to keep."),
        html.P(f"Data: {source}, from {root}. Session {block['session_id']}, block {block['block_id']}, "
               f"{'whole block' if run is None else f'run {run}'}.")]


def field(name, component):
    """
    A labelled control of the left panel.
    """
    return html.Div([html.Label(name, className="block text-xs text-gray-500"), component])


def layout(blocks, rows, transformed):
    """
    The page: the left panel, the figure with its controls and the run strip, the table of every block and run, and
    the hidden stores.
    """
    sessions = sorted({block["session_id"] for block in blocks})
    panel = html.Div([
        html.H1(TITLE, className="text-xl font-semibold"),
        field("session", dcc.Dropdown(id="session", options=sessions, clearable=False)),
        field("block", dcc.Dropdown(id="block", clearable=False)),
        field("run", dcc.Dropdown(id="run", placeholder="whole block")),
        html.Div(id="labels", className="text-sm leading-6"),
        html.Div(id="live", className="text-sm"), html.Div(id="offset", className="text-sm"),
        field("tag (keys f, t, m, u)", dcc.Dropdown(id="tag", options=list(data.TAGS), placeholder="tag")),
        dcc.Textarea(id="comment", placeholder="comment", className="w-full h-20 border rounded p-2 text-sm"),
        html.Button("save", id="save", n_clicks=0, className=BUTTON),
        html.Div(id="saved", className="text-xs text-gray-600"),
    ], className="w-80 shrink-0 flex flex-col gap-3")
    speed_marks = {i: f"{speed:g}x" for i, speed in enumerate(SPEEDS)}
    main = html.Div([
        dcc.Graph(id="figure", config={"displayModeBar": False}, style={"height": FIGURE_HEIGHT}),
        html.Div([html.Button("play", id="play", n_clicks=0, className=BUTTON),
                  html.Span(id="clock", className="font-mono text-sm"),
                  html.Button("previous run", id="prev-run", n_clicks=0, className=BUTTON),
                  html.Button("next run", id="next-run", n_clicks=0, className=BUTTON),
                  html.Span("arrow:", className="text-sm text-gray-500 ml-4"),
                  dcc.RadioItems(id="arrow", options=arrow_options(transformed), value="corrected", inline=True,
                                 inputClassName="mr-1", labelClassName="mr-3 text-sm")],
                 className="flex flex-wrap items-center gap-3 my-2"),
        dcc.Slider(id="timeline", min=0, max=1, step=1, value=0, marks={}, updatemode="drag"),
        dcc.Graph(id="strip", config={"displayModeBar": False}, style={"height": f"{STRIP_HEIGHT_PX}px"}),
        html.Div([html.Label("speed", className="text-xs text-gray-500"),
                  dcc.Slider(id="speed", min=0, max=len(SPEEDS) - 1, step=None, value=SPEEDS.index(1), marks=speed_marks)],
                 className="w-80"),
        html.Div(id="caption", className="text-sm text-gray-700 mt-3 space-y-1"),
    ], className="flex-1 min-w-0")
    table = dash_table.DataTable(
        id="table", data=rows, columns=[{"name": name, "id": name} for name in TABLE_COLUMNS],
        style_table={"height": "35vh", "overflowY": "auto"}, style_cell={"textAlign": "left", "fontSize": "14px"},
        style_data_conditional=[{"if": {"filter_query": "{run} = ''"}, "fontWeight": "bold"}])
    return html.Div([
        html.Div([panel, main], className="flex gap-6"),
        html.Div(table, className="mt-4"),
        dcc.Store(id="block-data"), dcc.Store(id="loaded-block"), dcc.Store(id="run-span"), dcc.Store(id="keys"),
        dcc.Store(id="run-keys"),
        dcc.Interval(id="interval", interval=INTERVAL_MS, disabled=True),
    ], className="font-sans text-base text-gray-900 p-4")
