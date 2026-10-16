import { scaleLinear, zoomIdentity } from "d3";
import type { ScaleLinear, ZoomTransform } from "d3";
import type { Epoch, ReviewBlock, Run } from "../api/types";

export type Lane = "session" | "runs" | "frames" | "blocks";
export const LANES: readonly Lane[] = ["session", "runs", "frames", "blocks"];

// The lanes share the plot's height by these weights with a gap between them. The plot leaves room at the left for the
// lane names and under the lanes for the time axis.
const LANE_WEIGHTS: Record<Lane, number> = { session: 1, runs: 2, frames: 3, blocks: 2 };
const LANE_GAP_PX = 4;
export const PLOT = { left: 72, right: 12, top: 4, bottom: 22 };

// A bar is never thinner than this, and a click this close to a bar still hits it.
const MIN_BAR_PX = 2;
const HIT_SLOP_PX = 1;

// The closest zoom shows this many seconds. A cursor that leaves the window pages it so the cursor lands this fraction
// of the window from the edge it crossed.
const MIN_SPAN_S = 5;
const PAGE_MARGIN = 0.1;

// The paths of the lab's tasks: the outbound runs and the return runs, any other path is neither.
const OUTBOUND_PATHS = [1, 2, 3, 4];
const RETURN_PATHS = [9, 10];

const TICK_STEPS_S = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];
const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;

export type Scale = ScaleLinear<number, number>;
interface Band {
  top: number;
  bottom: number;
}
export type Bands = Record<Lane, Band>;

export type Bar =
  | { lane: "session"; first: number; last: number; epoch: Epoch }
  | { lane: "runs"; first: number; last: number; run: Run }
  | { lane: "blocks"; first: number; last: number; block: ReviewBlock; name: string };

export const blockName = (position: number): string => `block ${position + 1}`;

export function runKind(pathId: number): "outbound" | "return" | "other" {
  if (OUTBOUND_PATHS.includes(pathId)) return "outbound";
  return RETURN_PATHS.includes(pathId) ? "return" : "other";
}

/** The vertical band of each lane in a canvas of this height. */
export function laneBands(height: number): Bands {
  const room = height - PLOT.top - PLOT.bottom - LANE_GAP_PX * (LANES.length - 1);
  const unit = room / LANES.reduce((total, lane) => total + LANE_WEIGHTS[lane], 0);
  const bands = {} as Bands;
  let top = PLOT.top;
  for (const lane of LANES) {
    bands[lane] = { top, bottom: top + unit * LANE_WEIGHTS[lane] };
    top = bands[lane].bottom + LANE_GAP_PX;
  }
  return bands;
}

export function laneAt(bands: Bands, y: number): Lane | null {
  return LANES.find((lane) => y >= bands[lane].top && y <= bands[lane].bottom) ?? null;
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

/** The bars of the session, runs and blocks lanes. A block is named by its place in time order. */
export function barsOf(epochs: Epoch[], runs: Run[], blocks: ReviewBlock[]): Bar[] {
  return [
    ...epochs.map((epoch): Bar => ({ lane: "session", first: epoch.frame_start, last: epoch.frame_end, epoch })),
    ...runs.map((run): Bar => ({ lane: "runs", first: run.frame_start, last: run.frame_end, run })),
    ...blocks.map((block, position): Bar => ({ lane: "blocks", first: block.frame_start, last: block.frame_end, block, name: blockName(position) })),
  ];
}

/** The bar under a point, none over a gap, the axis or empty lane. */
export function hitBar(bars: Bar[], bands: Bands, scale: Scale, rateHz: number, point: { x: number; y: number }): Bar | null {
  const lane = laneAt(bands, point.y);
  return bars.find((bar) => {
    const [x0, x1] = barSpan(scale, bar, rateHz);
    return bar.lane === lane && point.x >= x0 - HIT_SLOP_PX && point.x <= x1 + HIT_SLOP_PX;
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

/** What a hover tells of a bar: for a run its number, path, clean or dirty and frames. */
export function describeBar(bar: Bar, rateHz: number, flagged = false): string {
  const frames = bar.last - bar.first + 1;
  const where = `frames ${bar.first} to ${bar.last}`;
  switch (bar.lane) {
    case "runs":
      return `run ${bar.run.run}, path ${bar.run.path_id} ${runKind(bar.run.path_id)}, ${bar.run.clean ? "clean" : "dirty"}${flagged ? ", flagged" : ""}, ${frames} frames (${bar.first} to ${bar.last})`;
    case "blocks":
      return `${bar.name}, ${bar.block.status}, ${where}, ${(frames / rateHz).toFixed(1)} s`;
    case "session":
      return `${bar.epoch.epoch}, ${bar.epoch.environment}, ${bar.epoch.condition}, ${where}, ${(frames / rateHz / SECONDS_PER_MINUTE).toFixed(1)} min`;
  }
}
