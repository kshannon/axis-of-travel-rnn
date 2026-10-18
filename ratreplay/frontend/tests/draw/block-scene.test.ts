import { expect, test } from "vitest";
import type { BlockHeader, BlockWindow, WindowSettings } from "../../src/api/types";
import { blockScene } from "../../src/draw/block-scene";

const SETTINGS: WindowSettings = {
  window_s: 5, stride_s: 2.5, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1,
};

const window = (index: number, ok = true): BlockWindow => ({
  index, first: 150 * index, burn_in_stop: 150 * index + 60, window_stop: 150 * index + 300, stop: 150 * index + 330,
  start_s: 2.5 * index, stop_s: 2.5 * index + 5.5, position_finite: 1, heading_measured: ok ? 1 : 0.636, trips_complete: 1, trips_partial: 0, ok,
  reason: ok ? null : "reason from the server",
});

const header = {
  row: { n_frames: 1200 }, rate_hz: 60,
  runs: [{ run: 1, path_id: 1, clean: true, first: 99, last: 199 }],
  trips: [{ trip: 1, partial: true, first: 0, last: 98 }, { trip: 2, partial: false, first: 99, last: 498 }],
  heading_filled: [[10, 19]], heading_held: [], one_light: [[699, 818]],
} as unknown as BlockHeader;

const scene = (settings = SETTINGS, windows = [window(0), window(1, false)]) => blockScene(header, windows, settings, new Float64Array(10), 1);
const lane = (name: string, settings = SETTINGS, windows = [window(0), window(1, false)]) => scene(settings, windows).bars.filter((bar) => bar.lane === name);

test("a window is its burn-in, the rest of it and its horizon in frames from one, red with the server's reason when the server says so", () => {
  const bars = lane("windows");
  expect(bars.map((bar) => [bar.first, bar.last])).toEqual([[1, 60], [61, 300], [301, 330], [151, 210], [211, 450], [451, 480]]);
  expect(bars.map((bar) => bar.hatched ?? false)).toEqual([false, false, true, false, false, true]);
  expect(bars.map((bar) => bar.light ?? false)).toEqual([true, false, false, true, false, false]);
  expect(bars.map((bar) => bar.fill)).toEqual(["accent", "accent", "warn", "bad", "bad", "warn"]);
  expect(bars[1].pick).toBe(0);
  expect(bars[1].tip).toBe("window 1 from 0.0 s, 5 s, ok");
  expect(bars[4].tip).toBe("window 2 from 2.5 s, 5 s, trouble, reason from the server");
});

test("runs and trips are in frames from one and a partial trip is hatched", () => {
  expect(lane("runs").map((bar) => [bar.first, bar.last, bar.hatched])).toEqual([[100, 200, false]]);
  expect(lane("trips").map((bar) => [bar.first, bar.last, bar.hatched, bar.text])).toEqual([[1, 99, true, "1"], [100, 499, false, "2"]]);
  expect(lane("trips")[0].tip).toBe("trip 1, partial, 1.6 s");
});
