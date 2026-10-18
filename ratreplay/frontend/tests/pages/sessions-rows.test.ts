import { expect, test } from "vitest";
import type { SessionRow } from "../../src/api/types";
import { rowTitle, sessionFacts, totalsLine } from "../../src/pages/sessions-rows";

function row(session_id: string, extra: Partial<SessionRow> = {}): SessionRow {
  return {
    session_id, subject_id: session_id.slice(0, 4), group: "G", date: "2015-01-01", protocol: "standard", rate_hz: 60, max_gap: 30,
    epochs: [{ epoch: "arena", environment: "open_arena", condition: "baseline", frame_start: 1, frame_end: 1800, duration_s: 30 }],
    n_runs: 4, n_clean_runs: 3, in_dataset: true, reason: null, built: 0, reviewed: false, reviewed_at: null, reviewed_by: null,
    n_confirmed: 0, confirmed_s: {}, notes: "", ...extra,
  };
}

test("a session the rules leave out says why in its facts and in the title of its row", () => {
  const out = row("NS5_b", { in_dataset: false, reason: "protocol rotation, not standard" });
  expect(sessionFacts(out, null)[0]).toEqual({ label: "in dataset", value: "no, protocol rotation, not standard" });
  expect(rowTitle(out)).toBe("NS5_b, not in the dataset: protocol rotation, not standard");
  expect(rowTitle(row("NS14_a"))).toBe("NS14_a");
});

test("the totals count the sessions reviewed, the blocks confirmed and the hours confirmed per epoch kind", () => {
  const reviewed = (confirmed_s: Record<string, number>, n_confirmed: number) => row("NS1_x", { reviewed: true, n_confirmed, confirmed_s });
  const rows = [reviewed({ track: 1800, arena: 900 }, 3), reviewed({ track: 5400 }, 2), row("NS2_y")];
  expect(totalsLine(rows)).toBe("2 of 3 sessions reviewed, 5 blocks confirmed, confirmed hours: arena 0.25, track 2.00");
  expect(totalsLine([row("NS2_y", { confirmed_s: { arena: 0, track: 0 } })])).toBe("0 of 1 session reviewed, 0 blocks confirmed, confirmed hours: arena 0.00, track 0.00");
});
