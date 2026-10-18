import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { allLayers, LAYERS } from "../../src/draw/layers";
import { runFill } from "../../src/draw/lanes";
import { sessionScene } from "../../src/draw/session-scene";
import type { SessionHeader } from "../../src/api/types";
import { colourOf, PALETTE_NAMES } from "../../src/ui/palette";
import type { Palette } from "../../src/ui/palette";

const css = readFileSync(new URL("../../src/styles.css", import.meta.url), "utf8");
const themeOf = (selector: string): Record<string, string> => {
  const block = css.split(`${selector} {`)[1].split("}")[0];
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6});/g)].map(([, name, hex]) => [name, hex]));
};
const LIGHT = themeOf(":root");
const DARK = themeOf(":root.dark");

test("both themes define every colour of the palette as a hex", () => {
  for (const theme of [LIGHT, DARK]) expect(PALETTE_NAMES.filter((name) => !theme[name])).toEqual([]);
  // the margins are light on the dark theme and dark on the light theme
  expect(DARK.margin).not.toBe(LIGHT.margin);
});

test("a name stands for the theme's colour, as a name or as var(--name), else a CSS colour stands as it is", () => {
  const colours = DARK as Palette;
  expect(colourOf(colours, "bad")).toBe(DARK.bad);
  expect(colourOf(colours, "var(--margin)")).toBe(DARK.margin);
  expect(colourOf(colours, "#123456")).toBe("#123456");
});

test("every colour the timeline names resolves to a theme colour, so a canvas never gets an unknown name", () => {
  const header = {
    rate_hz: 60, n_frames: 600, epochs: [{ epoch: "track", frame_start: 1, frame_end: 600 }, { epoch: "other", frame_start: 1, frame_end: 600 }],
    runs: [1, 9, 5].map((path_id, run) => ({ run, path_id, clean: true, frame_start: 1, frame_end: 10 })),
    cut_points: [], margins: [], heading_spans: { lost: [], filled: [], held: [] },
  } as unknown as SessionHeader;
  const blocks = (["auto", "confirmed", "edited", "dropped"] as const).map((status) => ({ block_id: status, frame_start: 1, frame_end: 10, status, windows: null }));
  const scene = sessionScene(header, blocks as never, [0], allLayers(), new Float64Array(0), 1);
  const names = [
    ...scene.bars.flatMap((bar) => [bar.fill, bar.outline ?? bar.fill]), ...scene.frames.flatMap((layer) => (layer.kind === "trace" ? [] : [layer.colour])),
    ...LAYERS.map((layer) => layer.colour), ...[1, 9, 5].map(runFill),
  ];
  for (const theme of [LIGHT, DARK]) for (const name of names) expect(colourOf(theme as Palette, name)).toMatch(/^#[0-9a-f]{6}$/);
});
