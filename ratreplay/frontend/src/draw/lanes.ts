import { scaleLinear, zoomIdentity } from "d3";
import type { ScaleLinear, ZoomTransform } from "d3";
import type { Span } from "../api/types";

/** A lane of the timeline, named at its left, with its share of the plot's height. */
export interface LaneSpec {
  name: string;
  weight: number;
}

// The lanes share the plot's height by their weights with a gap between them. The plot leaves room at the left for the
// lane names and under the lanes for the time axis.
const LANE_GAP_PX = 4;
export const PLOT = { left: 72, right: 12, top: 4, bottom: 22 };

// A bar is never thinner than this, and a click this close to a bar still hits it. A bar sits this far in from the edges of its lane.
const MIN_BAR_PX = 2;
const HIT_SLOP_PX = 1;
export const BAR_INSET_PX = 1;

// The closest zoom shows this many seconds. A cursor that leaves the window pages it so the cursor lands this fraction
// of the window from the edge it crossed.
const MIN_SPAN_S = 5;
const PAGE_MARGIN = 0.1;

// The paths of the lab's tasks: the outbound runs and the return runs, any other path is neither.
const OUTBOUND_PATHS = [1, 2, 3, 4];
const RETURN_PATHS = [9, 10];
const RUN_COLOURS = { outbound: "#3b82f6", return: "#93c5fd", other: "#9ca3af" };

const TICK_STEPS_S = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];
const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;

export type Scale = ScaleLinear<number, number>;
interface Band {
  top: number;
  bottom: number;
}
export type Bands = Record<string, Band>;

/** A bar of a lane over lab frames counted from 1, both ends included. */
export interface Bar {
  lane: string;
  first: number;
  last: number;
  /** A palette colour name or a CSS colour. */
  fill: string;
  alpha?: number;
  /** Drawn in a lighter shade of its colour. */
  light?: boolean;
  text?: string;
  hatched?: boolean;
  /** A palette colour name. */
  outline?: string;
  /** Bars that overlap in time sit in rows of their lane, this one in row `row` of `rows`. */
  row?: number;
  rows?: number;
  /** What a hover says of the bar. */
  tip: string;
  /** A click selects the bar, handing this number to the page, instead of moving the cursor. */
  pick?: number;
}

/** What the frames lane draws, in order. Spans and ticks are over lab frames from 1, `from` and `to` are fractions of the lane's height from its top. */
export type FrameLayer =
  | { kind: "span"; spans: Span[]; colour: string; alpha: number; from: number; to: number }
  | { kind: "tick"; frames: number[]; colour: string; to: number }
  | { kind: "trace"; values: Float64Array; top: number };

/** Everything a timeline draws: its lanes, the bars and the frames lane's layers over a recording of `nFrames` at `rateHz`. */
export interface Scene {
  lanes: readonly LaneSpec[];
  rateHz: number;
  nFrames: number;
  bars: Bar[];
  frames: FrameLayer[];
}

/** The lane the frame layers are drawn in. */
export const FRAMES_LANE = "frames";

export function runKind(pathId: number): "outbound" | "return" | "other" {
  if (OUTBOUND_PATHS.includes(pathId)) return "outbound";
  return RETURN_PATHS.includes(pathId) ? "return" : "other";
}

/** The colour of a run's bar by its path. */
export const runFill = (pathId: number): string => RUN_COLOURS[runKind(pathId)];

/** The vertical band of each lane in a canvas of this height. */
export function laneBands(height: number, lanes: readonly LaneSpec[]): Bands {
  const room = height - PLOT.top - PLOT.bottom - LANE_GAP_PX * (lanes.length - 1);
  const unit = room / lanes.reduce((total, lane) => total + lane.weight, 0);
  const bands: Bands = {};
  let top = PLOT.top;
  for (const { name, weight } of lanes) {
    bands[name] = { top, bottom: top + unit * weight };
    top = bands[name].bottom + LANE_GAP_PX;
  }
  return bands;
}

/** Whether a point of the canvas is over the lanes, the gaps between them included. */
export function inPlot(point: { x: number; y: number }, width: number, height: number): boolean {
  return point.x >= PLOT.left && point.x <= width - PLOT.right && point.y >= PLOT.top && point.y <= height - PLOT.bottom;
}

/** Seconds of recording to pixels with the whole session across the plot. A frame's time is its index over the rate, a pause is a mark and not a stretch. */
export function baseScale(durationS: number, width: number): Scale {
  return scaleLinear().domain([0, durationS]).range([PLOT.left, width - PLOT.right]);
}

/** The frame index nearest to a pixel, clamped to the session. */
export function indexAt(scale: Scale, x: number, rateHz: number, nFrames: number): number {
  return Math.min(Math.max(Math.round(scale.invert(x) * rateHz), 0), nFrames - 1);
}

/** The pixel span of a bar of lab frames, first to last inclusive. */
export function barSpan(scale: Scale, bar: Pick<Bar, "first" | "last">, rateHz: number): [number, number] {
  const x0 = scale((bar.first - 1) / rateHz);
  return [x0, Math.max(scale(bar.last / rateHz), x0 + MIN_BAR_PX)];
}

/** A bar's pixel box (left, top, width, height) in its lane, one row of the lane's rows. */
export function barBox(scale: Scale, bands: Bands, bar: Bar, rateHz: number): [number, number, number, number] {
  const [x0, x1] = barSpan(scale, bar, rateHz);
  const { top, bottom } = bands[bar.lane];
  const height = (bottom - top) / (bar.rows ?? 1);
  return [x0, top + (bar.row ?? 0) * height + BAR_INSET_PX, x1 - x0, height - 2 * BAR_INSET_PX];
}

/** The bar under a point, none over a gap, the axis or an empty part of a lane. */
export function hitBar(bars: Bar[], bands: Bands, scale: Scale, rateHz: number, point: { x: number; y: number }): Bar | null {
  return bars.find((bar) => {
    const [x, y, width, height] = barBox(scale, bands, bar, rateHz);
    return point.x >= x - HIT_SLOP_PX && point.x <= x + width + HIT_SLOP_PX && point.y >= y && point.y <= y + height;
  }) ?? null;
}

export function zoomLimits(durationS: number): [number, number] {
  return [1, Math.max(1, durationS / MIN_SPAN_S)];
}

/** The zoom that shows the window from startS to endS, at least the closest zoom wide and never past the session. */
export function windowTransform(base: Scale, startS: number, endS: number): ZoomTransform {
  const [left, right] = base.range();
  const duration = base.domain()[1];
  const span = Math.min(Math.max(endS - startS, MIN_SPAN_S), duration);
  const k = duration / span;
  const x = left - k * base((startS + endS) / 2 - span / 2);
  return zoomIdentity.translate(Math.min(Math.max(x, right * (1 - k)), left * (1 - k)), 0).scale(k);
}

/** The zoom paged to show the second when it falls outside the window, the same transform when it is inside. */
export function keepVisible(transform: ZoomTransform, base: Scale, seconds: number): ZoomTransform {
  const [from, to] = transform.rescaleX(base).domain();
  if (seconds >= from && seconds <= to) return transform;
  const start = seconds - (to - from) * (seconds > to ? PAGE_MARGIN : 1 - PAGE_MARGIN);
  return windowTransform(base, start, start + (to - from));
}

/** The tick seconds inside the window, at the smallest round step that gives no more than maxTicks. */
export function timeTicks([from, to]: [number, number], maxTicks: number): number[] {
  const step = TICK_STEPS_S.find((s) => (to - from) / s <= maxTicks) ?? TICK_STEPS_S[TICK_STEPS_S.length - 1];
  const ticks: number[] = [];
  for (let t = Math.ceil(from / step) * step; t <= to; t += step) ticks.push(t);
  return ticks;
}

const twoDigits = (n: number) => String(n).padStart(2, "0");

/** Seconds as minutes and seconds, with hours once there are any. */
export function timeLabel(seconds: number): string {
  const whole = Math.round(seconds);
  const hours = Math.floor(whole / SECONDS_PER_HOUR);
  const minutes = Math.floor((whole % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  const rest = twoDigits(whole % SECONDS_PER_MINUTE);
  return hours ? `${hours}:${twoDigits(minutes)}:${rest}` : `${minutes}:${rest}`;
}
