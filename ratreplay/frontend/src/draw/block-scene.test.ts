import { expect, test } from "vitest";
import type { BlockHeader, BlockWindow, WindowSettings } from "../api/types";
import { blockScene, windowRows } from "./block-scene";

const SETTINGS: WindowSettings = {
  window_s: 5, stride_s: 2.5, burn_in_s: 1, horizon_s: 0.5, train_rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1,
};

const window = (index: number, ok = true): BlockWindow => ({
  index, first: 150 * index, burn_in_stop: 150 * index + 60, window_stop: 150 * index + 300, stop: 150 * index + 330,
  position_finite: 1, heading_measured: 1, trips_complete: 1, trips_partial: 0, ok,
});

const header = (settings: WindowSettings, windows: BlockWindow[]) => ({
  rate_hz: 60, n_frames: 1200, settings, windows,
  runs: [{ run: 1, path_id: 1, clean: true, first: 99, last: 199 }],
  trips: [{ trip: 1, partial: true, first: 0, last: 98 }, { trip: 2, partial: false, first: 99, last: 498 }],
  heading_filled: [[10, 19]], heading_held: [], one_light: [[699, 818]],
}) as unknown as BlockHeader;

const scene = (settings = SETTINGS, windows = [window(0), window(1, false)]) => blockScene(header(settings, windows), new Float64Array(10), 1);
const lane = (name: string, settings = SETTINGS, windows = [window(0), window(1, false)]) => scene(settings, windows).bars.filter((bar) => bar.lane === name);

test("windows sit in as many rows as overlap, at least one and at most six", () => {
  expect(windowRows(SETTINGS)).toBe(3);
  expect(windowRows({ window_s: 40, horizon_s: 0.5, stride_s: 10 })).toBe(5);
  expect(windowRows({ window_s: 40, horizon_s: 0, stride_s: 100 })).toBe(1);
  expect(windowRows({ window_s: 40, horizon_s: 0, stride_s: 1 })).toBe(6);
});

test("a window is its burn-in, the rest of it and its horizon in frames from one, in the row its number gives", () => {
  const bars = lane("windows");
  expect(bars.map((bar) => [bar.first, bar.last, bar.row, bar.rows])).toEqual([
    [1, 60, 0, 3], [61, 300, 0, 3], [301, 330, 0, 3], [151, 210, 1, 3], [211, 450, 1, 3], [451, 480, 1, 3],
  ]);
  expect(bars.map((bar) => bar.hatched ?? false)).toEqual([false, false, true, false, false, true]);
  expect(bars.map((bar) => bar.light ?? false)).toEqual([true, false, false, true, false, false]);
  expect(bars.map((bar) => bar.fill)).toEqual(["accent", "accent", "warn", "bad", "bad", "warn"]);
  expect(bars[1].pick).toBe(0);
  expect(bars[1].tip).toBe("window 1 from 0.0 s, 5 s, ok");
  expect(bars[4].tip).toBe("window 2 from 2.5 s, 5 s, trouble");
});

test("without a burn-in or a horizon those parts are not drawn", () => {
  const plain = { ...SETTINGS, burn_in_s: 0, horizon_s: 0 };
  const bars = lane("windows", plain, [{ ...window(0), burn_in_stop: 0, stop: 300 }]);
  expect(bars.map((bar) => [bar.first, bar.last])).toEqual([[1, 300]]);
});

test("runs and trips are in frames from one and a partial trip is hatched", () => {
  expect(lane("runs").map((bar) => [bar.first, bar.last, bar.hatched])).toEqual([[100, 200, false]]);
  expect(lane("trips").map((bar) => [bar.first, bar.last, bar.hatched, bar.text])).toEqual([[1, 99, true, "1"], [100, 499, false, "2"]]);
  expect(lane("trips")[0].tip).toBe("trip 1, partial, 1.6 s");
});

test("the frames lane holds the one light and heading bands, then the speed trace", () => {
  const { frames } = scene();
  expect(frames.map((layer) => layer.kind)).toEqual(["span", "span", "span", "trace"]);
  expect(frames[0]).toMatchObject({ spans: [[700, 819]] });
  expect(frames[1]).toMatchObject({ spans: [[11, 20]] });
});
