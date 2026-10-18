import { expect, test } from "vitest";
import { fitScales } from "../../src/draw/map";

const EXTENT = { x: [0, 2] as [number, number], y: [0, 1] as [number, number] };
const PAD_PX = 16;

test("the scales are equal in x and y, the extent is centred in the box and the smaller side limits the scale", () => {
  const { x, y } = fitScales(EXTENT, 400, 300, true);
  expect(Math.abs(x(1) - x(0))).toBeCloseTo(Math.abs(y(1) - y(0)));
  expect(x(2) - x(0)).toBeCloseTo(400 - 2 * PAD_PX);
  expect((x(0) + x(2)) / 2).toBeCloseTo(200);
  expect((y(0) + y(1)) / 2).toBeCloseTo(150);
  const wide = fitScales(EXTENT, 1000, 100, true);
  expect(Math.abs(wide.y(1) - wide.y(0))).toBeCloseTo(100 - 2 * PAD_PX);
});

test("y runs up the screen for a room and down it for a camera image", () => {
  const room = fitScales(EXTENT, 400, 300, true);
  const camera = fitScales(EXTENT, 400, 300, false);
  expect(room.y(1)).toBeLessThan(room.y(0));
  expect(camera.y(1)).toBeGreaterThan(camera.y(0));
  expect(room.x(1)).toBeCloseTo(camera.x(1));
});
