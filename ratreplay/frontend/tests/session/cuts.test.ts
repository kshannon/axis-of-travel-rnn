import { expect, test } from "vitest";
import type { SessionHeader } from "../../src/api/types";
import { cutsOf, splitAtPauses } from "../../src/session/cuts";

test("a span that holds the frames on both sides of a pause is split between them, one that does not is left as it is", () => {
  // the pause at frame 101 lies between frames 100 and 101
  expect(splitAtPauses([[50, 150]], [101])).toEqual([[50, 100], [101, 150]]);
  expect(splitAtPauses([[50, 100], [101, 150], [200, 300]], [101])).toEqual([[50, 100], [101, 150], [200, 300]]);
  expect(splitAtPauses([[101, 101], [100, 101]], [101])).toEqual([[101, 101], [100, 100], [101, 101]]);
});

test("a span over several pauses is split at each, whatever order the pauses come in", () => {
  expect(splitAtPauses([[1, 400]], [301, 101, 201])).toEqual([[1, 100], [101, 200], [201, 300], [301, 400]]);
  expect(splitAtPauses([[1, 400]], [])).toEqual([[1, 400]]);
});

test("the cuts the lanes read keep the pauses as the frame after each", () => {
  const header = { cut_points: [{ frame: 2701, reason: "pause" }, { frame: 3000, reason: "jump" }], margins: [] } as unknown as SessionHeader;
  expect(cutsOf(header).pauses).toEqual([2701]);
});
