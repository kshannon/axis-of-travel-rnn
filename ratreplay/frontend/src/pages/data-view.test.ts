import { expect, test } from "vitest";
import type { Folder, Health, Rebuilt, WindowSettings } from "../api/types";
import { foldersView, rebuildPrompt, rebuildSummary } from "./data-view";

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

const SETTINGS: WindowSettings = { window_s: 40, stride_s: 10, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1 };

test("a folder shows its root, the counts it has in reading order and the times it reports", () => {
  const { transformed, processed } = foldersView(health(PROCESSED));
  expect(transformed.root).toBe("/data/transformed");
  expect(transformed.counts).toEqual([{ label: "sessions", value: 6 }, { label: "frames files", value: 2 }]);
  expect(transformed.times).toEqual([
    { label: "converter run", stamp: "2026-10-13T10:00:00+00:00" }, { label: "folder last changed", stamp: "2026-10-16T11:00:00+00:00" },
  ]);
  expect([transformed.direction, transformed.status, transformed.note]).toEqual(["incoming", "ok", ""]);
  expect(processed.counts.map((c) => c.label)).toEqual(["reviews", "blocks", "built sessions"]);
  expect(processed.times).toEqual([{ label: "folder last changed", stamp: "2026-10-17T09:00:00+00:00" }]);
});

test("the environments folder is the third card, with a note that the config does not name it", () => {
  const { environments } = foldersView(health(PROCESSED));
  expect([environments.status, environments.key, environments.counts]).toEqual(["ok", "", [{ label: "environments", value: 4 }]]);
  expect(environments.note).toMatch(/configs\/environments/);
});

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

test("the rebuild confirmation names the sessions, the settings and the folder it replaces blocks in", () => {
  expect(rebuildPrompt(2, SETTINGS, "/data/processed")).toBe(
    "Build the blocks of 2 reviewed sessions again at a 40 s window every 10 s, burn-in 1 s, horizon 0.5 s, 20 Hz, " +
    "measured heading at least 80%, at least 1 complete trip? " +
    "Their built blocks and metadata in /data/processed are replaced, the reviews are not changed.",
  );
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
