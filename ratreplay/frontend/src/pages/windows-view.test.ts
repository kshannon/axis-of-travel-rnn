import { expect, test } from "vitest";
import type { BlockHeader, BlockWindow, WindowSettings } from "../api/types";
import { jumpTarget, stepWindow, windowChecks, windowsOk, windowSpan, windowStretches, windowVerdict } from "./windows-view";

const SETTINGS: WindowSettings = {
  window_s: 5, stride_s: 10, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1,
};
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

test("the checks of a window show what its row measured and the settings it is held to, and decide nothing", () => {
  const checks = windowChecks(window({ position_finite: 0.98, heading_measured: 0.6364 }), SETTINGS);
  expect(checks.map((c) => [c.label, c.value])).toEqual([
    ["position finite", "98%"], ["heading measured", "63.6%"], ["trips", "1 complete, 1 partial"], ["burn-in and horizon", "1 s and 0.5 s"],
  ]);
  expect(checks[1].note).toContain("at least 80%");
  expect(Object.keys(checks[0])).toEqual(["label", "value", "note"]);
});

test("a window says what the server says of it, ok or in trouble with its reason", () => {
  expect(windowVerdict(window())).toBe("window ok");
  expect(windowVerdict(window({ ok: false, reason: "measured heading 64% under 80%" }))).toBe("window trouble, measured heading 64% under 80%");
});

test("the span tells where the window lies from its row and the totals count the windows ok", () => {
  expect(windowSpan(window())).toBe("10.0 s to 15.5 s in the block, the window and its horizon");
  expect(windowsOk([window(), window({ ok: false }), window()])).toBe(2);
});

test("the map draws the whole path, the burn-in lighter, the rest of the window and the horizon, each starting where the last ended", () => {
  const stretches = windowStretches(header, window());
  expect(stretches.map((s) => [s.first, s.last, s.colour])).toEqual([[1, 1200, "ink"], [601, 660, "accent"], [660, 900, "accent"], [900, 930, "warn"]]);
  expect(stretches.map((s) => s.light ?? false)).toEqual([false, true, false, false]);
});
