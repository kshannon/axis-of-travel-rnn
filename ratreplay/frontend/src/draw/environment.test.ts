import { expect, test } from "vitest";
import type { Geometry } from "../api/types";
import { extentOf } from "./environment";

const TRACK: Geometry = {
  name: "triple_t", kind: "triple_t", room: [1.8, 1.8], boundary: null, circle: null,
  walls: [[[0.86, 0.355], [0.86, 0.785]], [[0.94, 0.355], [0.94, 0.785]]],
  centerline: [{ name: "stem", p0: [0.9, 0.315], p1: [0.9, 0.825], axis_deg: 90 }],
  reward_sites: { start: [0.9, 0.315], g_ee: [1.48, 1.135] },
};
const none = new Float64Array(0);

test("the extent covers the walls, the centerline and the reward sites", () => {
  expect(extentOf(TRACK, none, none)).toEqual({ x: [0.86, 1.48], y: [0.315, 1.135] });
});

test("a path that strays off the environment widens the extent and a lost position is skipped", () => {
  const x = new Float64Array([0.9, NaN, 2.0]);
  const y = new Float64Array([0.5, 9, -0.2]);
  expect(extentOf(TRACK, x, y)).toEqual({ x: [0.86, 2.0], y: [-0.2, 1.135] });
});

test("an arena is covered by its circle", () => {
  const arena: Geometry = { ...TRACK, walls: [], centerline: [], reward_sites: {}, circle: { center: [0.9, 0.9], radius: 0.5 } };
  expect(extentOf(arena, none, none)).toEqual({ x: [0.4, 1.4], y: [0.4, 1.4] });
});
