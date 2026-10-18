import { expect, test } from "vitest";
import type { Folder, Health, Rebuilt } from "../../src/api/types";
import { foldersView, rebuildSummary } from "../../src/pages/data-view";

const TRANSFORMED: Folder = {
  root: "/data/transformed", exists: true, problems: [], counts: { sessions: 6, frames: 2 },
  manifest: { timestamp: "2026-10-13T10:00:00+00:00", modified: "2026-10-16T11:00:00+00:00" },
};
const PROCESSED: Folder = {
  root: "/data/processed", exists: true, problems: [], counts: { reviews: 2, blocks: 3, sessions: 2 }, manifest: { modified: "2026-10-17T09:00:00+00:00" },
};
const ENVIRONMENTS: Folder = {
  root: "/repo/configs/environments", exists: true, problems: [], counts: { environments: 4 }, manifest: { modified: "2026-08-23T17:37:33+00:00" },
};
const health = (processed: Folder, transformed = TRANSFORMED): Health => ({ transformed, processed, environments: ENVIRONMENTS, config_path: "configs/local.yaml" });

test("a processed folder that does not exist yet is ok with a note, an empty one says nothing is saved", () => {
  const missing = { ...PROCESSED, exists: false, counts: {}, manifest: null };
  expect(foldersView(health(missing)).processed).toMatchObject({ status: "ok", times: [], counts: [] });
  expect(foldersView(health(missing)).processed.note).toMatch(/Does not exist yet/);
  const empty = { ...PROCESSED, counts: { reviews: 0, blocks: 0, sessions: 0 }, manifest: null };
  expect(foldersView(health(empty)).processed.note).toMatch(/Nothing saved yet/);
});

test("a key the config lacks shows the problem naming it and no root", () => {
  const notSet: Folder = { root: null, exists: false, problems: ["PROCESSED_LAB_DATA is not set in configs/local.yaml"], counts: {}, manifest: null };
  const { processed } = foldersView(health(notSet));
  expect([processed.root, processed.status, processed.note]).toEqual(["not set", "problem", ""]);
  expect(processed.problems).toEqual(notSet.problems);
  expect(processed.key).toBe("PROCESSED_LAB_DATA");
});

test("the rebuild toast gives the totals and names the first build that stopped", () => {
  const done: Rebuilt = {
    sessions: { A: { built: 2, failed: [], build_error: null }, B: { built: 0, failed: [], build_error: "Invalid: session B is not in the dataset: no frames" } },
    totals: { sessions: 2, built: 2, failed: 0, errors: 1 },
  };
  expect(rebuildSummary(done)).toBe("Rebuilt 2 sessions, 2 blocks built, 0 failed, 1 error. B: Invalid: session B is not in the dataset: no frames");
  const clean: Rebuilt = { sessions: { A: done.sessions.A }, totals: { sessions: 1, built: 2, failed: 0, errors: 0 } };
  expect(rebuildSummary(clean)).toBe("Rebuilt 1 session, 2 blocks built, 0 failed, 0 errors");
});
