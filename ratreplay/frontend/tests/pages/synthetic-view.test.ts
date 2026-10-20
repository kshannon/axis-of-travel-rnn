import { expect, test } from "vitest";
import type { Quantiles, Recipe, SessionRow, SetRow } from "../../src/api/types";
import { compareCaption, compareRows, compareTables, fixed, generateBlocked, generatedText, lengthsOf, setLines, sourceChoices } from "../../src/pages/synthetic-view";

const q = (median: number): Quantiles => ({ q05: median / 2, q25: median * 0.75, q50: median, q75: median * 1.25, q95: median * 2, mean: median });
const NULLS: Quantiles = { q05: null, q25: null, q50: null, q75: null, q95: null, mean: null };

const track = (median: number): Recipe => ({
  counts: { blocks: 2, frames: 2400, seconds: 40 }, speed: q(median), turn_rate: q(1), turn_rate_abs_mean: 0.8, still_fraction: 0.3, heading_spread_rad: 0.25,
  pauses: { per_min: 1.5, duration_s: q(2) }, runs: { "1": { count: 3, duration_s: q(4) }, "9": { count: 3, duration_s: q(5) } },
  dwell_s: { start: q(3), goal: q(6) }, trips_per_min: 2.5, goal_share: { "1": 0.5, "2": 0.5, "3": 0, "4": 0 },
  phase_share: { outbound: 0.3, dwell: 0.4, return: 0.3, pause: 0 },
});
const arena: Recipe = {
  counts: { blocks: 1, frames: 1200, seconds: 20 }, speed: q(0.2), turn_rate: q(1.6), turn_rate_abs_mean: 1.2, still_fraction: 0.1, heading_spread_rad: 0.4,
  pauses: { per_min: 2, duration_s: NULLS }, environment: "open_arena", boundary_distance_m: q(0.1), occupancy_grid: [[1]], phase_share: { forage: 1, pause: 0 },
};

const set = (set_id: string, created_at: string, extra: Partial<SetRow> = {}): SetRow => ({
  set_id, created_at, created_by: "kyle", sources: ["A", "B"], seed: 3, length_s: { arena: 600, track: 1200 }, n_blocks: 2, kinds: ["arena", "track"], n_guesses: 0, n_correct: 0, ...extra,
});

test("the sets table lists the newest set first with its minutes per kind, blocks per kind and guesses with how many were right", () => {
  const lines = setLines([set("syn_a", "2026-10-19T10:00:00+00:00"), set("syn_b", "2026-10-19T11:00:00+00:00", { n_guesses: 4, n_correct: 3, length_s: { track: 90 }, kinds: ["track"], n_blocks: 1 })]);
  expect(lines.map((line) => line.set_id)).toEqual(["syn_b", "syn_a"]);
  expect(lines[1]).toMatchObject({ sources: "A, B", seed: "3", minutes: "arena 10, track 20", blocks: "2 (arena, track)", guesses: "none" });
  expect(lines[0]).toMatchObject({ minutes: "track 1.5", blocks: "1 (track)", guesses: "4, 3 correct" });
  expect(lines[0].created).toMatch(/^2026-10-19 /);
});

test("the comparison lays the two recipes side by side to two decimals, every path, site and phase of either side a row, n/a where a side has no value", () => {
  const rows = compareRows(track(0.4), { ...track(0.5), runs: { "1": { count: 2, duration_s: q(4) } }, goal_share: { "1": 1, "2": 0, "3": 0, "4": 0 } });
  const row = (label: string) => rows.find((r) => r.label === label)!;
  expect(row("speed (m/s) median")).toEqual({ label: "speed (m/s) median", real: "0.40", synthetic: "0.50" });
  expect(row("blocks")).toEqual({ label: "blocks", real: "2", synthetic: "2" });
  expect(row("runs on path 9")).toEqual({ label: "runs on path 9", real: "3", synthetic: "n/a" });
  expect(row("run duration on path 9 (s) median").synthetic).toBe("n/a");
  expect(row("dwell at goal (s) median").real).toBe("6.00");
  expect([row("trips per minute").real, row("goal share, path 1").synthetic, row("phase share dwell").real]).toEqual(["2.50", "1.00", "0.40"]);
  expect(rows.some((r) => r.label.startsWith("boundary distance"))).toBe(false);
  const both = compareRows(arena, arena);
  expect(both.find((r) => r.label === "boundary distance (m) median")).toEqual({ label: "boundary distance (m) median", real: "0.10", synthetic: "0.10" });
  expect(both.find((r) => r.label === "pause duration (s) median")!.real).toBe("n/a");
  expect(both.some((r) => r.label.startsWith("runs on path"))).toBe(false);
  expect([fixed(-0.001), fixed(-0), fixed(-0.006), fixed(null)]).toEqual(["0.00", "0.00", "-0.01", "n/a"]);
});

test("a kind one side lacks still gets its table, with a note saying which side and the other side's numbers", () => {
  const tables = compareTables({ arena, track: track(0.4) }, { track: track(0.4) });
  expect(tables.map((t) => [t.kind, t.note])).toEqual([["arena", "the set has no arena blocks"], ["track", ""]]);
  expect(tables[0].rows.find((r) => r.label === "speed (m/s) median")).toEqual({ label: "speed (m/s) median", real: "0.20", synthetic: "n/a" });
  expect(compareTables({ track: track(0.4) }, { arena, track: track(0.4) })[0].note).toBe("the sources have no arena blocks");
  expect(compareCaption("syn_1", ["A", "B"], 3)).toMatch(/^Each row is one recipe number, measured the same way on the real blocks of A, B \(left\) and on the blocks of set syn_1 \(right, seed 3\)/);
});

test("the form sends seconds per kind for the kinds given minutes, only built sessions are sources, and the button says why it is off", () => {
  expect(lengthsOf({ arena: 10, track: 20 })).toEqual({ arena: 600, track: 1200 });
  expect(lengthsOf({ arena: 0, track: 1.5 })).toEqual({ track: 90 });
  const rows = [{ session_id: "A", built: 2 }, { session_id: "B", built: 0 }] as SessionRow[];
  expect(sourceChoices(rows).map((r) => r.session_id)).toEqual(["A"]);
  expect(generateBlocked([], 3, { arena: 10, track: 20 })).toBe("choose at least one source session");
  expect(generateBlocked(["A"], 1.5, { arena: 10, track: 20 })).toBe("the seed must be a whole number, 0 or more");
  expect(generateBlocked(["A"], 3, { arena: 0, track: 0 })).toBe("give at least one kind some minutes");
  expect(generateBlocked(["A"], 0, { arena: 0, track: 20 })).toBe("");
  expect(generatedText({ set_id: "syn_1", built: 2, failed: [], warnings: [], kinds: ["arena", "track"] })).toBe("Generated set syn_1: 2 blocks built (arena, track), 0 failed");
  expect(generatedText({ set_id: "syn_1", built: 1, failed: [{ block_id: "x", problems: ["p"] }], warnings: ["w1", "w2"], kinds: ["track"] })).toBe("Generated set syn_1: 1 block built (track), 1 failed. w1");
});
