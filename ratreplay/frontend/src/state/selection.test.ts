import { expect, test } from "vitest";
import type { Source } from "../api/types";
import { loadSelection, NONE, problemWith, reconcile, saveSelection, selectionOf } from "./selection";

function source(id: string, status: Source["status"] = "ok"): Source {
  return {
    id, kind: "transformed", path: `/data/${id}`, processed_path: "/data/processed", attached_at: "2026-10-16T12:00:00+00:00",
    status, problems: [], counts: { sessions: 6 }, manifests: { transformed: null, processed: null },
  };
}

function memory() {
  const items = new Map<string, string>();
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => void items.set(key, value) };
}

test("a saved selection comes back after a reload, an empty store gives none", () => {
  const storage = memory();
  expect(loadSelection(storage)).toEqual(NONE);
  const chosen = selectionOf(source("3d611da3"), "NS14_rec1_20150101_001");
  saveSelection(storage, chosen);
  expect(loadSelection(storage)).toEqual(chosen);
});

test("the selection is refreshed from the sources and keeps its session", () => {
  const stale = { ...selectionOf(source("a"), "S1"), counts: { sessions: 1 } };
  expect(reconcile(stale, [source("a")])).toEqual(selectionOf(source("a"), "S1"));
});

test("a source that is gone or no longer valid clears the selection", () => {
  const chosen = selectionOf(source("a"), "S1");
  expect(reconcile(chosen, [source("b")])).toEqual(NONE);
  expect(reconcile(chosen, [source("a", "invalid")])).toEqual(NONE);
});

test("a page needing a transformed source says what is wrong with the selection", () => {
  expect(problemWith(NONE, "transformed")).toBe("No source is selected.");
  expect(problemWith({ ...selectionOf(source("a")), kind: "processed" }, "transformed")).toMatch(/is processed/);
  expect(problemWith(selectionOf(source("a")), "transformed")).toBe("");
  expect(problemWith({ ...selectionOf(source("a")), kind: "processed" })).toBe("");
});
