import { scaleLinear } from "d3";
import { expect, test } from "vitest";
import type { Geometry, SessionHeader } from "../../src/api/types";
import { ALL_EPOCHS, defaultMapChoice, environmentsShown, epochsShown, FOLLOW_CURSOR, roomRect, rowsFromTop, scopeOptions } from "../../src/draw/occupancy";

const geometry = (name: string) => ({ name }) as Geometry;
const header = {
  epochs: [
    { epoch: "arena", environment: "open_arena", frame_start: 1, frame_end: 1800 },
    { epoch: "track", environment: "triple_t", frame_start: 1801, frame_end: 3600 },
    { epoch: "variant", environment: "triple_t_rot90", frame_start: 3601, frame_end: 5400 },
  ],
  selected_epochs: ["arena", "track"],
  environments: { open_arena: geometry("open_arena"), triple_t: geometry("triple_t") },
} as unknown as SessionHeader;

// The epoch scope is one choice of four: the epoch under the cursor, one kind, or every selected kind.
test("following the cursor shows the epoch under it, which is the lab frame after the index", () => {
  expect(epochsShown(header, FOLLOW_CURSOR, 0)).toEqual(["arena"]);
  expect(epochsShown(header, FOLLOW_CURSOR, 1800)).toEqual(["track"]);
  expect(epochsShown(header, FOLLOW_CURSOR, 9000)).toEqual([]);
  expect(environmentsShown(header, FOLLOW_CURSOR, 1799)).toEqual(["open_arena"]);
  expect(environmentsShown(header, FOLLOW_CURSOR, 1800)).toEqual(["triple_t"]);
});

test("a kind shows that kind wherever the cursor is, and both shows every selected kind", () => {
  expect(epochsShown(header, "track", 0)).toEqual(["track"]);
  expect(environmentsShown(header, "track", 0)).toEqual(["triple_t"]);
  expect(environmentsShown(header, "arena", 4000)).toEqual(["open_arena"]);
  expect(epochsShown(header, ALL_EPOCHS, 9000)).toEqual(["arena", "track"]);
  expect(environmentsShown(header, ALL_EPOCHS, 0)).toEqual(["open_arena", "triple_t"]);
});

test("an epoch the rules do not cut is never shown, and has no geometry, under any scope", () => {
  expect(epochsShown(header, "variant", 0)).toEqual([]);
  expect(environmentsShown(header, "variant", 0)).toEqual([]);
  expect(epochsShown(header, FOLLOW_CURSOR, 4000)).toEqual([]);
  expect(environmentsShown(header, FOLLOW_CURSOR, 4000)).toEqual([]);
  expect(environmentsShown(header, ALL_EPOCHS, 4000)).not.toContain("triple_t_rot90");
});

test("the scope choices are follow cursor, each selected kind, then both for two kinds and all for more, none for a single kind", () => {
  expect(defaultMapChoice().scope).toBe(FOLLOW_CURSOR);
  expect(scopeOptions(["arena", "track"]).map((o) => [o.value, o.label])).toEqual([[FOLLOW_CURSOR, "follow cursor"], ["arena", "arena"], ["track", "track"], [ALL_EPOCHS, "both"]]);
  expect(scopeOptions(["arena", "track", "variant"]).at(-1)).toMatchObject({ value: ALL_EPOCHS, label: "all" });
  expect(scopeOptions(["track"]).map((o) => o.value)).toEqual([FOLLOW_CURSOR, "track"]);
});

test("the room's image sits on the projected room corners, however much wider than the room the projection reaches", () => {
  // 100 px per metre, x from -1 to 3 m and y from -2 to 2 m, y up the screen: a map widened to a path that strays off the room
  const project = { x: scaleLinear().domain([-1, 3]).range([0, 400]), y: scaleLinear().domain([-2, 2]).range([400, 0]) };
  const room = { x: [0, 1.8] as [number, number], y: [0, 1.8] as [number, number] };
  const rect = roomRect(project, room);
  expect(rect.left).toBeCloseTo(100);
  expect(rect.width).toBeCloseTo(180);
  expect(rect.top).toBeCloseTo(20); // the room's highest y is the top edge
  expect(rect.height).toBeCloseTo(180); // positive, a negative height does not flip an image in a canvas
});

test("the rows of the counts are turned so the row of the lowest y ends up last, at the bottom of the image", () => {
  expect(rowsFromTop([1, 2, 3, 4, 5, 6, 7, 8, 9], 3)).toEqual([7, 8, 9, 4, 5, 6, 1, 2, 3]);
});
