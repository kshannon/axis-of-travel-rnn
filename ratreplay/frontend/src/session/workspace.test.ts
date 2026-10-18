import { beforeEach, expect, test, vi } from "vitest";
import * as client from "../api/client";
import type { Edit, MadeBlock, Preview, ReviewBlock, SessionArrays, SessionHeader } from "../api/types";
import { Workspace } from "./workspace";

vi.mock("../api/client");

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
  return new Workspace({ header, arrays, settings: {} as never, saved: null, preview: first });
}

beforeEach(() => vi.resetAllMocks());

test("an edit the server applies joins the list and the blocks are the server's answer", async () => {
  vi.mocked(client.previewEdits).mockImplementation(serverDropping());
  const ws = workspace();
  const drop: Edit = { op: "drop", frame: 1 };
  expect(await ws.edit(() => drop)).toBe(drop);
  expect(ws.editor.edits).toEqual([drop]);
  expect(ws.preview.blocks.map((b) => b.status)).toEqual(["dropped", "auto", "auto"]);
  expect(client.previewEdits).toHaveBeenCalledWith("S", { edits: [drop], settings: {} });
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

test("a save marks the edits as saved and keeps the review the server wrote", async () => {
  const review = { edits: [{ op: "accept" }], reviewed_by: "kyle" } as never;
  vi.mocked(client.saveBlocks).mockResolvedValue({ review, replaced: false, built: 1, failed: [], build_error: null });
  const ws = workspace();
  ws.editor.push({ op: "accept" });
  expect(ws.editor.dirty).toBe(true);
  await ws.save("a note");
  expect(client.saveBlocks).toHaveBeenCalledWith("S", { edits: [{ op: "accept" }], notes: "a note", settings: {} });
  expect([ws.editor.dirty, ws.saved]).toEqual([false, review]);
});

test("opening the session already open keeps its edits and reads the window settings again", async () => {
  vi.mocked(client.getFormat).mockResolvedValue({ settings: { window_s: 5 } } as never);
  const ws = workspace();
  Workspace.current = ws;
  ws.editor.push({ op: "accept" });
  expect(await Workspace.open("S")).toBe(ws);
  expect([ws.settings.window_s, ws.editor.edits.length]).toEqual([5, 1]);
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
