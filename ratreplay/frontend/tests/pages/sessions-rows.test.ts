import { expect, test } from "vitest";
import type { SessionRow } from "../../src/api/types";
import { COLUMNS, reviewText, rowTitle, sessionFacts, tiles, totalsText } from "../../src/pages/sessions-rows";

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

test("the review text says who reviewed and when, who excluded and when, and a session only excluded was not reviewed", () => {
  const reviewed = { reviewed: true, reviewed_by: "kyle", reviewed_at: "2026-10-16T12:00:00+00:00", n_confirmed: 2, confirmed_s: { track: 600 } };
  const excluded = { excluded: true, excluded_by: "yuki", excluded_at: "2026-10-17T12:00:00+00:00" };
  expect(reviewText(row("A"))).toBe("not reviewed yet");
  expect(reviewText(row("A", reviewed))).toMatch(/^reviewed by kyle on .*, 2 blocks kept \(track 10\.0 min\)$/);
  expect(reviewText(row("A", { reviewed: true, ...excluded }))).toMatch(/^excluded by yuki on [^.]*$/);
  expect(reviewText(row("A", { ...reviewed, ...excluded }))).toMatch(/^reviewed by kyle on .*\. excluded by yuki on /);
});
