import { expect, test } from "vitest";
import type { MadeBlock, ReviewBlock, SessionHeader } from "../../src/api/types";
import { allLayers } from "../../src/draw/layers";
import { blockName, sessionScene } from "../../src/draw/session-scene";

const header = {
  rate_hz: 60, n_frames: 36_000,
  epochs: [{ epoch: "track", environment: "triple_t", condition: "baseline", frame_start: 1, frame_end: 36_000, duration_s: 600 }],
  runs: [{ run: 1, epoch: "track", path_id: 1, clean: true, frame_start: 6001, frame_end: 6600 }, { run: 2, epoch: "track", path_id: 9, clean: false, frame_start: 7001, frame_end: 7100 }],
  cut_points: [{ frame: 2701, reason: "pause" }, { frame: 3000, reason: "jump" }, { frame: 10, frame_end: 20, reason: "gap" }], margins: [[21, 30]],
  heading_spans: { lost: [[1, 60]], filled: [[100, 129]], held: [] },
} as unknown as SessionHeader;

const OK = { count: 3, verdict: { ok: true, reasons: [] } };
const block = (frame_start: number, frame_end: number, status: ReviewBlock["status"], windows: MadeBlock["windows"] = status === "dropped" ? null : OK): MadeBlock =>
  ({ block_id: `S_${frame_start}`, epoch: "track", environment: "triple_t", frame_start, frame_end, status, note: null, windows, problems: [] });

const speed = new Float64Array(10);
const scene = (blocks: MadeBlock[], flagged: number[] = [], layers = allLayers()) => sessionScene(header, blocks, flagged, layers, speed, 1);

test("a dirty run is hatched, a flagged run outlined and said so", () => {
  const runs = scene([], [2]).bars.filter((bar) => bar.lane === "runs");
  expect(runs.map((bar) => [bar.hatched, bar.outline])).toEqual([[false, undefined], [true, "bad"]]);
  expect(runs[1].tip).toContain("dirty, flagged,");
});

test("blocks are named by their place in time order, can be picked by it and a removed one is faint", () => {
  const blocks = scene([block(1, 100, "confirmed"), block(200, 300, "dropped")]).bars.filter((bar) => bar.lane === "blocks");
  expect(blocks.map((bar) => [bar.text, bar.short, bar.pick, bar.fill])).toEqual([["block 1", "1", 0, "ok"], ["block 2", "2", 1, "muted"]]);
  expect(blocks[1].alpha).toBeLessThan(blocks[0].alpha!);
  expect(blockName(2)).toBe("block 3");
});

test("a block not judged yet is the same blue as a confirmed one but fainter", () => {
  const [auto, confirmed] = scene([block(1, 100, "auto"), block(200, 300, "confirmed")]).bars.filter((bar) => bar.lane === "blocks");
  expect(auto.fill).toBe("accent");
  expect(auto.alpha).toBeLessThan(confirmed.alpha!);
});

test("the margins are a theme colour drawn fainter than the bars, so the cut under them shows", () => {
  const margins = scene([]).frames.find((layer) => layer.kind === "span" && layer.colour === "var(--margin)");
  expect(margins).toMatchObject({ kind: "span", spans: [[21, 30]] });
  expect((margins as { alpha: number }).alpha).toBeLessThan(0.8);
});

test("a pause is not a toggle, it is a break the scene always carries, and no layer has a tick for it", () => {
  const off = Object.fromEntries(Object.keys(allLayers()).map((key) => [key, false])) as ReturnType<typeof allLayers>;
  expect(scene([], [], off).breaks).toEqual([2701]);
  expect(scene([]).frames.filter((layer) => layer.kind === "tick")).toHaveLength(1); // the jumps alone
});

test("no span of the frames lane runs across a pause: the lost heading, the lost tracking and the margins are split where one falls inside", () => {
  const crossing = {
    ...header,
    heading_spans: { lost: [[2600, 2800]], filled: [[100, 129]], held: [[2701, 2900]] },
    cut_points: [...header.cut_points, { frame: 2650, frame_end: 2750, reason: "gap" }], margins: [[2690, 2710]],
  } as unknown as SessionHeader;
  const layers = sessionScene(crossing, [], [], allLayers(), speed, 1).frames.filter((layer) => layer.kind === "span");
  const spans = layers.flatMap((layer) => (layer as { spans: [number, number][] }).spans);
  expect(spans.filter(([first, last]) => first < 2701 && last >= 2701)).toEqual([]);
  expect(spans).toContainEqual([2600, 2700]);
  expect(spans).toContainEqual([2701, 2800]);
  expect(spans).toContainEqual([2701, 2750]); // the margins trimmed beside the pause still draw on their own frames
  expect(spans).toContainEqual([2690, 2700]);
});

test("the lost tracking is a striped span in the muted violet, and no other layer is striped", () => {
  const gaps = scene([]).frames.find((layer) => layer.kind === "span" && layer.hatched);
  expect(gaps).toMatchObject({ colour: "var(--trip)", spans: [[10, 20]] });
  expect(scene([]).frames.filter((layer) => layer.kind === "span" && layer.hatched)).toHaveLength(1);
});

test("epochs and runs can be picked by their place in the header, as the blocks are by their place in time", () => {
  const bars = scene([block(1, 100, "confirmed")]).bars;
  expect(bars.filter((bar) => bar.lane === "session").map((bar) => bar.pick)).toEqual([0]);
  expect(bars.filter((bar) => bar.lane === "runs").map((bar) => bar.pick)).toEqual([0, 1]);
});
