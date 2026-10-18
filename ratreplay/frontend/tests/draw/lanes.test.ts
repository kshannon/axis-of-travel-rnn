import { expect, test } from "vitest";
import { barBox, barSpan, baseScale, hitBar, indexAt, inPlot, keepVisible, laneBands, PLOT, timeLabel, timeTicks, windowTransform, zoomLimits } from "../../src/draw/lanes";
import type { Bar, LaneSpec } from "../../src/draw/lanes";

const RATE_HZ = 60;
const N_FRAMES = 36_000; // ten minutes
const WIDTH = 1000;
const HEIGHT = 200;
const base = baseScale(N_FRAMES / RATE_HZ, WIDTH);

const LANES: LaneSpec[] = [{ name: "session", weight: 1 }, { name: "runs", weight: 2 }, { name: "frames", weight: 3 }, { name: "blocks", weight: 2 }];
const bands = laneBands(HEIGHT, LANES);
const middle = (lane: string) => (bands[lane].top + bands[lane].bottom) / 2;

const bar = (lane: string, first: number, last: number, extra: Partial<Bar> = {}): Bar => ({ lane, first, last, fill: "accent", tip: lane, ...extra });
const epoch = bar("session", 1, N_FRAMES);
const run = bar("runs", 6001, 6600);
const block = bar("blocks", 3001, 9000, { pick: 3001 });
const bars = [epoch, run, block];

test("the whole recording spans the plot and a pixel maps back to its second", () => {
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

test("a window is never closer than the closest zoom nor past the recording", () => {
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

test("the lanes fill the plot in order by their weights", () => {
  expect(bands.session.top).toBe(PLOT.top);
  expect(bands.blocks.bottom).toBeCloseTo(HEIGHT - PLOT.bottom);
  LANES.slice(1).forEach(({ name }, i) => expect(bands[name].top).toBeGreaterThan(bands[LANES[i].name].bottom));
  expect(bands.frames.bottom - bands.frames.top).toBeCloseTo(1.5 * (bands.runs.bottom - bands.runs.top));
  expect(laneBands(HEIGHT, [{ name: "only", weight: 1 }]).only).toEqual({ top: PLOT.top, bottom: HEIGHT - PLOT.bottom });
  expect(inPlot({ x: 500, y: middle("runs") }, WIDTH, HEIGHT)).toBe(true);
  expect(inPlot({ x: 10, y: middle("runs") }, WIDTH, HEIGHT)).toBe(false);
  expect(inPlot({ x: 500, y: HEIGHT - 2 }, WIDTH, HEIGHT)).toBe(false);
});

test("a click finds the block bar or the run bar under it and nothing outside them", () => {
  const [b0, b1] = barSpan(base, block, RATE_HZ);
  expect([b0, b1].map((x) => Math.round(base.invert(x)))).toEqual([50, 150]);
  expect(hitBar(bars, bands, base, RATE_HZ, { x: (b0 + b1) / 2, y: middle("blocks") })).toBe(block);
  expect(hitBar(bars, bands, base, RATE_HZ, { x: b1 + 5, y: middle("blocks") })).toBeNull();
  const x = base(105);
  expect(hitBar(bars, bands, base, RATE_HZ, { x, y: middle("runs") })).toBe(run);
  expect(hitBar(bars, bands, base, RATE_HZ, { x, y: middle("frames") })).toBeNull();
  expect(hitBar(bars, bands, base, RATE_HZ, { x, y: middle("session") })).toBe(epoch);
});

test("bars that overlap in time share their lane in rows, each hit only in its own row", () => {
  const early = bar("runs", 1000, 4000, { row: 0, rows: 3 });
  const late = bar("runs", 2000, 5000, { row: 2, rows: 3 });
  const [, top0, , height0] = barBox(base, bands, early, RATE_HZ);
  const [, top2, , height2] = barBox(base, bands, late, RATE_HZ);
  const rowHeight = (bands.runs.bottom - bands.runs.top) / 3;
  expect(top2 - top0).toBeCloseTo(2 * rowHeight);
  expect(height0).toBeCloseTo(rowHeight - 2);
  expect(height2).toBeCloseTo(height0);
  const x = base(50);
  expect(hitBar([early, late], bands, base, RATE_HZ, { x, y: top0 + height0 / 2 })).toBe(early);
  expect(hitBar([early, late], bands, base, RATE_HZ, { x, y: top2 + height2 / 2 })).toBe(late);
  expect(hitBar([early, late], bands, base, RATE_HZ, { x, y: top0 + rowHeight + height0 / 2 })).toBeNull();
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

test("ticks are round seconds inside the window and labels read as a clock", () => {
  expect(timeTicks([0, 600], 8)).toEqual([0, 120, 240, 360, 480, 600]);
  expect(timeTicks([95, 125], 3)).toEqual([100, 110, 120]);
  expect(timeTicks([95, 125], 8)).toEqual([95, 100, 105, 110, 115, 120, 125]);
  expect([0, 65, 600, 3725].map(timeLabel)).toEqual(["0:00", "1:05", "10:00", "1:02:05"]);
});
