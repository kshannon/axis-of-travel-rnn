import { expect, test } from "vitest";
import { degrees, percent } from "../../src/ui/format";

test("a share is a percent with the decimals asked for and none left over", () => {
  expect([0.9, 0.6364, 1, 0.004].map((share) => percent(share))).toEqual(["90%", "64%", "100%", "0%"]);
  expect([0.9, 0.6364, 1].map((share) => percent(share, 1))).toEqual(["90%", "63.6%", "100%"]);
});

test("an angle is degrees and a rotation of a hair under zero is 0", () => {
  expect(degrees(Math.PI)).toBe("180 deg");
  expect(degrees(3.0642, 1)).toBe("175.6 deg");
  expect(degrees(-1e-9, 1)).toBe("0 deg");
});
