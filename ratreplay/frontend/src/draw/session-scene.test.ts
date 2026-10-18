import { expect, test } from "vitest";
import type { MadeBlock, ReviewBlock, SessionHeader } from "../api/types";
import { allLayers } from "./layers";
import { blockName, sessionScene, yieldOf } from "./session-scene";

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

test("the bars say what a hover tells of an epoch, a run and a block", () => {
  const bars = scene([block(3001, 9000, "auto")]).bars;
  expect(bars.map((bar) => bar.tip)).toEqual([
    "track, triple_t, baseline, frames 1 to 36000, 10.0 min",
    "run 1, path 1 outbound, clean, 600 frames (6001 to 6600)",
    "run 2, path 9 return, dirty, 100 frames (7001 to 7100)",
    "block 1, auto, frames 3001 to 9000, 100.0 s, 3 windows, ok",
  ]);
});

test("a dirty run is hatched, a flagged run outlined and said so", () => {
  const runs = scene([], [2]).bars.filter((bar) => bar.lane === "runs");
  expect(runs.map((bar) => [bar.hatched, bar.outline])).toEqual([[false, undefined], [true, "bad"]]);
  expect(runs[1].tip).toContain("dirty, flagged,");
});

test("blocks are named by their place in time order, can be picked by it and a removed one is faint", () => {
  const blocks = scene([block(1, 100, "confirmed"), block(200, 300, "dropped")]).bars.filter((bar) => bar.lane === "blocks");
  expect(blocks.map((bar) => [bar.text, bar.pick, bar.fill])).toEqual([["block 1", 0, "ok"], ["block 2", 1, "muted"]]);
  expect(blocks[1].alpha).toBeLessThan(blocks[0].alpha!);
  expect(blockName(2)).toBe("block 3");
});

test("the frames lane holds the layers that are on, the speed trace between the bands and the ticks", () => {
  const kinds = (layers = allLayers()) => scene([], [], layers).frames.map((layer) => layer.kind);
  expect(kinds()).toEqual(["span", "span", "span", "span", "span", "trace", "tick", "tick"]);
  expect(kinds({ ...allLayers(), speed: false, pauses: false, jumps: false, gaps: false })).toEqual(["span", "span", "span", "span"]);
});

test("what a block yields is the manager's count and verdict, the reasons when it is not ok and removed when it has no windows", () => {
  expect(yieldOf(block(1, 100, "confirmed"))).toBe("3 windows, ok");
  expect(yieldOf(block(1, 100, "auto", { count: 1, verdict: { ok: true, reasons: [] } }))).toBe("1 window, ok");
  expect(yieldOf(block(1, 100, "auto", { count: 0, verdict: { ok: false, reasons: ["no window fits", "0 complete trips under 1"] } }))).toBe("0 windows, no window fits, 0 complete trips under 1");
  expect(yieldOf(block(1, 100, "dropped"))).toBe("removed");
});
