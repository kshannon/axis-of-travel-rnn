import { expect, test } from "vitest";
import type { MadeBlock, Preview, ReviewBlock, SavedBlocks, SessionArrays, SessionHeader } from "../api/types";
import { blockCards, factsLine, liveTiles, marksLine, saveToast, sessionNotes, settingsLine, stateLine, summaryTiles } from "./replay-view";

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

// What the manager answers for a kept block, and for a removed one.
const OK = { count: 2, verdict: { ok: true, reasons: [] } };
const TROUBLE = { count: 0, verdict: { ok: false, reasons: ["no window fits", "measured heading 60% under 80%"] } };
const block = (frame_start: number, frame_end: number, status: ReviewBlock["status"], windows: MadeBlock["windows"] = status === "dropped" ? null : OK, problems: string[] = []): MadeBlock =>
  ({ block_id: `S_${frame_start}`, epoch: "arena", environment: "e", frame_start, frame_end, status, note: null, windows, problems });

const blocks = [block(301, 900, "confirmed"), block(901, 1500, "auto", TROUBLE, ["position not finite on 3 frames"]), block(1501, 1800, "dropped")];
const preview: Preview = { blocks, cuts: [], flagged_runs: [2], refusals: [] };

test("a card per block in time order, with the runs that start inside it and what its toggles may do", () => {
  const cards = blockCards(blocks, header, blocks[1]);
  expect(cards.map((c) => [c.name, c.minutes, c.runs, c.glyph, c.selected])).toEqual([
    ["block 1", "0.17", 1, "☑", false], ["block 2", "0.17", 0, "☐", true], ["block 3", "0.08", 1, "✕", false],
  ]);
  expect(cards.map((c) => [c.accepted, c.removed, c.acceptable])).toEqual([[true, false, true], [false, false, true], [false, true, false]]);
  expect(blockCards([block(1, 600, "edited")], header, null)[0]).toMatchObject({ accepted: true, acceptable: false });
});

test("two blocks that start on the same frame are told apart by their place and only the selected one is selected", () => {
  const removed = block(301, 1500, "dropped");
  const made = block(301, 1299, "edited");
  const cards = blockCards([removed, made], header, made);
  expect(cards.map((c) => [c.position, c.selected])).toEqual([[0, false], [1, true]]);
});

test("a card shows the manager's window count and verdict, the problems of the block's frames, and nothing to count for a removed block", () => {
  const cards = blockCards(blocks, header, null);
  expect(cards.map((c) => [c.windows, c.windowsText, c.verdict, c.ok])).toEqual([
    [2, "2 training windows", "ok", true],
    [0, "0 training windows", "no window fits, measured heading 60% under 80%", false],
    [null, "removed, yields nothing", "", true],
  ]);
  expect(cards.map((c) => c.problems)).toEqual([[], ["position not finite on 3 frames"], []]);
  expect(blockCards([block(1, 600, "auto", { count: 1, verdict: OK.verdict })], header, null)[0].windowsText).toBe("1 training window");
});

test("the summary counts the blocks by status and the time kept of the epochs the processor cuts", () => {
  const tiles = Object.fromEntries(summaryTiles(preview, header, SETTINGS).map((t) => [t.label, t]));
  expect([tiles.automatic.value, tiles.confirmed.value, tiles.edited.value, tiles.removed.value]).toEqual(["1", "1", "0", "1"]);
  expect(tiles.kept).toMatchObject({ value: "0.3 min", note: "67%" }); // 20 s kept of the arena's 30 s, the variant epoch is not cut
  expect(tiles.windows).toMatchObject({ value: "2", note: "5 s each" }); // the manager's counts summed: 2 for the confirmed block, 0 for the auto one, the removed one has none
  expect(tiles.windows.title).toContain("1 block not ok");
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
  expect(liveTiles(header, arrays, 0)).toEqual({ time: "0.00 s", frame: "1", speed: "10.40 m/s", lights: "2", run: "none" });
  expect(liveTiles(header, arrays, 1).speed).toBe("n/a");
  const inRun = { ...arrays, t: new Float64Array(500), speed: new Float64Array(500), n_lights: new Int8Array(500) } as SessionArrays;
  expect(liveTiles(header, inRun, 449).run).toBe("1, path 1 clean");
});

test("the settings in use are one line a person can read", () => {
  expect(settingsLine({ ...SETTINGS, window_s: 40, min_heading_measured: 0.8 })).toBe(
    "window 40 s, stride 5 s, burn-in 1 s, horizon 0 s, heading measured at least 80%, at least 1 complete trip, resampled at 20 Hz");
});

test("the session notes say why a session is out of the dataset, the warnings, the saved edits that do not apply and the positions off the map", () => {
  const edits = [{ op: "accept" }, { op: "split", frame: 700 }] as never;
  const quiet = { ...header, in_dataset: true, reason: null, warnings: [], occupancy: { outside: 0 } } as unknown as SessionHeader;
  expect(sessionNotes(quiet, [], edits)).toEqual([]);
  const noisy = { ...quiet, in_dataset: false, reason: "protocol rotation", warnings: ["reviewed under other rules"], occupancy: { outside: 1 } } as unknown as SessionHeader;
  const notes = sessionNotes(noisy, [{ index: 1, op: "split", reason: "no block holds frame 700" }], edits);
  expect(notes.map((n) => n.text)).toEqual([
    "Not in the dataset: protocol rotation. It can be viewed and previewed, Save blocks is disabled.",
    "reviewed under other rules",
    "Edit 2 (split at frame 700) is not applied under the current rules: no block holds frame 700",
    "1 position outside the room, drawn outside its outline.",
  ]);
  expect(notes.map((n) => n.tone)).toEqual(["text-warn", "text-warn", "text-warn", "text-muted"]);
});

test("a save toast names the review file and the blocks built, and warns on a failed build with the blocks and why", () => {
  const saved: SavedBlocks = { review: {} as never, replaced: false, file: "review/S1.json", built: 2, failed: [], build_error: null };
  expect(saveToast(saved)).toEqual({ kind: "success", text: "Saved, a new file, built 2 blocks", path: "review/S1.json" });
  expect(saveToast({ ...saved, replaced: true, built: 1 }).text).toBe("Saved, replacing the earlier review, built 1 block");
  const failed = saveToast({ ...saved, built: 1, failed: [{ block_id: "S1_track_01", problems: ["position not finite on 3 frames", "t steps irregular"] }] });
  expect(failed).toEqual({
    kind: "warning", path: "review/S1.json",
    text: "Saved, a new file, built 1 block, but 1 failed: S1_track_01 (position not finite on 3 frames, t steps irregular)",
  });
  const broken = saveToast({ ...saved, built: 0, build_error: "OSError: disk full" });
  expect(broken).toEqual({ kind: "warning", path: "review/S1.json", text: "Saved, a new file, but the build failed and nothing was built: OSError: disk full" });
});

test("the facts line tells the rat, the recording and how many blocks the rules cut", () => {
  expect(factsLine({ ...header, n_initial_blocks: 2 } as SessionHeader)).toBe("rat NS14, 2015-01-01, standard, 60 Hz, 6000 frames, 2 blocks cut by the rules");
});
