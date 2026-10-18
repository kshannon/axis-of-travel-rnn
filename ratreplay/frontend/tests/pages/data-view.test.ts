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

test("the rebuild toast gives the totals, names the first review skipped, the first session you excluded with its note and the first build that stopped", () => {
  const done: Rebuilt = {
    sessions: {
      A: { built: 2, failed: [], build_error: null }, C: { built: 0, failed: [], build_error: null },
      B: { built: 0, failed: [], build_error: "NotFound: no session B" },
    },
    skipped: { E: "no frames", F: "no arena or track epoch under condition baseline" },
    excluded: { C: "camera moved\nbad light", D: "" },
    totals: { sessions: 3, built: 2, failed: 0, errors: 1, skipped: 2, excluded: 2 },
  };
  expect(rebuildSummary(done)).toBe(
    "Rebuilt 3 sessions, 2 blocks built, 0 failed, 2 skipped (not in the dataset), 2 excluded by you, 1 error. " +
    "Skipped E: no frames. Excluded C: camera moved, bad light. B: NotFound: no session B");
  expect(rebuildSummary({ ...done, skipped: {}, excluded: { D: "" } })).toContain("Excluded D. B: NotFound");
  const clean: Rebuilt = { sessions: { A: done.sessions.A }, skipped: {}, excluded: {}, totals: { sessions: 1, built: 2, failed: 0, errors: 0, skipped: 0, excluded: 0 } };
  expect(rebuildSummary(clean)).toBe("Rebuilt 1 session, 2 blocks built, 0 failed, 0 skipped (not in the dataset), 0 excluded by you, 0 errors");
});
