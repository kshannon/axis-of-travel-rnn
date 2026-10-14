// Playback in the browser: the block's arrays arrive once in the block-data store, then every interval tick draws the
// frame the wall clock asks for, so 1x is real time whatever the browser manages. Keys go through the keys stores.

const SPEEDS = [0.25, 0.5, 1, 2, 4, 8];
const TRAIL_S = 2;
const TRAIL_HZ = 20;
const TRAIL_WIDTH = 3;
const TRAIL_MARKER = 9;
const POINT_SIZE = 14;
const ARROW_FRACTION = 0.08;
const ARROW_SIZE = 16;
const ARROW_COLOURS = {corrected: "#d62728", raw: "#ff7f0e", motion: "#1f77b4"};
const RANGE_PAD = 0.05;
const SPEED_SCALE_PERCENTILE = 0.95;
const CURSOR = {color: "black", width: 2};
const TAG_KEYS = {f: "fine", t: "tracking artifact", m: "run mislabelled", u: "unsure"};

const S = {block: null, span: null, index: 0, playing: false, speed: 1, arrow: "corrected", anchorWall: 0,
           anchorIndex: 0, range: null, speedMax: 1, occupancy: null};

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

function loadBlock(block) {
  S.block = block;
  if (block.error) return;
  S.range = {x: axisRange(block.x, false), y: axisRange(block.y, block.y_down)};
  S.speedMax = percentile(block.speed, SPEED_SCALE_PERCENTILE);
  S.occupancy = {type: "heatmap", x: block.occupancy.x, y: block.occupancy.y, z: block.occupancy.z, zmin: 0,
                 colorscale: [[0, "rgba(0,0,0,0)"], [1, "rgba(60,60,60,0.55)"]], showscale: false, hoverinfo: "skip"};
}

function n() {
  return S.block.t.length;
}

function startRun(span) {
  S.span = span;
  S.index = span.start;
  S.playing = !S.block.error;
  anchor();
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
  const rate = S.block.rate_hz;
  const limit = S.anchorIndex < S.span.end ? S.span.end : n() - 1;
  const index = S.anchorIndex + Math.floor((performance.now() - S.anchorWall) / 1000 * S.speed * rate);
  S.index = Math.min(index, limit);
  if (S.index >= limit) S.playing = false;
}

function errorFigure(block) {
  return {data: [], layout: {title: {text: `block ${block.block_id} failed to load: ${block.error}`}}};
}

function degrees(radians) {
  return radians === null ? "n/a" : `${(radians * 180 / Math.PI).toFixed(0)} deg`;
}

// The arrow's angle from the chosen source, in the data's own axes: the corrected heading is the LED axis minus the
// session's offset, which the processed data has already subtracted.
function arrowAngle(b, i) {
  const source = S.arrow === "motion" ? b.motion[i] : b.heading[i];
  if (source === null) return null;
  return S.arrow === "corrected" && b.led_offset ? source - b.led_offset.rad : source;
}

// The arrow is a segment from the current point plus an arrow marker pointing along it, all in data coordinates, so
// the reversed image y axis draws it where the data says.
function arrowTrace(b, i) {
  const angle = arrowAngle(b, i);
  if (angle === null || b.x[i] === null) return [];
  const length = ARROW_FRACTION * (S.range.x[1] - S.range.x[0]);
  const colour = ARROW_COLOURS[S.arrow];
  return [{type: "scatter", mode: "lines+markers",
           x: [b.x[i], b.x[i] + length * Math.cos(angle)], y: [b.y[i], b.y[i] + length * Math.sin(angle)],
           line: {color: colour, width: 3},
           marker: {symbol: ["circle", "arrow"], size: [0, ARROW_SIZE], angleref: "previous", color: colour},
           hoverinfo: "skip"}];
}

function figure() {
  const b = S.block, i = S.index, rate = b.rate_hz;
  const every = Math.max(1, Math.round(rate / TRAIL_HZ));
  const first = Math.max(0, i - TRAIL_S * rate);
  const trail = [];
  for (let k = i; k >= first; k -= every) trail.unshift(k);
  const units = `speed (${b.units}/s)`;
  const run = S.span.run === null ? "whole block" : `run ${S.span.run}`;
  return {
    data: [
      S.occupancy,
      {type: "scatter", mode: "lines+markers", x: trail.map((k) => b.x[k]), y: trail.map((k) => b.y[k]),
       line: {color: "rgba(0,0,0,0.35)", width: TRAIL_WIDTH},
       marker: {size: TRAIL_MARKER, color: trail.map((k) => b.speed[k]), colorscale: "Viridis", cmin: 0, cmax: S.speedMax,
                showscale: true, colorbar: {title: {text: units, side: "right"}, thickness: 18, len: 0.6, outlinewidth: 0}},
       hovertemplate: `%{marker.color:.2f} ${b.units}/s<extra></extra>`},
      {type: "scatter", mode: "markers", x: [b.x[i]], y: [b.y[i]],
       marker: {size: POINT_SIZE, color: "#d62728", line: {color: "white", width: 2}}, hoverinfo: "skip"},
      ...arrowTrace(b, i),
    ],
    layout: {
      title: {text: `${b.session_id} ${b.epoch}, block ${b.block_id}, ${run}`},
      xaxis: {title: {text: `x (${b.units})`}, range: S.range.x, constrain: "domain"},
      yaxis: {title: {text: `y (${b.units})`}, range: S.range.y, scaleanchor: "x", scaleratio: 1},
      showlegend: false, margin: {l: 60, r: 20, t: 50, b: 50}, uirevision: b.block_id,
    },
  };
}

// The strip arrives built with the block, the cursor at the current frame is the only thing that moves.
function strip() {
  const b = S.block, t = S.index / b.rate_hz;
  const cursor = {type: "line", x0: t, x1: t, y0: -0.5, y1: 0.5, line: CURSOR};
  return {data: b.strip.data, layout: {...b.strip.layout, shapes: [cursor], uirevision: b.block_id}};
}

function offsetLine(b) {
  if (!b.led_offset) return "heading: already corrected in the processed data";
  return `LED offset over the session: ${degrees(b.led_offset.rad)}, concentration ${b.led_offset.r.toFixed(2)}`;
}

function tick(nIntervals, playClicks, slider, speedIndex, keys, arrow, stripClick, block, span) {
  const nu = dash_clientside.no_update;
  S.speed = SPEEDS[speedIndex];
  S.arrow = arrow;
  if (triggered("block-data")) loadBlock(block);
  if (!S.block) return [nu, nu, nu, nu, nu, nu, nu, nu];
  if (S.block.error) return [errorFigure(S.block), nu, nu, "", "", "", "play", true];
  if (triggered("run-span")) startRun(span);
  else if (triggered("timeline")) seek(slider);
  else if (triggered("strip")) seek(Math.round(stripClick.points[0].x * S.block.rate_hz));
  else if (triggered("play")) { S.playing = !S.playing; anchor(); }
  else if (triggered("speed")) anchor();
  else if (triggered("keys")) {
    if (keys.key === " ") { S.playing = !S.playing; anchor(); }
    else step((keys.key === "ArrowLeft" ? -1 : 1) * (keys.shift ? S.block.rate_hz : 1));
  }
  else if (triggered("interval") && S.playing) advance();
  const b = S.block, i = S.index;
  const window = S.span.run === null ? "block" : `run ${S.span.run}`;
  const clock = `${b.t[i].toFixed(2)} s, lab frame ${b.frame_start + i}, ` +
                `${window} lab frames ${b.frame_start + S.span.start} to ${b.frame_start + S.span.end}`;
  const speed = b.speed[i] === null ? "n/a" : `${b.speed[i].toFixed(2)} ${b.units}/s`;
  const live = `phase: ${b.phase[i] || "n/a"}, speed: ${speed}, arrow: ${degrees(arrowAngle(b, i))} (${S.arrow}), ` +
               `motion: ${degrees(b.motion[i])}`;
  return [figure(), strip(), i, clock, live, offsetLine(b), S.playing ? "pause" : "play", !S.playing];
}

let keyCount = 0;
document.addEventListener("keydown", (event) => {
  if (["INPUT", "TEXTAREA"].includes(event.target.tagName)) return;
  const key = event.key;
  if (key === " " || key === "ArrowLeft" || key === "ArrowRight") {
    event.preventDefault();
    dash_clientside.set_props("keys", {data: {key: key, shift: event.shiftKey, n: ++keyCount}});
  } else if (key === "[" || key === "]") {
    dash_clientside.set_props("run-keys", {data: {step: key === "[" ? -1 : 1, n: ++keyCount}});
  } else if (TAG_KEYS[key]) {
    dash_clientside.set_props("tag", {value: TAG_KEYS[key]});
  }
});

window.dash_clientside = Object.assign({}, window.dash_clientside, {viewer: {tick: tick}});
