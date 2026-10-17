import { expect, test } from "vitest";
import type { Source, Sources } from "../api/types";
import { foldersView } from "./data-view";

const TRANSFORMED: Source = {
  path: "/data/transformed", status: "ok", problems: [], counts: { sessions: 6, frames: 2 },
  manifest: { timestamp: "2026-10-13T10:00:00+00:00", modified: "2026-10-16T11:00:00+00:00" },
};
const NOT_BUILT: Source = { path: "/data/processed", status: "ok", problems: [], counts: { reviews: 1 }, manifest: null };
const NOT_SET: Source = { path: null, status: "invalid", problems: ["PROCESSED_LAB_DATA is not set in configs/local.yaml"], counts: {}, manifest: null };
const sources = (processed: Source): Sources => ({ transformed: TRANSFORMED, processed, config_path: "configs/local.yaml" });

test("a folder shows its path, the counts it has in reading order and the times of its manifest", () => {
  const { transformed } = foldersView(sources(NOT_BUILT));
  expect(transformed.path).toBe("/data/transformed");
  expect(transformed.counts).toEqual([{ label: "sessions", value: 6 }, { label: "frames files", value: 2 }]);
  expect(transformed.times).toEqual([
    { label: "converter run", stamp: "2026-10-13T10:00:00+00:00" }, { label: "folder last changed", stamp: "2026-10-16T11:00:00+00:00" },
  ]);
  expect([transformed.direction, transformed.note]).toEqual(["incoming", ""]);
});

test("a processed folder the processor has not run in is ok with a note and no times", () => {
  const { processed } = foldersView(sources(NOT_BUILT));
  expect([processed.status, processed.times, processed.counts]).toEqual(["ok", [], [{ label: "reviews", value: 1 }]]);
  expect(processed.note).toMatch(/Not built yet/);
});

test("a key the config lacks shows the problem naming it and no path", () => {
  const { processed } = foldersView(sources(NOT_SET));
  expect([processed.path, processed.status, processed.note]).toEqual(["not set", "invalid", ""]);
  expect(processed.problems).toEqual(NOT_SET.problems);
  expect(processed.key).toBe("PROCESSED_LAB_DATA");
});
