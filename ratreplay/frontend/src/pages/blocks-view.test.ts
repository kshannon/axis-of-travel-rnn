import { expect, test } from "vitest";
import type { BlockRow, Readiness, ReadinessBlock, Selected, WindowSettings } from "../api/types";
import { blockLine, COLUMNS, indexFacts, indexRows, selectedLine, totalTiles, verdictText } from "./blocks-view";

const TRIED: WindowSettings = { window_s: 5, stride_s: 10, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1 };
const LONGER: WindowSettings = { ...TRIED, window_s: 40, min_complete_trips: 2 };

const block = (id: string, session: string, verdict = { ok: true, reasons: [] as string[] }): ReadinessBlock => ({
  block_id: id, session_id: session, kind: "track", status: "auto", duration_s: 120, n_runs: 6, n_trips: 4, n_complete_trips: 3,
  heading_filled_s: 12, heading_held_s: 0, count: 3, verdict, reviewed_by: null, environment: "track", subject_id: "NS14", date: "2015-01-01",
  protocol: "track", frame_start: 1, frame_end: 7200, scale_px_per_m: 300, rotation_rad: 0, led_offset_rad: 0, kinematics_version: 2,
} as unknown as ReadinessBlock);

const readiness: Readiness = {
  which: "real", settings: TRIED, totals: { blocks: 3, ok: 2, trouble: 1, windows: 9, windows_ok: 6 },
  blocks: [block("A_track_01", "A"), block("B_track_01", "B", { ok: false, reasons: ["no window fits", "0 complete trips under 1"] }), block("A_track_02", "A")],
  built: { A: { settings: TRIED, built_at: "2026-10-18T10:00:00+00:00" }, B: { settings: LONGER, built_at: "2026-10-17T10:00:00+00:00" } },
};

test("a block is marked when its session was built at other settings than the ones tried, and the comparison names those settings", () => {
  const [a, b, again] = indexRows(readiness);
  expect([a.otherSettings, b.otherSettings, again.otherSettings]).toEqual([false, true, false]);
  expect(a.compare.some((setting) => setting.differs)).toBe(false);
  expect(b.compare.filter((setting) => setting.differs)).toEqual([
    { label: "window (s)", tried: "5", built: "40", differs: true }, { label: "min complete trips", tried: "1", built: "2", differs: true },
  ]);
  expect(b.builtAt).toBe("2026-10-17T10:00:00+00:00");
  expect(indexFacts(b).at(-1)?.label).toBe("session built");
});

test("the verdict column shows ok or every reason, and the built column sorts the blocks built at other settings apart", () => {
  const [a, b] = indexRows(readiness);
  const column = (key: string) => COLUMNS.find((c) => c.key === key)!;
  expect([column("verdict").text(a), column("verdict").text(b)]).toEqual(["ok", "trouble, no window fits, 0 complete trips under 1"]);
  expect([column("built").text(a), column("built").text(b)]).toEqual(["as tried", "built at other settings"]);
  expect(column("built").value(a)).toBeLessThan(column("built").value(b) as number);
});

test("the totals are shown as the API returned them", () => {
  expect(totalTiles(readiness.totals).map((tile) => [tile.label, tile.value])).toEqual([
    ["blocks", "3"], ["ok", "2"], ["trouble", "1"], ["windows", "9"], ["windows, ok blocks", "6"],
  ]);
});

test("the header line of a block carries its verdict with the reasons", () => {
  const row = block("B_track_01", "B") as BlockRow;
  expect(blockLine(row, { ok: true, reasons: [] })).toMatchObject({ id: "B_track_01", session: "B", minutes: "2.0", ok: true, verdict: "ok" });
  expect(verdictText({ ok: false, reasons: ["no window fits"] })).toBe("trouble, no window fits");
});

test("the selection line says none when none was selected, else the settings, who and what they gave", () => {
  expect(selectedLine(null)).toBe("No settings are selected for export yet.");
  const selected: NonNullable<Selected["selected"]> = { settings: TRIED, totals: readiness.totals, selected_at: "2026-10-18T10:00:00+00:00", selected_by: "kyle" };
  const line = selectedLine(selected);
  expect(line).toContain("by kyle: a 5 s window every 10 s");
  expect(line).toContain("They gave 2 of 3 blocks ok and 6 windows in them.");
});
