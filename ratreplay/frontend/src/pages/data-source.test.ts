import { expect, test } from "vitest";
import type { Source } from "../api/types";
import { attachBody, attachProblem, countEntries, timeRows } from "./data-source";

const SOURCE: Source = {
  id: "3d611da3", kind: "transformed", path: "/data/transformed", processed_path: "/data/processed",
  attached_at: "2026-10-16T12:00:00+00:00", status: "ok", problems: [],
  counts: { reviews: 1, sessions: 6, blocks: 3 },
  manifests: { transformed: { timestamp: "2026-10-13T10:00:00+00:00", modified: "2026-10-16T11:00:00+00:00" }, processed: null },
};

test("the attach form needs a folder, and a processed folder for a transformed source", () => {
  expect(attachProblem({ path: " ", kind: "processed", processedPath: "" })).toMatch(/path of the folder/);
  expect(attachProblem({ path: "/data/t", kind: "transformed", processedPath: "" })).toMatch(/processed folder/);
  expect(attachProblem({ path: "/data/t", kind: "transformed", processedPath: "/data/p" })).toBe("");
  expect(attachProblem({ path: "/data/p", kind: "processed", processedPath: "" })).toBe("");
});

test("only a transformed source sends its processed path", () => {
  expect(attachBody({ path: " /data/t ", kind: "transformed", processedPath: "/data/p" })).toEqual({ path: "/data/t", kind: "transformed", processed_path: "/data/p" });
  expect(attachBody({ path: "/data/p", kind: "processed", processedPath: "/ignored" })).toEqual({ path: "/data/p", kind: "processed" });
});

test("the counts the source has come in reading order and the missing ones are left out", () => {
  expect(countEntries(SOURCE)).toEqual([{ label: "sessions", value: 6 }, { label: "blocks", value: 3 }, { label: "reviews", value: 1 }]);
});

test("the time rows leave out a manifest the folder does not have", () => {
  expect(timeRows(SOURCE).map((row) => row.label)).toEqual(["converter run", "converter folder changed", "attached"]);
});
