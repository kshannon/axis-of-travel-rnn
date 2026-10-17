import { expect, test } from "vitest";
import { speedTop } from "./speed";

test("the speed scale is a high percentile of the finite speeds, one when there are none", () => {
  const speeds = Float64Array.from({ length: 101 }, (_, i) => i);
  expect(speedTop(speeds)).toBe(95);
  expect(speedTop(new Float64Array([NaN, NaN]))).toBe(1);
  expect(speedTop(new Float64Array(10))).toBe(1);
});
