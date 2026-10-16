import { expect, test } from "vitest";
import cases from "./fixtures/windows.json";
import { windowCount } from "./windows";

test("the window counts equal the project's window_count on every case of the fixture", () => {
  expect(cases.length).toBeGreaterThan(30);
  for (const { n_frames, rate_hz, windows, ...settings } of cases) {
    expect(windowCount(n_frames, rate_hz, settings), JSON.stringify({ n_frames, rate_hz, ...settings })).toBe(windows);
  }
});
