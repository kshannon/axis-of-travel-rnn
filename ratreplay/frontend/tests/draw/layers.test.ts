import { expect, test } from "vitest";
import type { SessionHeader } from "../../src/api/types";
import { allLayers, LAYERS, layerMeanings } from "../../src/draw/layers";

const header = {
  max_gap: 12,
  rules: { pause_step_s: 0.1, gap_lights: "both", jump_px: 40, pause_margin_s: 5, heading_fill_s: 3, running_floor_m_per_s: 0.03 },
} as unknown as SessionHeader;

test("every layer says what it means with the numbers of the session's own rules", () => {
  const meanings = layerMeanings(header, 0.85);
  expect(Object.keys(meanings)).toEqual(LAYERS.map((layer) => layer.key));
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
    "tracking lost", "position jumped", "margins trimmed",
    "head dir missing", "head dir interpolated by RatReplay", "head dir held by RatReplay", "speed",
  ]);
});

test("the seven layers draw in seven colours of their own, none borrowed from the bars, the trips or the problem colour", () => {
  const tokens = LAYERS.map((layer) => layer.colour);
  expect(new Set(tokens).size).toBe(7);
  for (const token of tokens) expect(token).toMatch(/^var\(--[\w-]+\)$/);
  expect(tokens.filter((token) => ["var(--accent)", "var(--bad)", "var(--soft)", "var(--trip)"].includes(token))).toEqual([]);
});

test("a pause is not a layer, it is dead time drawn whatever the layers are", () => {
  expect(LAYERS.map((layer) => layer.key)).not.toContain("pauses");
  expect(Object.keys(allLayers())).toEqual(LAYERS.map((layer) => layer.key));
});
