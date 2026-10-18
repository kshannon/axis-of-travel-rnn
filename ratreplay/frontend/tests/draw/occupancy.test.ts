import { expect, test } from "vitest";
import type { Geometry, SessionHeader } from "../../src/api/types";
import { ALL, CURRENT, environmentsShown, epochsShown } from "../../src/draw/occupancy";

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

test("the current choice follows the epoch under the cursor, which is the lab frame after the index", () => {
  expect(epochsShown(header, CURRENT, 0)).toEqual(["arena"]);
  expect(epochsShown(header, CURRENT, 1800)).toEqual(["track"]);
  expect(epochsShown(header, CURRENT, 9000)).toEqual(["no epoch"]);
  expect(environmentsShown(header, CURRENT, 1799)).toEqual(["open_arena"]);
  expect(environmentsShown(header, CURRENT, 1800)).toEqual(["triple_t"]);
});

test("all shows the epochs the rules cut, one by name shows its own, and an epoch the rules do not cut has no geometry", () => {
  expect(epochsShown(header, ALL, 0)).toEqual(["arena", "track"]);
  expect(environmentsShown(header, ALL, 0)).toEqual(["open_arena", "triple_t"]);
  expect(environmentsShown(header, "track", 0)).toEqual(["triple_t"]);
  expect(environmentsShown(header, "variant", 0)).toEqual([]);
  expect(environmentsShown(header, CURRENT, 4000)).toEqual([]);
});
