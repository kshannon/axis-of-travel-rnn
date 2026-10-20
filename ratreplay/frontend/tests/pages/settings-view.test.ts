import { expect, test } from "vitest";
import type { Selected, WindowSettings } from "../../src/api/types";
import { atDefaults, compareSettings, fieldRows, judgedLine, ruleRows, SETTING_FIELDS, selectedLine, settingsLine, testedLine } from "../../src/pages/settings-view";

const DEFAULTS: WindowSettings = { window_s: 40, stride_s: 10, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1 };

test("there is a field with a hint for each of the seven settings the API knows, and the default of each stands beside it", () => {
  expect(SETTING_FIELDS.map((field) => field.key).sort()).toEqual(Object.keys(DEFAULTS).sort());
  expect(SETTING_FIELDS.every((field) => field.hint.length > 0 && !field.hint.includes("\n"))).toBe(true);
  expect(fieldRows(DEFAULTS).map((field) => [field.key, field.default])).toEqual(SETTING_FIELDS.map((field) => [field.key, String(DEFAULTS[field.key])]));
  expect(fieldRows(null).every((field) => field.default === "")).toBe(true);
});

test("the settings are at their defaults only when every one is, and nothing is until the defaults are known", () => {
  expect(atDefaults({ ...DEFAULTS }, DEFAULTS)).toBe(true);
  expect(atDefaults({ ...DEFAULTS, stride_s: 5 }, DEFAULTS)).toBe(false);
  expect(atDefaults({ ...DEFAULTS }, null)).toBe(false);
});

test("the sentence under the fields spells out the settings, the line on the Blocks page and the short line say them again", () => {
  expect(testedLine(DEFAULTS)).toBe("Verdicts at a 40 s window plus a 0.5 s horizon every 10 s, measured heading at least 80%, a track block with at least 1 complete trip.");
  expect(testedLine({ ...DEFAULTS, window_s: 5, min_complete_trips: 2 })).toContain("a 5 s window plus a 0.5 s horizon every 10 s");
  expect(testedLine({ ...DEFAULTS, min_complete_trips: 2 })).toContain("at least 2 complete trips");
  expect(settingsLine(DEFAULTS)).toBe("40 s window, 10 s stride, 1 s burn-in, 0.5 s horizon, 20 Hz, min 80% heading measured, min 1 complete trip");
  expect(judgedLine(DEFAULTS)).toBe(`judged at: ${settingsLine(DEFAULTS)}`);
  expect(judgedLine(DEFAULTS, "real lab blocks")).toBe(`judged at: real lab blocks, ${settingsLine(DEFAULTS)}`);
});

test("the selection line says none was selected, or when, by whom, the settings and what they gave", () => {
  expect(selectedLine(null)).toBe("No settings are selected for export yet.");
  const selected: Selected["selected"] = {
    settings: { ...DEFAULTS, window_s: 5 }, totals: { blocks: 3, ok: 2, trouble: 1, windows: 9, windows_ok: 4 }, selected_at: "2026-10-18T10:00:00+00:00", selected_by: "kyle",
  };
  expect(selectedLine(selected)).toMatch(/^Selected for export .* by kyle: a 5 s window every 10 s, .*They gave 2 of 3 blocks ok and 4 windows in them\.$/);
});

test("settings beside the ones a session was built with differ only where the values do", () => {
  const rows = compareSettings(DEFAULTS, { ...DEFAULTS, window_s: 5 });
  expect(rows).toHaveLength(7);
  expect(rows.filter((row) => row.differs)).toEqual([{ label: "window (s)", tried: "40", built: "5", differs: true }]);
});

test("the rules come in the engine's order with their values written plainly and a meaning each, a rule without one is still listed", () => {
  const rows = ruleRows({ condition: "baseline", epochs: ["arena", "track"], jump_px: 40, return_paths: [9, 10], rule_from_the_future: 1 });
  expect(rows.map((row) => [row.name, row.value])).toEqual([
    ["condition", "baseline"], ["epochs", "arena, track"], ["jump_px", "40"], ["return_paths", "9, 10"], ["rule_from_the_future", "1"],
  ]);
  expect(rows.slice(0, 4).every((row) => row.meaning.length > 0)).toBe(true);
  expect(rows[4].meaning).toBe("");
});
