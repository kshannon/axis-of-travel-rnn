import { beforeEach, expect, test, vi } from "vitest";
import * as client from "../../src/api/client";
import type { Edit, MadeBlock, Preview, ReviewBlock, SessionArrays, SessionHeader, WindowSettings } from "../../src/api/types";
import { Workspace } from "../../src/session/workspace";

vi.mock("../../src/api/client");

const SETTINGS: WindowSettings = { window_s: 40, stride_s: 10, burn_in_s: 1, horizon_s: 0.5, rate_hz: 20, min_heading_measured: 0.8, min_complete_trips: 1 };
const SHORTER: WindowSettings = { ...SETTINGS, window_s: 5 };

const block = (frame_start: number, status: ReviewBlock["status"]): MadeBlock => ({
  block_id: `S_arena_${frame_start}`, epoch: "arena", environment: "open_arena", frame_start, frame_end: frame_start + 999, status, note: null,
  windows: null, problems: [],
});

function preview(statuses: ReviewBlock["status"][], refused: string[] = []): Preview {
  return {
    blocks: statuses.map((status, i) => block(1 + 2000 * i, status)), cuts: [], flagged_runs: [],
    refusals: refused.map((reason, index) => ({ index, op: "drop", reason })),
  };
}

// The server stands in as a function of the edit list: each drop edit removes one more block.
function serverDropping(nBlocks = 3) {
  return vi.fn(async (_id: string, { edits }: { edits: Edit[] }) =>
    preview(Array.from({ length: nBlocks }, (_, i) => (i < edits.filter((e) => e.op === "drop").length ? "dropped" : "auto"))));
}

function workspace(first = preview(["auto", "auto", "auto"])) {
  const header = { session_id: "S", n_frames: 6000, rate_hz: 60 } as SessionHeader;
  const arrays = { speed: new Float64Array([1, 2, NaN, 3]) } as SessionArrays;
  return new Workspace({ header, arrays, settings: SETTINGS, saved: null, preview: first });
}

beforeEach(() => vi.resetAllMocks());

test("an edit the server applies joins the list and the blocks are the server's answer", async () => {
  vi.mocked(client.previewEdits).mockImplementation(serverDropping());
  const ws = workspace();
  const drop: Edit = { op: "drop", frame: 1 };
  expect(await ws.edit(() => drop)).toBe(drop);
  expect(ws.editor.edits).toEqual([drop]);
  expect(ws.preview.blocks.map((b) => b.status)).toEqual(["dropped", "auto", "auto"]);
  expect(client.previewEdits).toHaveBeenCalledWith("S", { edits: [drop], settings: SETTINGS });
});

test("an edit the server refuses gives back the server's reason and changes nothing", async () => {
  vi.mocked(client.previewEdits).mockResolvedValue(preview(["auto", "auto", "auto"], ["the server's reason"]));
  const ws = workspace();
  expect(await ws.edit(() => ({ op: "new", frame_start: 1, frame_end: 5 }))).toBe("the server's reason");
  expect(ws.editor.edits).toEqual([]);
});

test("an edit refused earlier does not refuse a new one, an edit that changes nothing is refused", async () => {
  vi.mocked(client.previewEdits).mockImplementation(async () => preview(["auto", "auto", "auto"], ["old reason"]));
  const ws = workspace(preview(["auto", "auto", "auto"], ["old reason"]));
  expect(await ws.edit(() => ({ op: "accept" }))).toBe("That changes nothing.");
  expect(ws.editor.edits).toEqual([]);
});

test("edits made at once are applied one after the other, each on top of the last", async () => {
  vi.mocked(client.previewEdits).mockImplementation(serverDropping());
  const ws = workspace();
  const results = await Promise.all([1, 2].map((frame) => ws.edit(() => ({ op: "drop", frame }))));
  expect(results).toEqual([{ op: "drop", frame: 1 }, { op: "drop", frame: 2 }]);
  expect(ws.editor.edits.map((e) => e.op === "drop" && e.frame)).toEqual([1, 2]);
  expect(ws.preview.blocks.map((b) => b.status)).toEqual(["dropped", "dropped", "auto"]);
});

test("undo takes the last edit back and previews the shorter list, reset previews none", async () => {
  vi.mocked(client.previewEdits).mockImplementation(serverDropping());
  const ws = workspace();
  expect(await ws.undo()).toBeUndefined();
  await ws.edit(() => ({ op: "drop", frame: 1 }));
  await ws.edit(() => ({ op: "drop", frame: 2 }));
  expect(await ws.undo()).toEqual({ op: "drop", frame: 2 });
  expect(ws.preview.blocks.map((b) => b.status)).toEqual(["dropped", "auto", "auto"]);
  await ws.reset();
  expect([ws.editor.edits, ws.preview.blocks.map((b) => b.status)]).toEqual([[], ["auto", "auto", "auto"]]);
});

test("a failed preview leaves the edits as they were and the next change still runs", async () => {
  vi.mocked(client.previewEdits).mockRejectedValueOnce(new Error("down")).mockImplementation(serverDropping());
  const ws = workspace();
  await expect(ws.edit(() => ({ op: "drop", frame: 1 }))).rejects.toThrow("down");
  expect(ws.editor.edits).toEqual([]);
  expect(await ws.edit(() => ({ op: "drop", frame: 1 }))).toEqual({ op: "drop", frame: 1 });
});

test("a save sends the edits, the note and the settings, marks the edits saved and keeps the review and the result the server gave", async () => {
  const review = { edits: [{ op: "accept" }], reviewed_by: "kyle" } as never;
  const result = { review, replaced: false, file: "review/S.json", built: 1, failed: [], build_error: null };
  vi.mocked(client.saveBlocks).mockResolvedValue(result);
  const ws = workspace();
  ws.editor.push({ op: "accept" });
  expect(ws.editor.dirty).toBe(true);
  expect(await ws.save("a note")).toBe(result);
  expect(client.saveBlocks).toHaveBeenCalledWith("S", { edits: [{ op: "accept" }], notes: "a note", settings: SETTINGS });
  expect([ws.editor.dirty, ws.saved]).toEqual([false, review]);
});

test("a save the server refuses leaves the edits unsaved", async () => {
  vi.mocked(client.saveBlocks).mockRejectedValue(new Error("some blocks are still auto"));
  const ws = workspace();
  ws.editor.push({ op: "accept" });
  await expect(ws.save("")).rejects.toThrow("still auto");
  expect([ws.editor.dirty, ws.saved]).toEqual([true, null]);
});

test("opening the session already open keeps its edits and previews them again at other settings, at the same settings it asks nothing", async () => {
  vi.mocked(client.previewEdits).mockResolvedValue(preview(["confirmed", "auto", "auto"]));
  const ws = workspace();
  Workspace.current = ws;
  ws.editor.push({ op: "accept" });
  expect(await Workspace.open("S", { ...SETTINGS })).toBe(ws);
  expect(client.previewEdits).not.toHaveBeenCalled();
  expect(await Workspace.open("S", SHORTER)).toBe(ws);
  expect(client.previewEdits).toHaveBeenCalledWith("S", { edits: [{ op: "accept" }], settings: SHORTER });
  expect([ws.settings, ws.editor.edits.length, ws.preview.blocks[0].status]).toEqual([SHORTER, 1, "confirmed"]);
  Workspace.current = null;
});

test("opening another session drops the open one's edits only while they are unsaved", () => {
  const ws = workspace();
  Workspace.current = ws;
  expect(Workspace.unsavedWhenOpening("T")).toBeNull();
  ws.editor.push({ op: "accept" });
  expect(Workspace.unsavedWhenOpening("T")).toBe(ws);
  expect(Workspace.unsavedWhenOpening("S")).toBeNull();
  ws.editor.markSaved();
  expect(Workspace.unsavedWhenOpening("T")).toBeNull();
  Workspace.current = null;
});

test("excluding a session keeps the edits not saved and takes the flag and the review the server wrote, and the open workspace answers for its own session", async () => {
  const review = { edits: [], notes: "camera moved", excluded: true } as never;
  const result = { review, replaced: false, file: "review/S.json", deleted: false, built: 0, failed: [], build_error: null };
  vi.mocked(client.setExclusion).mockResolvedValue(result);
  const ws = workspace();
  Workspace.current = ws;
  ws.editor.push({ op: "accept" });
  expect(await Workspace.exclude("S", true, "camera moved", SETTINGS)).toEqual(result);
  expect(client.setExclusion).toHaveBeenCalledWith("S", true, "camera moved", SETTINGS);
  expect([ws.excluded, ws.saved, ws.editor.dirty]).toEqual([true, review, true]);
  await Workspace.exclude("other", false, "", SHORTER);
  expect(client.setExclusion).toHaveBeenLastCalledWith("other", false, "", SHORTER);
  expect(ws.excluded).toBe(true);
  Workspace.current = null;
});

test("including a session whose review only recorded the exclusion leaves the workspace with no saved review", async () => {
  vi.mocked(client.setExclusion).mockResolvedValue({ review: null, replaced: false, file: "review/S.json", deleted: true, built: 0, failed: [], build_error: null });
  const ws = workspace();
  ws.excluded = true;
  await ws.setExclusion(false, "");
  expect([ws.excluded, ws.saved]).toEqual([false, null]);
  expect(client.setExclusion).toHaveBeenCalledWith("S", false, "", SETTINGS);
});
