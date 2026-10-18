import { expect, test } from "vitest";
import type { MadeBlock, Preview, ReviewBlock, SessionArrays, SessionHeader } from "../api/types";
import { blockCards, liveTiles, marksLine, stateLine, summaryTiles } from "./replay-view";

const SETTINGS = { window_s: 5, stride_s: 5, burn_in_s: 1, horizon_s: 0, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1 };

const header = {
  rate_hz: 60, n_frames: 6000, subject_id: "NS14", date: "2015-01-01", protocol: "standard", group: "NS14Data", selected_epochs: ["arena", "track"],
  epochs: [{ epoch: "arena", frame_start: 1, frame_end: 1800, duration_s: 30 }, { epoch: "variant", frame_start: 1801, frame_end: 3600, duration_s: 30 }],
  runs: [{ run: 1, epoch: "track", path_id: 1, clean: true, frame_start: 400, frame_end: 500 }, { run: 2, epoch: "track", path_id: 9, clean: false, frame_start: 1600, frame_end: 1700 }],
  cut_points: [
    { frame: 10, reason: "pause" }, { frame: 20, reason: "jump" }, { frame: 30, reason: "jump" }, { frame: 40, frame_end: 50, reason: "gap" },
  ],
  margins: [],
} as unknown as SessionHeader;

const block = (frame_start: number, frame_end: number, status: ReviewBlock["status"]): MadeBlock =>
  ({ block_id: `S_${frame_start}`, epoch: "arena", environment: "e", frame_start, frame_end, status, note: null, windows: null, problems: [] });

const blocks = [block(301, 900, "confirmed"), block(901, 1500, "auto"), block(1501, 1800, "dropped")];
const preview: Preview = { blocks, cuts: [], flagged_runs: [2], refusals: [] };

test("a card per block in time order, with the runs that start inside it and what its toggles may do", () => {
  const cards = blockCards(blocks, header, blocks[1], SETTINGS);
  expect(cards.map((c) => [c.name, c.minutes, c.runs, c.glyph, c.selected])).toEqual([
    ["block 1", "0.17", 1, "☑", false], ["block 2", "0.17", 0, "☐", true], ["block 3", "0.08", 1, "✕", false],
  ]);
  expect(cards.map((c) => [c.accepted, c.removed, c.acceptable])).toEqual([[true, false, true], [false, false, true], [false, true, false]]);
  expect(blockCards([block(1, 600, "edited")], header, null, SETTINGS)[0]).toMatchObject({ accepted: true, acceptable: false });
});

test("two blocks that start on the same frame are told apart by their place and only the selected one is selected", () => {
  const removed = block(301, 1500, "dropped");
  const made = block(301, 1299, "edited");
  const cards = blockCards([removed, made], header, made, SETTINGS);
  expect(cards.map((c) => [c.position, c.selected])).toEqual([[0, false], [1, true]]);
});

test("a card tells the training windows the block yields at the settings and a block shorter than one window yields none", () => {
  const cards = blockCards([block(1, 600, "auto"), block(601, 900, "auto"), block(901, 1000, "auto")], header, null, { ...SETTINGS, window_s: 8 });
  expect(cards.map((c) => [c.windows, c.windowsText])).toEqual([[1, "1 training window"], [0, "shorter than one window"], [0, "shorter than one window"]]);
  expect(blockCards([block(1, 1200, "auto")], header, null, SETTINGS)[0].windowsText).toBe("4 training windows");
});

test("the summary counts the blocks by status and the time kept of the epochs the processor cuts", () => {
  const tiles = Object.fromEntries(summaryTiles(preview, header, SETTINGS).map((t) => [t.label, t]));
  expect([tiles.automatic.value, tiles.confirmed.value, tiles.edited.value, tiles.removed.value]).toEqual(["1", "1", "0", "1"]);
  expect(tiles.kept).toMatchObject({ value: "0.3 min", note: "67%" }); // 20 s kept of the arena's 30 s, the variant epoch is not cut
  expect(tiles.windows.value).toBe("4"); // two blocks of 10 s at 5 s windows every 5 s
  expect(tiles["pauses, jumps, gaps"].value).toBe("1, 2, 1");
  expect(tiles.flagged).toMatchObject({ value: "1", note: "of 2 runs" });
});

test("the state line says automatic or who saved and when, and the edits not saved yet", () => {
  const saved = { reviewed_by: "kyle", reviewed_at: "2026-10-16T12:00:00+00:00", edits: [{}, {}] } as never;
  expect(stateLine(null, 0, false, 0)).toBe("automatic");
  expect(stateLine(null, 3, true, 0)).toBe("automatic, now 3 edits not saved yet");
  expect(stateLine(null, 1, true, 0)).toBe("automatic, now 1 edit not saved yet");
  expect(stateLine(saved, 2, false, 1)).toMatch(/^saved .* by kyle, 2 edits, 1 skipped under the current rules$/);
  expect(stateLine(saved, 3, true, 0)).toMatch(/by kyle, 2 edits, now 3 edits not saved yet$/);
  expect(stateLine(saved, 0, true, 0)).toBe("automatic, the saved review on disk is not loaded");
});

test("the marks line follows the marks", () => {
  expect(marksLine(null, null, 60)).toBe("No range marked.");
  expect(marksLine(300, null, 60)).toMatch(/Marked frame 300/);
  expect(marksLine(1500, 900, 60)).toBe("Marked frames 900 to 1500, 10.0 s.");
});

test("the live tiles read the arrays at the frame index and the run under the lab frame", () => {
  const arrays = { t: new Float64Array([0, 0.5, 1]), speed: new Float64Array([10.4, NaN, 3]), n_lights: new Int8Array([2, 2, 1]) } as SessionArrays;
  expect(liveTiles(header, arrays, 0)).toEqual({ time: "0.00 s", frame: "1", speed: "10 px/s", lights: "2", run: "none" });
  expect(liveTiles(header, arrays, 1).speed).toBe("n/a");
  const inRun = { ...arrays, t: new Float64Array(500), speed: new Float64Array(500), n_lights: new Int8Array(500) } as SessionArrays;
  expect(liveTiles(header, inRun, 449).run).toBe("1, path 1 clean");
});
