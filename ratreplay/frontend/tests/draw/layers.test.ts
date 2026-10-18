import { expect, test } from "vitest";
import type { SessionHeader } from "../../src/api/types";
import { LAYERS, layerMeanings } from "../../src/draw/layers";

const header = {
  max_gap: 12,
  rules: { pause_step_s: 0.1, gap_lights: "both", jump_px: 40, pause_margin_s: 5, heading_fill_s: 3, running_floor_m_per_s: 0.03 },
} as unknown as SessionHeader;

test("every layer says what it means with the numbers of the session's own rules", () => {
  const meanings = layerMeanings(header, 0.85);
  expect(Object.keys(meanings)).toEqual(LAYERS.map((layer) => layer.key));
  expect(meanings.pauses).toContain("0.1 s");
  expect(meanings.gaps).toContain("both lights");
  expect(meanings.gaps).toContain("up to 12 frames");
  expect(meanings.jumps).toContain("40 px");
  expect(meanings.margins).toContain("5 s");
  expect(meanings.filled).toContain("3 s");
  expect(meanings.held).toContain("0.03 m/s");
  expect(meanings.speed).toContain("0.85 m/s");
  // other rules, other words
  const other = layerMeanings({ ...header, max_gap: 30, rules: { ...header.rules, jump_px: 25, gap_lights: "either", heading_fill_s: 1.5 } }, 1);
  expect([other.jumps, other.gaps, other.filled].join(" ")).toMatch(/25 px.*up to 30 frames, a light lost.*1\.5 s/);
});

test("the layers are named by whose work they are", () => {
  expect(LAYERS.map((layer) => layer.label)).toEqual([
    "recording paused", "tracking lost", "position jumped", "margins trimmed",
    "head dir missing", "head dir interpolated by RatReplay", "head dir held by RatReplay", "speed",
  ]);
});
