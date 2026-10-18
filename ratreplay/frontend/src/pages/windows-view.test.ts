import { expect, test } from "vitest";
import type { BlockWindow, WindowSettings } from "../api/types";
import type { BlockView } from "../session/block";
import { jumpTarget, stepWindow, windowChecks, windowsOk, windowSpan, windowStretches } from "./windows-view";

const SETTINGS: WindowSettings = {
  window_s: 5, stride_s: 10, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1,
};
const header = { rate_hz: 60, n_frames: 1200, settings: SETTINGS } as unknown as BlockView;
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

test("the checks of a window pass when the position is whole and the heading reaches the minimum", () => {
  const checks = windowChecks(window(), header);
  expect(checks.map((c) => [c.label, c.status])).toEqual([
    ["position finite", "ok"], ["heading measured", "ok"], ["trips", "info"], ["burn-in and horizon", "ok"],
  ]);
  expect(checks.map((c) => c.value)).toEqual(["100%", "90%", "1 complete, 1 partial", "1 s and 0.5 s"]);
});

test("a window with lost positions or too little heading is in trouble on that check", () => {
  const checks = windowChecks(window({ position_finite: 0.98, heading_measured: 0.6364 }), header);
  expect(checks.map((c) => c.status)).toEqual(["trouble", "trouble", "info", "ok"]);
  expect(checks[1].value).toBe("63.6%");
  expect(checks[1].note).toContain("at least 80%");
  expect(windowChecks(window({ heading_measured: 0.8 }), header)[1].status).toBe("ok");
});

test("a horizon running past the end of the block does not fit, nor does a burn-in longer than the window", () => {
  expect(windowChecks(window({ stop: 1200 }), header)[3].status).toBe("ok");
  expect(windowChecks(window({ stop: 1201 }), header)[3].status).toBe("trouble");
  expect(windowChecks(window({ burn_in_stop: 901 }), header)[3].status).toBe("trouble");
});

test("the span tells where the window lies and the totals count the windows ok", () => {
  expect(windowSpan(window(), 60)).toBe("10.0 s to 15.0 s in the block, horizon to 15.5 s");
  expect(windowsOk([window(), window({ ok: false }), window()])).toBe(2);
});

test("the map draws the whole path, the burn-in lighter, the rest of the window and the horizon, each starting where the last ended", () => {
  const stretches = windowStretches(header, window());
  expect(stretches.map((s) => [s.first, s.last, s.colour])).toEqual([[1, 1200, "ink"], [601, 660, "accent"], [660, 900, "accent"], [900, 930, "warn"]]);
  expect(stretches.map((s) => s.light ?? false)).toEqual([false, true, false, false]);
});
