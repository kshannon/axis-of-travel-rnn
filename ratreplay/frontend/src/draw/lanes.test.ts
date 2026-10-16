import { expect, test } from "vitest";
import type { Epoch, ReviewBlock, Run } from "../api/types";
import { barSpan, describeBar, barsOf, baseScale, hitBar, indexAt, inPlot, keepVisible, laneAt, laneBands, LANES, PLOT, runKind, timeLabel, timeTicks, windowTransform, zoomLimits } from "./lanes";

const RATE_HZ = 60;
const N_FRAMES = 36_000; // ten minutes
const WIDTH = 1000;
const HEIGHT = 200;
const base = baseScale(N_FRAMES / RATE_HZ, WIDTH);

const epoch: Epoch = { epoch: "track", environment: "triple_t", condition: "baseline", frame_start: 1, frame_end: N_FRAMES, duration_s: 600 };
const run: Run = { run: 1, epoch: "track", path_id: 1, clean: true, frame_start: 6001, frame_end: 6600 };
const block: ReviewBlock = { block_id: "S_track_01", epoch: "track", environment: "triple_t", frame_start: 3001, frame_end: 9000, status: "auto", note: "" };
const bars = barsOf([epoch], [run], [block]);
const bands = laneBands(HEIGHT);
const middle = (lane: (typeof LANES)[number]) => (bands[lane].top + bands[lane].bottom) / 2;

test("the whole session spans the plot and a pixel maps back to its second", () => {
  expect(base(0)).toBe(PLOT.left);
  expect(base(600)).toBe(WIDTH - PLOT.right);
  expect(base.invert(base(123.5))).toBeCloseTo(123.5);
});

test("under a zoom a time and its pixel map both ways and a click lands on the frame under it", () => {
  const transform = windowTransform(base, 120, 180);
  const scale = transform.rescaleX(base);
  expect(scale.domain()[0]).toBeCloseTo(120);
  expect(scale.domain()[1]).toBeCloseTo(180);
  expect(scale(150)).toBeCloseTo((PLOT.left + WIDTH - PLOT.right) / 2);
  expect(scale.invert(scale(133.25))).toBeCloseTo(133.25);
  expect(indexAt(scale, scale(150), RATE_HZ, N_FRAMES)).toBe(150 * RATE_HZ);
  expect(indexAt(base, -500, RATE_HZ, N_FRAMES)).toBe(0);
  expect(indexAt(base, 5000, RATE_HZ, N_FRAMES)).toBe(N_FRAMES - 1);
});

test("a window is never closer than the closest zoom nor past the session", () => {
  const closest = windowTransform(base, 100, 101).rescaleX(base).domain();
  expect(closest[0]).toBeCloseTo(98);
  expect(closest[1]).toBeCloseTo(103);
  const whole = windowTransform(base, -50, 5000);
  expect([whole.k, whole.x]).toEqual([1, 0]);
  const end = windowTransform(base, 590, 700).rescaleX(base).domain();
  expect(end[1]).toBeCloseTo(600);
  expect(zoomLimits(600)).toEqual([1, 120]);
  expect(zoomLimits(2)).toEqual([1, 1]);
});

test("the lanes fill the plot in order and a height finds its lane", () => {
  expect(bands.session.top).toBe(PLOT.top);
  expect(bands.blocks.bottom).toBeCloseTo(HEIGHT - PLOT.bottom);
  for (let i = 1; i < LANES.length; i++) expect(bands[LANES[i]].top).toBeGreaterThan(bands[LANES[i - 1]].bottom);
  expect(bands.frames.bottom - bands.frames.top).toBeCloseTo(1.5 * (bands.runs.bottom - bands.runs.top));
  expect(LANES.map((lane) => laneAt(bands, middle(lane)))).toEqual([...LANES]);
  expect(laneAt(bands, (bands.runs.bottom + bands.frames.top) / 2)).toBeNull();
  expect(inPlot({ x: 500, y: middle("runs") }, WIDTH, HEIGHT)).toBe(true);
  expect(inPlot({ x: 10, y: middle("runs") }, WIDTH, HEIGHT)).toBe(false);
  expect(inPlot({ x: 500, y: HEIGHT - 2 }, WIDTH, HEIGHT)).toBe(false);
});

test("a click finds the block bar or the run bar under it and nothing outside them", () => {
  const [b0, b1] = barSpan(base, bars[2], RATE_HZ);
  expect([b0, b1].map((x) => Math.round(base.invert(x)))).toEqual([50, 150]);
  expect(hitBar(bars, bands, base, RATE_HZ, { x: (b0 + b1) / 2, y: middle("blocks") })?.lane).toBe("blocks");
  expect(hitBar(bars, bands, base, RATE_HZ, { x: b1 + 5, y: middle("blocks") })).toBeNull();
  const x = base(105);
  expect(hitBar(bars, bands, base, RATE_HZ, { x, y: middle("runs") })).toMatchObject({ lane: "runs", run: { run: 1 } });
  expect(hitBar(bars, bands, base, RATE_HZ, { x, y: middle("frames") })).toBeNull();
  expect(hitBar(bars, bands, base, RATE_HZ, { x, y: middle("session") })).toMatchObject({ lane: "session" });
});

test("a bar too short to see is still two pixels wide and can be hit", () => {
  const blink: Run = { ...run, run: 2, frame_start: 100, frame_end: 100 };
  const tiny = barsOf([], [blink], []);
  const [x0, x1] = barSpan(base, tiny[0], RATE_HZ);
  expect(x1 - x0).toBe(2);
  expect(hitBar(tiny, bands, base, RATE_HZ, { x: x0 + 1, y: middle("runs") })).not.toBeNull();
});

test("blocks are named by their place in time order", () => {
  const later: ReviewBlock = { ...block, frame_start: 20_000, frame_end: 25_000 };
  const named = barsOf([], [], [block, later]).filter((bar) => bar.lane === "blocks").map((bar) => bar.lane === "blocks" && bar.name);
  expect(named).toEqual(["block 1", "block 2"]);
});

test("a cursor past the window pages the window to it, one inside leaves the zoom alone", () => {
  const zoomed = windowTransform(base, 120, 180);
  expect(keepVisible(zoomed, base, 150)).toBe(zoomed);
  const paged = keepVisible(zoomed, base, 181).rescaleX(base).domain();
  expect(paged[0]).toBeCloseTo(181 - 6);
  expect(paged[1] - paged[0]).toBeCloseTo(60);
  const back = keepVisible(zoomed, base, 119).rescaleX(base).domain();
  expect(back[1]).toBeCloseTo(119 + 6);
});

test("the lab's paths are outbound or return", () => {
  expect([1, 4, 9, 10, 5].map(runKind)).toEqual(["outbound", "outbound", "return", "return", "other"]);
});

test("ticks are round seconds inside the window and labels read as a clock", () => {
  expect(timeTicks([0, 600], 8)).toEqual([0, 120, 240, 360, 480, 600]);
  expect(timeTicks([95, 125], 3)).toEqual([100, 110, 120]);
  expect(timeTicks([95, 125], 8)).toEqual([95, 100, 105, 110, 115, 120, 125]);
  expect([0, 65, 600, 3725].map(timeLabel)).toEqual(["0:00", "1:05", "10:00", "1:02:05"]);
});

test("a hover names the run with its path, whether it is clean and its frames", () => {
  expect(describeBar(bars[1], RATE_HZ)).toBe("run 1, path 1 outbound, clean, 600 frames (6001 to 6600)");
  expect(describeBar(bars[1], RATE_HZ, true)).toContain("clean, flagged,");
  expect(describeBar(bars[2], RATE_HZ)).toBe("block 1, auto, frames 3001 to 9000, 100.0 s");
  expect(describeBar(bars[0], RATE_HZ)).toBe("track, triple_t, baseline, frames 1 to 36000, 10.0 min");
});
