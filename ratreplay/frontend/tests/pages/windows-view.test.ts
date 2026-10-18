import { expect, test } from "vitest";
import type { BlockHeader, BlockWindow } from "../../src/api/types";
import { jumpTarget, stepWindow, windowsOk, windowStretches, windowVerdict } from "../../src/pages/windows-view";

const header = { rate_hz: 60, row: { n_frames: 1200 } } as unknown as BlockHeader;
const window = (extra: Partial<BlockWindow> = {}): BlockWindow => ({
  index: 0, first: 600, burn_in_stop: 660, window_stop: 900, stop: 930, position_finite: 1, heading_measured: 0.9, trips_complete: 1, trips_partial: 1, ok: true, start_s: 10, stop_s: 15.5, reason: null, ...extra,
});

test("a step moves one window and stops at the first and the last", () => {
  expect(stepWindow(2, 1, 5)).toBe(3);
  expect(stepWindow(2, -1, 5)).toBe(1);
  expect(stepWindow(0, -1, 5)).toBe(0);
  expect(stepWindow(4, 1, 5)).toBe(4);
});

test("a jump names a window by its number from 1 and refuses anything else", () => {
  expect(jumpTarget(1, 5)).toBe(0);
  expect(jumpTarget(5, 5)).toBe(4);
  expect(jumpTarget("3", 5)).toBe(2);
  for (const typed of [0, 6, 2.5, "", "abc", null, -1]) expect(jumpTarget(typed, 5)).toBeNull();
});

test("a window is ok or in trouble as the server's row says, whatever its measures", () => {
  expect(windowVerdict(window())).toBe("window ok");
  expect(windowVerdict(window({ ok: false, reason: "the server's reason" }))).toBe("window trouble, the server's reason");
  expect(windowVerdict(window({ ok: true, heading_measured: 0, position_finite: 0 }))).toBe("window ok");
  expect(windowsOk([window(), window({ ok: false, heading_measured: 1 }), window()])).toBe(2);
});

test("the map draws the whole path, the burn-in lighter, the rest of the window and the horizon, each starting where the last ended", () => {
  const stretches = windowStretches(header, window());
  expect(stretches.map((s) => [s.first, s.last, s.colour])).toEqual([[1, 1200, "ink"], [601, 660, "accent"], [660, 900, "accent"], [900, 930, "warn"]]);
  expect(stretches.map((s) => s.light ?? false)).toEqual([false, true, false, false]);
});
