// RatReplay in the browser: the session's arrays arrive once in the session-data store, then every interval tick draws
// the frame the wall clock asks for, so 1x is real time whatever the browser manages. Keys and the action buttons (each
// carrying its key as data-key) go through the keys store, as do the clicks the lanes turn into keys: a click on a
// block's glyph (the key glyph, confirm) and a right click on a run bar (the key right-click, flag), each with the lab
// frame it fell on. The ones that edit become operations in the action store through their own callback, act, so the
// tick, which redraws from the server's answer, is never upstream of itself. The lanes arrive drawn from the server,
// the cursor, the marks, the selected block's outline and connectors, the ghost of its first windows and the zoom are
// laid over them here. A click on the lanes moves the cursor, a click on a block bar selects the block. The selection
// and the marks go to the server in the ui store, when they change, so it can fill the Block card and grey the actions.
// Hints from here and notices from the server share one message area that fades after MESSAGE_MS. The occupancy comes
// as one grid per epoch and the view chooses which are shown.

const SPEEDS = [0.25, 0.5, 1, 2, 4, 8];
const OCCUPANCY_SCALE = [[0, "rgba(0,0,0,0)"], [1, "rgba(60,60,60,0.55)"]];
const GHOST_WINDOWS = 3;
const GHOST = {fillcolor: "rgba(0,0,0,0.10)", line: {color: "rgba(0,0,0,0.35)", width: 1}};
const TRAIL_S = 2;
const TRAIL_HZ = 20;
const TRAIL_WIDTH = 3;
const TRAIL_MARKER = 9;
const POINT_SIZE = 14;
const PATH_HZ = 4;
const PATH_LINE = {color: "rgba(0,0,0,0.3)", width: 1};
const ARROW_FRACTION = 0.08;
const ARROW_SIZE = 16;
const ARROW_COLOUR = "#d62728";
const RANGE_PAD = 0.05;
const SPEED_SCALE_PERCENTILE = 0.95;
const MINUTE_S = 60;
const LANES_HZ = 10;
const RUNS_AXIS = "yaxis2";
const FRAMES_AXIS = "yaxis3";
const BLOCKS_AXIS = "yaxis4";
const BLOCKS_REF = "y4";
const CURSOR_COLOUR = "#7c3aed";
const CURSOR = {color: CURSOR_COLOUR, width: 3};
const CURSOR_HEAD = {text: "▼", font: {color: CURSOR_COLOUR, size: 14}};
const MARK = {color: "#d62728", width: 2, dash: "dash"};
const MARK_FILL = "rgba(214,39,40,0.12)";
const SELECTED = {color: "#111827", width: 3};
const CONNECTOR = {color: "#111827", width: 1};
const MESSAGE_MS = 4000;
const OPS = {Enter: "confirm", a: "accept", n: "new", d: "drop", ",": "move", ".": "move", s: "split", f: "flag",
             z: "undo"};
const CLICK_OPS = {glyph: "confirm", "right-click": "flag"};
const KEYS = [" ", "ArrowLeft", "ArrowRight", "[", "]", "{", "}", "i", "o", "Escape", ...Object.keys(OPS)];
const N_OUTPUTS = 10;

const S = {session: null, base: null, blocks: [], index: 0, playing: false, speed: 1, view: "current", knobs: null,
           anchorWall: 0, anchorIndex: 0, range: null, speedMax: 1, occupancy: {}, markIn: null, markOut: null,
           selectedFrame: null, pendingNew: false, ui: null, timer: null, path: {key: null, trace: null},
           drawnIndex: -1, actions: 0};

function triggered(id) {
  return dash_clientside.callback_context.triggered.some((t) => t.prop_id.startsWith(id + "."));
}

function anchor() {
  S.anchorWall = performance.now();
  S.anchorIndex = S.index;
}

function finite(values) {
  return values.filter((v) => v !== null && isFinite(v));
}

function axisRange(values, reversed) {
  const v = finite(values);
  let lo = Infinity, hi = -Infinity;
  for (const x of v) { if (x < lo) lo = x; if (x > hi) hi = x; }
  const pad = (hi - lo) * RANGE_PAD;
  return reversed ? [hi + pad, lo - pad] : [lo - pad, hi + pad];
}

function percentile(values, q) {
  const v = finite(values).sort((a, b) => a - b);
  return v.length ? v[Math.floor(q * (v.length - 1))] : 1;
}

// The message area shows the text and fades once the timer runs out, a new message restarting it.
function showMessage(text) {
  const area = document.getElementById("message");
  area.textContent = text;
  area.classList.add("show");
  clearTimeout(S.timer);
  S.timer = setTimeout(() => area.classList.remove("show"), MESSAGE_MS);
}

function loadSession(session) {
  S.session = session;
  S.index = 0;
  S.playing = false;
  S.markIn = S.markOut = S.selectedFrame = null;
  S.pendingNew = false;
  S.drawnIndex = -1;
  if (session.error) return;
  S.range = {x: axisRange(session.x, false), y: axisRange(session.y, true)};
  S.speedMax = percentile(session.speed, SPEED_SCALE_PERCENTILE);
  S.occupancy = Object.fromEntries(Object.entries(session.occupancy).map(([name, grid]) =>
    [name, {type: "heatmap", x: grid.x, y: grid.y, z: grid.z, zmin: 0, colorscale: OCCUPANCY_SCALE, showscale: false,
            hoverinfo: "skip"}]));
  anchor();
}

// The occupancy grids the view asks for: the epoch under the cursor, every epoch, or one by name.
function occupancyTraces(frame) {
  if (S.view === "all") return Object.values(S.occupancy);
  const name = S.view === "current" ? epochAt(frame) : S.view;
  return S.occupancy[name] ? [S.occupancy[name]] : [];
}

function n() {
  return S.session.n_frames;
}

// Lab frames are 1-based and contiguous, so the array index is the frame minus one.
function lab(index) {
  return index + 1;
}

function seek(index) {
  S.index = Math.min(Math.max(index, 0), n() - 1);
  anchor();
}

function step(frames) {
  S.playing = false;
  seek(S.index + frames);
}

function advance() {
  const index = S.anchorIndex + Math.floor((performance.now() - S.anchorWall) / 1000 * S.speed * S.session.rate_hz);
  S.index = Math.min(index, n() - 1);
  if (S.index >= n() - 1) S.playing = false;
}

function holding(items, frame) {
  return items.find((item) => item.frame_start <= frame && frame <= item.frame_end) || null;
}

// The selected block as it stands now: the one holding the frame selected, so it survives renumbering.
function selected() {
  return S.selectedFrame === null ? null : holding(S.blocks, S.selectedFrame);
}

// The previous or next start among the items, relative to the cursor's lab frame.
function jump(items, direction) {
  const frame = lab(S.index);
  const starts = items.map((item) => item.frame_start).sort((a, b) => a - b);
  const target = direction > 0 ? starts.find((s) => s > frame) : starts.reverse().find((s) => s < frame);
  if (target !== undefined) step(target - 1 - S.index);
}

// The arrow is a segment from the current point plus an arrow marker pointing along the corrected heading, all in data
// coordinates, so the reversed image y axis draws it where the data says.
function arrowTrace(s, i) {
  const angle = s.heading[i];
  if (angle === null || s.x[i] === null) return [];
  const length = ARROW_FRACTION * (S.range.x[1] - S.range.x[0]);
  return [{type: "scatter", mode: "lines+markers",
           x: [s.x[i], s.x[i] + length * Math.cos(angle)], y: [s.y[i], s.y[i] + length * Math.sin(angle)],
           line: {color: ARROW_COLOUR, width: 3},
           marker: {symbol: ["circle", "arrow"], size: [0, ARROW_SIZE], angleref: "previous", color: ARROW_COLOUR},
           hoverinfo: "skip"}];
}

// The selected block's whole path as a thin line, built once per block and reused every frame.
function pathTrace(block) {
  const key = `${block.frame_start}-${block.frame_end}`;
  if (S.path.key !== key) {
    const s = S.session, every = Math.max(1, Math.round(s.rate_hz / PATH_HZ)), x = [], y = [];
    for (let k = block.frame_start - 1; k < block.frame_end; k += every) { x.push(s.x[k]); y.push(s.y[k]); }
    S.path = {key: key, trace: {type: "scatter", mode: "lines", x: x, y: y, line: PATH_LINE, hoverinfo: "skip"}};
  }
  return S.path.trace;
}

function epochAt(frame) {
  const epoch = holding(S.session.epochs, frame);
  return epoch ? epoch.epoch : "no epoch";
}

function mapFigure() {
  const s = S.session, i = S.index, rate = s.rate_hz, block = selected();
  const every = Math.max(1, Math.round(rate / TRAIL_HZ));
  const first = Math.max(0, i - TRAIL_S * rate);
  const trail = [];
  for (let k = i; k >= first; k -= every) trail.unshift(k);
  return {
    data: [
      ...occupancyTraces(lab(i)),
      ...(block ? [pathTrace(block)] : []),
      {type: "scatter", mode: "lines+markers", x: trail.map((k) => s.x[k]), y: trail.map((k) => s.y[k]),
       line: {color: "rgba(0,0,0,0.35)", width: TRAIL_WIDTH},
       marker: {size: TRAIL_MARKER, color: trail.map((k) => s.speed[k]), colorscale: "Viridis", cmin: 0, cmax: S.speedMax,
                showscale: true, colorbar: {title: {text: "speed (px/s)", side: "right"}, thickness: 18, len: 0.6,
                                            outlinewidth: 0}},
       hovertemplate: "%{marker.color:.1f} px/s<extra></extra>"},
      {type: "scatter", mode: "markers", x: [s.x[i]], y: [s.y[i]],
       marker: {size: POINT_SIZE, color: ARROW_COLOUR, line: {color: "white", width: 2}}, hoverinfo: "skip"},
      ...arrowTrace(s, i),
    ],
    layout: {
      title: {text: `RatReplay, ${s.session_id}, ${epochAt(lab(i))}` +
                    `${block ? `, ${block.name}` : ""}, camera pixels with y down`},
      xaxis: {title: {text: "x (px)"}, range: S.range.x, constrain: "domain"},
      yaxis: {title: {text: "y (px)"}, range: S.range.y, scaleanchor: "x", scaleratio: 1},
      showlegend: false, margin: {l: 60, r: 20, t: 50, b: 50}, uirevision: s.session_id,
    },
  };
}

function minutes(index) {
  return index / S.session.rate_hz / MINUTE_S;
}

function across(x0, x1, extra) {
  return {type: "line", xref: "x", yref: "paper", x0: x0, x1: x1, y0: 0, y1: 1, ...extra};
}

// A line from the top of the blocks lane to the top of the frames lane, showing where the selected block's edge falls.
function connector(index) {
  const layout = S.base.layout, x = minutes(index);
  return {type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: layout[BLOCKS_AXIS].domain[1],
          y1: layout[FRAMES_AXIS].domain[1], line: CONNECTOR};
}

// The selected block's first windows at the knobs, as faint bars on the blocks lane, as many as fit up to GHOST_WINDOWS.
function ghostWindows(block) {
  const rate = S.session.rate_hz, length = S.knobs.window_s * rate, stride = S.knobs.stride_s * rate, shapes = [];
  for (let k = 0; k < GHOST_WINDOWS; k++) {
    const start = block.frame_start - 1 + k * stride;
    if (start + length > block.frame_end) break;
    shapes.push({type: "rect", xref: "x", yref: BLOCKS_REF, x0: minutes(start), x1: minutes(start + length),
                 y0: 0.2 + 0.1 * k, y1: 0.8 - 0.1 * k, ...GHOST});
  }
  return shapes;
}

// The cursor's head: a small triangle sitting on the top edge of the figure at the cursor's time.
function cursorHead() {
  return {xref: "x", x: minutes(S.index), yref: "paper", y: 1, yanchor: "bottom", showarrow: false, ...CURSOR_HEAD};
}

function lanesFigure() {
  const block = selected(), shapes = [...S.base.layout.shapes];
  if (S.markIn !== null && S.markOut !== null) {
    const [a, b] = [S.markIn, S.markOut].sort((p, q) => p - q);
    shapes.push({...across(minutes(a), minutes(b + 1), {type: "rect"}), fillcolor: MARK_FILL, line: {width: 0}});
  }
  for (const mark of [S.markIn, S.markOut]) {
    if (mark !== null) shapes.push(across(minutes(mark), minutes(mark), {line: MARK}));
  }
  if (block) {
    shapes.push({type: "rect", xref: "x", yref: BLOCKS_REF, x0: minutes(block.frame_start - 1),
                 x1: minutes(block.frame_end), y0: 0.05, y1: 0.95, line: SELECTED},
                connector(block.frame_start - 1), connector(block.frame_end), ...ghostWindows(block));
  }
  shapes.push(across(minutes(S.index), minutes(S.index), {line: CURSOR}));
  S.drawnIndex = S.index;
  const xaxis = {...S.base.layout.xaxis, range: block ? block.zoom : S.base.layout.xaxis.range};
  const annotations = [...S.base.layout.annotations, cursorHead()];
  return {data: S.base.data, layout: {...S.base.layout, xaxis: xaxis, shapes: shapes, annotations: annotations}};
}

function errorFigure(session) {
  return {data: [], layout: {title: {text: `${session.session_id} failed to load: ${session.error}`}}};
}

function refuse(hint) {
  showMessage(hint);
  return null;
}

// The operation a key asks for, or null with the hint saying what it needs. Confirm from a glyph click and flag from a
// right click act at the frame the click fell on, Enter, remove, move and split on the selected block, split where the
// cursor stands inside it.
function operation(keys) {
  const op = OPS[keys.key] || CLICK_OPS[keys.key], frame = keys.frame === undefined ? lab(S.index) : keys.frame;
  const block = selected();
  if (op === "accept" || op === "undo") return {op: op};
  if (op === "new") {
    if (S.markIn === null || S.markOut === null) return refuse("mark the range first, i at its start and o at its end");
    const [a, b] = [S.markIn, S.markOut].sort((p, q) => p - q);
    S.pendingNew = true;
    return {op: op, frame_start: lab(a), frame_end: lab(b)};
  }
  if (op === "flag") {
    const run = holding(S.session.runs, frame);
    return run ? {op: op, run: run.run} : refuse("no run under the cursor to flag");
  }
  if (keys.key === "glyph") return {op: op, frame: frame};
  if (!block) return refuse("select a block first, click its bar");
  if (op === "move") return {op: op, frame: frame, edge: keys.key === "," ? "start" : "end", at: block.frame_start};
  if (op === "split") {
    if (frame <= block.frame_start || frame > block.frame_end) return refuse("move the cursor inside the selected block to split it there");
    return {op: op, frame: frame};
  }
  return {op: op, frame: block.frame_start};
}

function onKey(keys) {
  const key = keys.key, rate = S.session.rate_hz;
  if (key === " ") { S.playing = !S.playing; anchor(); }
  else if (key === "ArrowLeft" || key === "ArrowRight") step((key === "ArrowLeft" ? -1 : 1) * (keys.shift ? rate : 1));
  else if (key === "[" || key === "]") jump(S.session.runs, key === "]" ? 1 : -1);
  else if (key === "{" || key === "}") jump(S.blocks, key === "}" ? 1 : -1);
  else if (key === "i") S.markIn = S.index;
  else if (key === "o") S.markOut = S.index;
  else if (key === "Escape") S.selectedFrame = null;
  else if (key === "jump") seek(keys.frame - 1);
}

// The keys store as an operation for the action store, counted so the same operation twice still arrives, or no update
// for a key that moves or marks and for a refused one.
function act(keys) {
  if (!S.session || S.session.error || !(OPS[keys.key] || CLICK_OPS[keys.key])) return dash_clientside.no_update;
  const op = operation(keys);
  return op ? {...op, n: ++S.actions} : dash_clientside.no_update;
}

// A click on a block bar selects the block, its customdata the block id. A click on a glyph, customdata naming the
// block, becomes the glyph key at the block's first frame, pressed once this tick is over.
function select(click) {
  const data = click.points[0].customdata;
  if (typeof data === "string") S.selectedFrame = S.blocks.find((b) => b.block_id === data).frame_start;
  else if (data && data.glyph) {
    const block = S.blocks.find((b) => b.block_id === data.glyph);
    setTimeout(() => press({key: "glyph", frame: block.frame_start}), 0);
  }
}

// The live tiles: time in session, lab frame, speed, lights and the run under the cursor.
function liveTexts() {
  const s = S.session, i = S.index, frame = lab(i), run = holding(s.runs, frame);
  return [`${s.t[i].toFixed(2)} s`, `${frame}`, s.speed[i] === null ? "n/a" : `${s.speed[i].toFixed(0)} px/s`,
          `${s.n_lights[i]}`, run ? `${run.run}, path ${run.path_id} ${run.clean ? "clean" : "dirty"}` : "none"];
}

// What the server needs to fill the Block card and grey the actions, sent only when it changes: the selected block
// and the two marks as lab frames.
function uiState() {
  const block = selected();
  const marks = [S.markIn, S.markOut].map((mark) => (mark === null ? null : lab(mark)));
  const ui = {selected: block ? block.block_id : null, marks: marks};
  const key = JSON.stringify(ui);
  if (key === S.ui) return dash_clientside.no_update;
  S.ui = key;
  return ui;
}

function tick(nIntervals, keys, click, speedIndex, view, knobs, session, base, blocks, notice) {
  const nu = dash_clientside.no_update;
  S.speed = SPEEDS[speedIndex];
  S.view = view;
  S.knobs = knobs;
  if (triggered("notice") && notice) showMessage(notice.text);
  if (triggered("session-data")) loadSession(session);
  if (triggered("lanes-base")) { S.base = base; S.drawnIndex = -1; }
  if (triggered("blocks")) {
    S.blocks = blocks;
    S.drawnIndex = -1;
    if (S.pendingNew) { S.markIn = S.markOut = null; S.pendingNew = false; }
  }
  if (!S.session || !S.base || S.base.layout.meta !== S.session.session_id) return Array(N_OUTPUTS).fill(nu);
  if (S.session.error) return [errorFigure(S.session), S.base, "", "", "", "", "", "play", true, nu];
  if (triggered("lanes") && click) select(click);
  if (triggered("keys")) onKey(keys);
  else if (triggered("speed")) anchor();
  else if (triggered("interval") && S.playing) advance();
  const redraw = !triggered("interval") || Math.abs(S.index - S.drawnIndex) >= S.session.rate_hz / LANES_HZ;
  return [mapFigure(), redraw ? lanesFigure() : nu, ...liveTexts(), S.playing ? "pause" : "play", !S.playing, uiState()];
}

let keyCount = 0;
function press(data) {
  dash_clientside.set_props("keys", {data: {...data, n: ++keyCount}});
}

// The drawn lanes under a pointer event with the pointer's position in the plot's pixels, or null off the lanes.
function lanesUnder(event) {
  const gd = event.target.closest("#lanes .js-plotly-plot");
  if (!gd || !S.session || !gd._fullLayout) return null;
  const box = gd.getBoundingClientRect();
  return {layout: gd._fullLayout, px: event.clientX - box.left, py: event.clientY - box.top};
}

// The lab frame under a pointer event on the lanes, from the pixel through the drawn x axis, or null off the plot area.
function laneFrame(event) {
  const under = lanesUnder(event);
  if (!under) return null;
  const ax = under.layout.xaxis, px = under.px - ax._offset;
  if (px < 0 || px > ax._length) return null;
  return Math.round(ax.p2d(px) * MINUTE_S * S.session.rate_hz) + 1;
}

// Whether a pointer event on the lanes fell within the runs lane.
function onRunsLane(event) {
  const under = lanesUnder(event), ax = under.layout[RUNS_AXIS];
  return under.py >= ax._offset && under.py <= ax._offset + ax._length;
}

document.addEventListener("keydown", (event) => {
  if (["INPUT", "TEXTAREA"].includes(event.target.tagName) || !KEYS.includes(event.key)) return;
  event.preventDefault();
  press({key: event.key, shift: event.shiftKey});
});

document.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-toggle]");
  if (toggle) { document.getElementById(toggle.dataset.toggle).classList.toggle("hidden"); return; }
  const button = event.target.closest("[data-key]");
  if (button) { press({key: button.dataset.key, shift: false}); return; }
  const frame = laneFrame(event);
  if (frame !== null) press({key: "jump", frame: frame});
});

document.addEventListener("contextmenu", (event) => {
  const frame = laneFrame(event);
  if (frame === null || !onRunsLane(event)) return;
  event.preventDefault();
  press({key: "right-click", frame: frame});
});

window.dash_clientside = Object.assign({}, window.dash_clientside, {replay: {tick: tick, act: act}});
