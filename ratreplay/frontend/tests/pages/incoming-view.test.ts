import { expect, test } from "vitest";
import { formatGroups } from "../../src/api/describe";
import type { FormatContract, Folder, Health, SessionRow } from "../../src/api/types";
import { COLUMNS, incomingGroups, reviewText, rowTitle, sessionFacts, stripLines, stripProblems, stripStatus, tiles, totalsText } from "../../src/pages/incoming-view";

function row(session_id: string, extra: Partial<SessionRow> = {}): SessionRow {
  return {
    session_id, subject_id: session_id.slice(0, 4), group: "G", date: "2015-01-01", protocol: "standard", rate_hz: 60, max_gap: 30,
    epochs: [{ epoch: "arena", environment: "open_arena", condition: "baseline", frame_start: 1, frame_end: 1800, duration_s: 30 }],
    n_runs: 4, n_clean_runs: 3, in_dataset: true, reason: null, annotated_exclude: false, excluded: false, excluded_by: null, excluded_at: null, built: 0, reviewed: false, reviewed_at: null, reviewed_by: null,
    n_confirmed: 0, confirmed_s: {}, notes: "", ...extra,
  };
}

test("a session the rules leave out says why in its facts and in the title of its row", () => {
  const out = row("NS5_b", { in_dataset: false, reason: "protocol rotation, not standard" });
  expect(sessionFacts(out, null)[0]).toEqual({ label: "in dataset", value: "no, protocol rotation, not standard" });
  expect(rowTitle(out)).toBe("NS5_b, not in the dataset: protocol rotation, not standard");
  expect(rowTitle(row("NS14_a"))).toBe("NS14_a");
});

test("the tiles count the sessions in the dataset, reviewed and excluded, the blocks confirmed, the hours confirmed per epoch kind and the blocks built, in that order", () => {
  const reviewed = (confirmed_s: Record<string, number>, n_confirmed: number, extra: Partial<SessionRow> = {}) => row("NS1_x", { reviewed: true, n_confirmed, confirmed_s, ...extra });
  const rows = [reviewed({ track: 1800, arena: 900 }, 3, { built: 3 }), reviewed({ track: 5400 }, 2, { excluded: true, built: 2 }), row("NS2_y", { in_dataset: false, reason: "no frames" })];
  expect(tiles(rows)).toEqual([
    { label: "in the dataset", value: "2 of 3" },
    { label: "reviewed", value: "2" },
    { label: "excluded", value: "1" },
    { label: "blocks confirmed", value: "5" },
    { label: "arena hours confirmed", value: "0.25" },
    { label: "track hours confirmed", value: "2.00" },
    { label: "built blocks", value: "5" },
  ]);
  expect(totalsText(rows)).toBe("2 of 3 sessions in the dataset, 2 reviewed, 1 excluded, 5 blocks confirmed, confirmed hours arena 0.25, track 2.00, 5 blocks built");
  expect(totalsText([row("NS2_y", { confirmed_s: { arena: 0, track: 0 } })])).toBe("1 of 1 session in the dataset, 0 reviewed, 0 excluded, 0 blocks confirmed, confirmed hours arena 0.00, track 0.00, 0 blocks built");
});

test("the Excluded column says yes for a session you excluded and nothing for the others, and sorts on it", () => {
  const column = COLUMNS.find((c) => c.key === "excluded")!;
  const [kept, left, annotated] = [row("A"), row("B", { excluded: true }), row("C", { annotated_exclude: true })];
  expect([kept, left, annotated].map(column.text)).toEqual(["", "yes", ""]);
  expect([kept, left].map(column.value)).toEqual([0, 1]);
});

test("the Has notes column says yes for a session with notes, exclusion notes included, and nothing for the others, and sorts on it", () => {
  const column = COLUMNS.find((c) => c.key === "notes")!;
  expect(column.label).toBe("Has notes");
  const [none, blank, noted] = [row("A"), row("B", { notes: "  \n" }), row("C", { notes: "camera moved\nbad light" })];
  expect([none, blank, noted].map(column.text)).toEqual(["", "", "yes"]);
  expect([none, blank, noted].map(column.value)).toEqual([0, 0, 1]);
});

test("the review text says who reviewed and when, who excluded and when, and a session only excluded was not reviewed", () => {
  const reviewed = { reviewed: true, reviewed_by: "kyle", reviewed_at: "2026-10-16T12:00:00+00:00", n_confirmed: 2, confirmed_s: { track: 600 } };
  const excluded = { excluded: true, excluded_by: "yuki", excluded_at: "2026-10-17T12:00:00+00:00" };
  expect(reviewText(row("A"))).toBe("not reviewed yet");
  expect(reviewText(row("A", reviewed))).toMatch(/^reviewed by kyle on .*, 2 blocks kept \(track 10\.0 min\)$/);
  expect(reviewText(row("A", { reviewed: true, ...excluded }))).toMatch(/^excluded by yuki on [^.]*$/);
  expect(reviewText(row("A", { ...reviewed, ...excluded }))).toMatch(/^reviewed by kyle on .*\. excluded by yuki on /);
});

const folder = (extra: Partial<Folder> = {}): Folder => ({
  root: "/data/transformed", exists: true, problems: [], counts: { sessions: 6, frames: 2 },
  manifest: { timestamp: "2026-10-13T10:00:00+00:00", modified: "2026-10-16T11:00:00+00:00" }, ...extra,
});
const ENVIRONMENTS: Folder = { root: "/repo/configs/environments", exists: true, problems: [], counts: { environments: 4 }, manifest: { modified: "2026-08-23T17:37:33+00:00" } };
const PROCESSED: Folder = { root: "/data/processed", exists: true, problems: ["1 block files missing"], counts: {}, manifest: null };
const health = (transformed: Folder, environments = ENVIRONMENTS): Health => ({ transformed, processed: PROCESSED, environments, config_path: "configs/local.yaml" });

test("the strip has a line for the lab data, the environment geometry and the config file, the Reload button on the last, and says nothing of the processed folder", () => {
  const lines = stripLines(health(folder()));
  expect(lines.map((l) => [l.label, l.path, l.status, l.reloads])).toEqual([
    ["lab data read from", "/data/transformed", "ok", false],
    ["environment geometry read from", "/repo/configs/environments", "ok", false],
    ["config file", "configs/local.yaml", "ok", true],
  ]);
  expect(lines[0].detail).toMatch(/^6 sessions, converter run 2026-10-13 /);
  expect(lines[1].detail).toBe("4 environments");
  expect(stripProblems(lines)).toEqual([]);
});

test("a lab data folder that exists and holds no sessions has nothing yet, and the strip card takes the worst of its lines", () => {
  const empty = stripLines(health(folder({ counts: { sessions: 0 } })));
  expect(empty.map((line) => line.status)).toEqual(["nothing yet", "ok", "ok"]);
  expect(stripStatus(empty)).toBe("nothing yet");
  expect(stripStatus(stripLines(health(folder())))).toBe("ok");
  expect(stripStatus(stripLines(health(folder({ counts: { sessions: 0 } }), { ...ENVIRONMENTS, problems: ["no yaml files"] })))).toBe("problem");
});

test("a folder with problems shows them under the strip with the line they belong to, a key the config lacks shows as not set", () => {
  const notSet = folder({ root: null, exists: false, problems: ["TRANSFORMED_LAB_DATA is not set in configs/local.yaml"], counts: {}, manifest: null });
  const lines = stripLines(health(notSet, { ...ENVIRONMENTS, problems: ["no yaml files"] }));
  expect([lines[0].path, lines[0].status, lines[0].detail, lines[1].status]).toEqual(["not set", "problem", "", "problem"]);
  expect(stripProblems(lines)).toEqual([
    { label: "lab data read from", text: "TRANSFORMED_LAB_DATA is not set in configs/local.yaml" },
    { label: "environment geometry read from", text: "no yaml files" },
  ]);
});

test("the incoming format keeps the transformed files' tables and leaves the processed ones, the review file and the settings to their pages", () => {
  const contract = { version: 1, transformed: { files: [] }, processed: { files: [{ path: "review/<session_id>.json", optional: true, edits: {} }] }, settings: {}, rules: {} } as unknown as FormatContract;
  const groups = formatGroups(contract);
  expect(groups.map((g) => g.title)).toEqual(["Transformed folder", "Processed folder", "Review file", "Window settings"]);
  expect(incomingGroups(groups).map((g) => g.title)).toEqual(["Transformed folder"]);
});
