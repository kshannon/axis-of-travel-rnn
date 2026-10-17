import { expect, test } from "vitest";
import type { SessionHeader, SessionRow } from "../api/types";
import { briefList, filterRows, minutesOf, sessionFacts, totalsLine } from "./sessions-rows";

function row(session_id: string, extra: Partial<SessionRow> = {}): SessionRow {
  return {
    session_id, subject_id: session_id.slice(0, 4), group: "G", date: "2015-01-01", protocol: "standard", rate_hz: 60, max_gap: 30,
    epochs: [{ epoch: "arena", environment: "open_arena", condition: "baseline", frame_start: 1, frame_end: 1800, duration_s: 30 }],
    n_runs: 4, n_clean_runs: 3, in_dataset: true, n_automatic: 2, reviewed: false, reviewed_at: null, reviewed_by: null,
    n_confirmed: 0, confirmed_s: {}, notes: "", ...extra,
  };
}

const ROWS = [
  row("NS14_a", { date: "2015-01-03", n_runs: 4, reviewed_by: "kyle", reviewed_at: "2026-10-16T10:00:00+00:00" }),
  row("NS5_b", { date: "2015-01-01", n_runs: 10 }),
  row("NS16_c", { date: "2015-01-02", n_runs: 7, reviewed_by: "ana", reviewed_at: "2026-10-15T10:00:00+00:00" }),
];
const ids = (rows: SessionRow[]) => rows.map((r) => r.session_id);

test("the filter matches the session id or the rat, in any case", () => {
  expect(ids(filterRows(ROWS, "ns5"))).toEqual(["NS5_b"]);
  expect(ids(filterRows(ROWS, " "))).toEqual(ids(ROWS));
});

test("minutes add up the epochs", () => {
  const two = row("NS1_x", { epochs: [...ROWS[0].epochs, { ...ROWS[0].epochs[0], epoch: "track", duration_s: 90 }] });
  expect(minutesOf(two)).toBe(2);
});

test("the facts grow with the session header and list a few frames of what cut the session", () => {
  expect(sessionFacts(ROWS[0], null).map((f) => f.label)).toEqual(["group", "frame rate", "runs"]);
  const header = {
    n_frames: 5400, led_offset: { rad: Math.PI, r: 0.0218 },
    cuts: { pauses: [2701], jumps: [], gaps: [[10, 20], [30, 40]], margins: [] },
  } as unknown as SessionHeader;
  const facts = Object.fromEntries(sessionFacts(ROWS[0], header).map((f) => [f.label, f.value]));
  expect(facts).toMatchObject({ pauses: "1, at frames 2701", gaps: "2, frames 10 to 20, 30 to 40", jumps: "none", "LED offset": "180 deg, concentration 0.02" });
});

test("a long list is cut short with the number left out", () => {
  expect(briefList(["1", "2", "3", "4"], 2)).toBe("1, 2 and 2 more");
});

test("the totals count the sessions reviewed, the blocks confirmed and the hours confirmed per epoch kind", () => {
  const reviewed = (confirmed_s: Record<string, number>, n_confirmed: number) => row("NS1_x", { reviewed: true, n_confirmed, confirmed_s });
  const rows = [reviewed({ track: 1800, arena: 900 }, 3), reviewed({ track: 5400 }, 2), row("NS2_y")];
  expect(totalsLine(rows)).toBe("2 of 3 sessions reviewed, 5 blocks confirmed, confirmed hours: arena 0.25, track 2.00");
  expect(totalsLine([row("NS2_y", { confirmed_s: { arena: 0, track: 0 } })])).toBe("0 of 1 session reviewed, 0 blocks confirmed, confirmed hours: arena 0.00, track 0.00");
});
