import { scaleLinear } from "d3";
import { expect, test } from "vitest";
import type { Geometry, SessionHeader } from "../../src/api/types";
import { defaultMapChoice, environmentsShown, epochsShown, roomRect, rowsFromTop } from "../../src/draw/occupancy";
import type { MapChoice } from "../../src/draw/occupancy";

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

// Every layer is its own choice: the kinds on, and with follow only the epoch under the cursor.
const choice = (changes: Partial<MapChoice> = {}): MapChoice => ({ ...defaultMapChoice(), kinds: { arena: true, track: true }, ...changes });

test("following the cursor shows the epoch under it, which is the lab frame after the index", () => {
  expect(epochsShown(header, choice(), 0)).toEqual(["arena"]);
  expect(epochsShown(header, choice(), 1800)).toEqual(["track"]);
  expect(epochsShown(header, choice(), 9000)).toEqual([]);
  expect(environmentsShown(header, choice(), 1799)).toEqual(["open_arena"]);
  expect(environmentsShown(header, choice(), 1800)).toEqual(["triple_t"]);
});

test("without following, each epoch kind that is on shows, and an epoch the rules do not cut has no geometry", () => {
  const all = choice({ follow: false });
  expect(epochsShown(header, all, 0)).toEqual(["arena", "track"]);
  expect(environmentsShown(header, all, 0)).toEqual(["open_arena", "triple_t"]);
  expect(environmentsShown(header, choice({ follow: false, kinds: { arena: false, track: true } }), 0)).toEqual(["triple_t"]);
  expect(environmentsShown(header, choice({ follow: false, kinds: { variant: true } }), 0)).toEqual([]);
  expect(environmentsShown(header, choice(), 4000)).toEqual([]);
});

test("a kind that is off is never shown, even under the cursor, and with every kind off nothing is", () => {
  expect(epochsShown(header, choice({ kinds: { arena: false, track: true } }), 0)).toEqual([]);
  expect(epochsShown(header, choice({ follow: false, kinds: { arena: false, track: false } }), 0)).toEqual([]);
  expect(environmentsShown(header, choice({ kinds: {} }), 0)).toEqual([]);
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
