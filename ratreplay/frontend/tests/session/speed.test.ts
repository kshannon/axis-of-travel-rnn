import { expect, test } from "vitest";
import { speedTop } from "../../src/session/speed";

test("a few tracking spikes do not set the speed scale, a lost position is ignored and a session with no speed has a scale of one", () => {
  const speeds = new Float64Array(1000).fill(0.5);
  speeds[10] = 400;
  speeds[11] = NaN;
  expect(speedTop(speeds)).toBe(0.5);
  expect(speedTop(new Float64Array([NaN, NaN]))).toBe(1);
  expect(speedTop(new Float64Array(10))).toBe(1);
});
