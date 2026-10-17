import type { BlockHeader, Span, WindowSettings } from "../api/types";
import { colourOf } from "./layers";
import { FRAMES_LANE, runFill, runKind } from "./lanes";
import type { Bar, FrameLayer, LaneSpec, Scene } from "./lanes";

export const BLOCK_LANES: readonly LaneSpec[] = [
  { name: "runs", weight: 2 }, { name: FRAMES_LANE, weight: 3 }, { name: "trips", weight: 1.5 }, { name: "windows", weight: 3 },
];

const TRIP_COLOUR = "#8c6bb1";
const ONE_LIGHT_COLOUR = "#9ca3af";

// Windows overlap, so they sit in as many rows as overlap, at most this many. A window's burn-in is drawn lighter than
// the rest of it and its horizon, the future position it predicts, hatched after it.
const WINDOW_ROWS_MAX = 6;
const BODY_ALPHA = 0.85;

// The heading bands at the bottom of the frames lane (a fraction of the lane) with the one light band just above.
const HEADING_BAND = 0.14;

// The block's arrays are counted from 0, the timeline's frames from 1.
const frameOf = (index: number): number => index + 1;
const asFrames = ([first, last]: Span): Span => [frameOf(first), frameOf(last)];

/** How many rows the windows lane staggers its bars over: as many as windows overlap, at least one. */
export function windowRows(settings: Pick<WindowSettings, "window_s" | "horizon_s" | "stride_s">): number {
  return Math.min(WINDOW_ROWS_MAX, Math.max(1, Math.ceil((settings.window_s + settings.horizon_s) / settings.stride_s)));
}

function runBars(header: BlockHeader): Bar[] {
  return header.runs.map((r) => ({
    lane: "runs", first: frameOf(r.first), last: frameOf(r.last), fill: runFill(r.path_id), hatched: !r.clean,
    tip: `run ${r.run}, path ${r.path_id} ${runKind(r.path_id)}, ${r.clean ? "clean" : "dirty"}, ${((r.last - r.first + 1) / header.rate_hz).toFixed(1)} s from ${(r.first / header.rate_hz).toFixed(1)} s`,
  }));
}

/** A trip is hatched when partial, the stub of a trip at a block's edge. */
function tripBars(header: BlockHeader): Bar[] {
  return header.trips.map((t) => ({
    lane: "trips", first: frameOf(t.first), last: frameOf(t.last), fill: TRIP_COLOUR, hatched: t.partial, text: String(t.trip),
    tip: `trip ${t.trip}, ${t.partial ? "partial" : "complete"}, ${((t.last - t.first + 1) / header.rate_hz).toFixed(1)} s`,
  }));
}

/** Each window as its burn-in, the rest of it and its horizon in one row, red when the window is in trouble. */
function windowBars(header: BlockHeader): Bar[] {
  const { windows, settings, rate_hz } = header;
  const rows = windowRows(settings);
  return windows.flatMap((w) => {
    const name = `window ${w.index + 1}`;
    const place = { lane: "windows", rows, row: w.index % rows };
    const fill = w.ok ? "accent" : "bad";
    const parts: Bar[] = [
      { ...place, first: frameOf(w.first), last: w.burn_in_stop, fill, light: true, tip: `${name} burn-in, ${settings.burn_in_s} s` },
      {
        ...place, first: frameOf(w.burn_in_stop), last: w.window_stop, fill, alpha: BODY_ALPHA, text: String(w.index + 1), pick: w.index,
        tip: `${name} from ${(w.first / rate_hz).toFixed(1)} s, ${settings.window_s} s, ${w.ok ? "ok" : "trouble"}`,
      },
      { ...place, first: frameOf(w.window_stop), last: w.stop, fill: "warn", hatched: true, tip: `${name} horizon, ${settings.horizon_s} s` },
    ];
    return parts.filter((bar) => bar.last >= bar.first);
  });
}

/** The frames lane: the one light stretches and the filled and held heading bands, then the speed trace over them. */
function frameLayers(header: BlockHeader, speed: Float64Array, speedTop: number): FrameLayer[] {
  const band = (spans: Span[], colour: string, from: number, to: number): FrameLayer => ({ kind: "span", spans: spans.map(asFrames), colour, alpha: 1, from, to });
  return [
    band(header.one_light, ONE_LIGHT_COLOUR, 1 - 2 * HEADING_BAND, 1 - HEADING_BAND),
    band(header.heading_filled, colourOf("filled"), 1 - HEADING_BAND, 1),
    band(header.heading_held, colourOf("held"), 1 - HEADING_BAND, 1),
    { kind: "trace", values: speed, top: speedTop },
  ];
}

/** A block's timeline: its runs, the frames lane, its trips and the windows at the settings the header was made at. */
export function blockScene(header: BlockHeader, speed: Float64Array, speedTop: number): Scene {
  return {
    lanes: BLOCK_LANES, rateHz: header.rate_hz, nFrames: header.n_frames,
    bars: [...runBars(header), ...tripBars(header), ...windowBars(header)], frames: frameLayers(header, speed, speedTop),
  };
}
