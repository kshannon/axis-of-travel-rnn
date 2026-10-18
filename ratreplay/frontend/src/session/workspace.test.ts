import { beforeEach, expect, test, vi } from "vitest";
import * as client from "../api/client";
import type { Edit, MadeBlock, Preview, ReviewBlock, SessionArrays, SessionHeader, WindowSettings } from "../api/types";
import { Workspace } from "./workspace";

vi.mock("../api/client");

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
  vi.mocked(client.previewEdits).mockResolvedValue(preview(["auto", "auto", "auto"], ["a new block must last 10 s or more"]));
  const ws = workspace();
  expect(await ws.edit(() => ({ op: "new", frame_start: 1, frame_end: 5 }))).toBe("a new block must last 10 s or more");
  expect(ws.editor.edits).toEqual([]);
});

test("an edit refused earlier does not refuse a new one, an edit that changes nothing is refused", async () => {
  vi.mocked(client.previewEdits).mockImplementation(async () => preview(["auto", "auto", "auto"], ["old reason"]));
  const ws = workspace(preview(["auto", "auto", "auto"], ["old reason"]));
  expect(await ws.edit(() => ({ op: "accept" }))).toBe("That changes nothing.");
  expect(ws.editor.edits).toEqual([]);
});

test("a text from the action is given back without asking the server", async () => {
  const ws = workspace();
  expect(await ws.edit(() => "Select a block first.")).toBe("Select a block first.");
  expect(client.previewEdits).not.toHaveBeenCalled();
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

test("a session not open yet is loaded at the settings with its saved review's edits and the blocks the header gives", async () => {
  const saved = { edits: [{ op: "accept" }], notes: "shaky" } as never;
  const blocks = [block(1, "confirmed")];
  const header = { session_id: "S", n_frames: 6000, rate_hz: 60, review: saved, blocks, refusals: [], cuts: [], flagged_runs: [3] } as unknown as SessionHeader;
  vi.mocked(client.getSession).mockResolvedValue(header);
  vi.mocked(client.getSessionArrays).mockResolvedValue({ speed: new Float64Array([1]) } as SessionArrays);
  Workspace.current = null;
  const ws = await Workspace.open("S", SETTINGS);
  expect(client.getSession).toHaveBeenCalledWith("S", SETTINGS);
  expect([ws.settings, ws.saved, ws.editor.edits, ws.editor.dirty]).toEqual([SETTINGS, saved, [{ op: "accept" }], false]);
  expect(ws.preview).toEqual({ blocks, refusals: [], cuts: [], flagged_runs: [3] });
  expect(Workspace.current).toBe(ws);
  Workspace.current = null;
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

test("settings the server cannot preview at are not taken, and edits made after use them", async () => {
  vi.mocked(client.previewEdits).mockRejectedValueOnce(new Error("down")).mockImplementation(serverDropping());
  const ws = workspace();
  await expect(ws.useSettings(SHORTER)).rejects.toThrow("down");
  expect(ws.settings).toBe(SETTINGS);
  await ws.useSettings(SHORTER);
  await ws.edit(() => ({ op: "drop", frame: 1 }));
  expect(client.previewEdits).toHaveBeenLastCalledWith("S", { edits: [{ op: "drop", frame: 1 }], settings: SHORTER });
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
