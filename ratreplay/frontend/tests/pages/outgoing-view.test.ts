import { expect, test } from "vitest";
import { formatGroups } from "../../src/api/describe";
import type { Folder, FormatContract, Readiness, Rebuilt, SessionRow, WindowSettings } from "../../src/api/types";
import { builtElsewhere, COLUMNS, failedLines, outgoingGroups, outRows, rebuildSummary, rowNote, syntheticView, writeView } from "../../src/pages/outgoing-view";

const PROCESSED: Folder = {
  root: "/data/processed", exists: true, problems: [], counts: { reviews: 2, blocks: 3, sessions: 2 }, manifest: { modified: "2026-10-17T09:00:00+00:00" },
};

test("a processed folder that does not exist yet is ok with a note, an empty one says nothing is saved and has nothing yet, a built one shows its counts and when it changed", () => {
  const missing = { ...PROCESSED, exists: false, counts: {}, manifest: null };
  expect(writeView(missing)).toMatchObject({ status: "ok", times: [], counts: [] });
  expect(writeView(missing).note).toMatch(/Does not exist yet/);
  const empty = { ...PROCESSED, counts: { reviews: 0, blocks: 0, sessions: 0 }, manifest: null };
  expect(writeView(empty).note).toMatch(/Nothing saved yet/);
  expect(writeView(empty).status).toBe("nothing yet");
  expect(writeView(PROCESSED)).toMatchObject({
    status: "ok", note: "", counts: [{ label: "reviews", value: 2 }, { label: "blocks", value: 3 }, { label: "built sessions", value: 2 }],
    times: [{ label: "folder last changed", stamp: "2026-10-17T09:00:00+00:00" }],
  });
});

test("a key the config lacks shows the problem naming it, no root and no note", () => {
  const notSet: Folder = { root: null, exists: false, problems: ["PROCESSED_LAB_DATA is not set in configs/local.yaml"], counts: {}, manifest: null };
  const view = writeView(notSet);
  expect([view.root, view.status, view.note]).toEqual(["not set", "problem", ""]);
  expect(view.problems).toEqual(notSet.problems);
});

test("the outgoing format keeps the processed files' tables, the review file's and the synthetic folder's, and leaves the transformed ones to the Incoming page", () => {
  const contract = { version: 1, transformed: { files: [] }, processed: { files: [{ path: "review/<session_id>.json", optional: true, edits: {} }] }, synthetic: { files: [] }, settings: {}, rules: {} } as unknown as FormatContract;
  expect(outgoingGroups(formatGroups(contract)).map((g) => g.title)).toEqual(["Processed folder", "Review file", "Synthetic folder"]);
});

test("the synthetic folder's view counts its sets, blocks and guesses, says what an absent or empty folder means, and has nothing yet while it holds no set", () => {
  const folder: Folder = { root: "/data/synthetic", exists: true, problems: [], counts: { sets: 1, blocks: 2, guesses: 3 }, manifest: { modified: "2026-10-19T09:00:00+00:00" } };
  expect(syntheticView(folder)).toMatchObject({ status: "ok", note: "", counts: [{ label: "sets", value: 1 }, { label: "blocks", value: 2 }, { label: "guesses", value: 3 }] });
  expect(syntheticView({ ...folder, exists: false, counts: {}, manifest: null }).note).toMatch(/first Generate on Synthetic creates it/);
  const empty = syntheticView({ ...folder, counts: { sets: 0, blocks: 0, guesses: 0 }, manifest: null });
  expect([empty.status, empty.note]).toEqual(["nothing yet", "No set yet, Generate on Synthetic writes here."]);
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

const IN_USE: WindowSettings = { window_s: 40, stride_s: 10, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1 };
const SHORT: WindowSettings = { ...IN_USE, window_s: 5 };
const PROBLEM = { block_id: "B_track_01", problems: ["a step in t differs from one frame"] };

const block = (session_id: string) => ({ session_id }) as Readiness["blocks"][number];
const readiness: Readiness = {
  which: "real", settings: IN_USE, totals: { blocks: 3, ok: 0, trouble: 3, windows: 0, windows_ok: 0 },
  blocks: [block("A"), block("A"), block("B")],
  built: {
    B: { settings: IN_USE, built_at: "2026-10-18T10:00:00+00:00", excluded: false, failed: [PROBLEM] },
    A: { settings: SHORT, built_at: "2026-10-17T10:00:00+00:00", excluded: false, failed: [] },
    C: { settings: IN_USE, built_at: "2026-10-18T11:00:00+00:00", excluded: true, failed: [] },
  },
};
const session = (session_id: string, extra: Partial<SessionRow> = {}) =>
  ({ session_id, reviewed: true, excluded: false, in_dataset: true, reason: null, ...extra }) as SessionRow;

test("every built session is a row with its blocks, failed blocks, exclusion and settings, then the reviewed sessions that are not built, in session order", () => {
  const sessions = [session("A"), session("B"), session("C", { excluded: true }), session("D"), session("E", { in_dataset: false, reason: "no frames" }), session("F", { reviewed: false })];
  const rows = outRows(readiness, sessions);
  expect(rows.map((r) => [r.session_id, r.blocks, r.failed.length, r.excluded, r.waiting])).toEqual([
    ["A", 2, 0, false, ""], ["B", 1, 1, false, ""], ["C", 0, 0, true, ""], ["D", 0, 0, false, "not built yet"], ["E", 0, 0, false, "skipped, not in the dataset: no frames"],
  ]);
  expect(rows[0].settings).toEqual(SHORT);
  expect(rows[3].settings).toBeNull();
  expect(rows[1].built_at).toBe("2026-10-18T10:00:00+00:00");
});

test("a built entry from an API older than the page, with no failed and no excluded, is a row with none failed and not excluded", () => {
  const old = { ...readiness, built: { A: { settings: IN_USE, built_at: "2026-10-17T10:00:00+00:00" } as Readiness["built"][string] } };
  const [row] = outRows(old, [session("A")]);
  expect([row.failed, row.excluded]).toEqual([[], false]);
  expect([COLUMNS.find((col) => col.key === "failed")!.text(row), rowNote(row), failedLines(row)]).toEqual(["0", "Every block was written.", []]);
  expect(outRows(old, [session("A", { excluded: true })])[0].excluded).toBe(true);
});

test("a session built at other settings than the ones in use is marked and names the settings that differ, one built the same is not", () => {
  const [a, b] = outRows(readiness, []);
  expect([builtElsewhere(a), builtElsewhere(b)]).toEqual([true, false]);
  expect(a.compare.filter((setting) => setting.differs)).toEqual([{ label: "window (s)", tried: "40", built: "5", differs: true }]);
});

test("the table columns show the failed count in red, the settings built with or why there is no build, and sort the unbuilt last by their missing time", () => {
  const rows = outRows(readiness, [session("A"), session("B"), session("C", { excluded: true }), session("D")]);
  const [a, b, c, d] = rows;
  const column = (key: string) => COLUMNS.find((col) => col.key === key)!;
  expect([a, b].map(column("failed").text)).toEqual(["0", "1"]);
  expect([a, b].map((r) => column("failed").tone!(r))).toEqual(["text-muted", "text-bad"]);
  expect(column("settings").text(a)).toMatch(/^5 s window, 10 s stride/);
  expect([column("settings").text(d), column("settings").tone!(a), column("settings").tone!(b)]).toEqual(["not built yet", "text-warn", ""]);
  expect([c].map(column("excluded").text)).toEqual(["yes"]);
  expect(column("at").value(d)).toBeNull();
});

test("an open row says what is wrong with it and lists each failed block with its problems", () => {
  const [a, b, c, d] = outRows(readiness, [session("A"), session("B"), session("C", { excluded: true }), session("D")]);
  expect([a, b, c, d].map(rowNote)).toEqual(["Every block was written.", "1 block failed and was not written", "Built excluded, no block is written for it.", "not built yet"]);
  expect(failedLines(b)).toEqual(["B_track_01: a step in t differs from one frame"]);
  expect(failedLines(a)).toEqual([]);
});
