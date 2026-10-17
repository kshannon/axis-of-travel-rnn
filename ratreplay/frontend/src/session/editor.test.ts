import { expect, test } from "vitest";
import type { Edit, ReviewBlock, Run } from "../api/types";
import { Editor, editFor, label, reselected } from "./editor";
import type { Target } from "./editor";

function block(frame_start: number, frame_end: number, status: ReviewBlock["status"] = "auto"): ReviewBlock {
  return { block_id: "S_arena_01", epoch: "arena", environment: "open_arena", frame_start, frame_end, status, note: "" };
}

const RUN: Run = { run: 3, epoch: "track", path_id: 2, clean: true, frame_start: 100, frame_end: 200 };
const NOTHING: Target = { cursor: 150, block: null, blocks: [], range: null, run: null };

test("the edit list grows with each edit and undo takes the last one back", () => {
  const editor = new Editor();
  editor.push({ op: "accept" });
  editor.push({ op: "drop", frame: 5 });
  expect(editor.edits).toEqual([{ op: "accept" }, { op: "drop", frame: 5 }]);
  expect(editor.undo()).toEqual({ op: "drop", frame: 5 });
  expect(editor.edits).toEqual([{ op: "accept" }]);
  editor.undo();
  expect(editor.undo()).toBeUndefined();
  expect(editor.edits).toEqual([]);
});

test("the edits are dirty only while they differ from what was saved", () => {
  const editor = new Editor([{ op: "accept" }]);
  expect(editor.dirty).toBe(false);
  editor.push({ op: "flag", run: 1 });
  expect(editor.dirty).toBe(true);
  editor.undo();
  expect(editor.dirty).toBe(false);
  editor.reset();
  expect(editor.dirty).toBe(true);
  editor.markSaved();
  expect(editor.dirty).toBe(false);
});

test("a range needs both marks and takes them in either order", () => {
  const editor = new Editor();
  editor.markOut = 900;
  expect(editor.range).toBeNull();
  editor.markIn = 1200;
  expect(editor.range).toEqual({ frame_start: 900, frame_end: 1200 });
  editor.clearMarks();
  expect(editor.range).toBeNull();
});

test("a new block from marks needs the range, else the action says so", () => {
  const range = { frame_start: 900, frame_end: 1200 };
  expect(editFor("new-block", { ...NOTHING, range })).toEqual({ op: "new", ...range });
  expect(editFor("new-block", NOTHING)).toMatch(/Mark both ends/);
});

test("block actions need a selected block and use the cursor as the lab frame", () => {
  const target = { ...NOTHING, block: block(301, 1500), cursor: 800 };
  expect(editFor("accept", target)).toEqual({ op: "confirm", frame: 301 });
  expect(editFor("reject", target)).toEqual({ op: "drop", frame: 301 });
  expect(editFor("start-to-cursor", target)).toEqual({ op: "move", frame: 800, edge: "start", at: 301 });
  expect(editFor("end-to-cursor", target)).toEqual({ op: "move", frame: 800, edge: "end", at: 301 });
  expect(editFor("split", target)).toEqual({ op: "split", frame: 800 });
  for (const action of ["accept", "reject", "start-to-cursor", "end-to-cursor", "split"] as const) {
    expect(editFor(action, NOTHING)).toBe("Select a block first.");
  }
});

test("a removed block is reached on a frame no kept block holds, since the server reaches the kept blocks first", () => {
  const removed = block(301, 1500, "dropped");
  const made = block(301, 1299, "edited");
  expect(editFor("reject", { ...NOTHING, block: made, blocks: [removed, made] })).toEqual({ op: "drop", frame: 301 });
  expect(editFor("reject", { ...NOTHING, block: removed, blocks: [removed, made] })).toEqual({ op: "drop", frame: 1300 });
  expect(editFor("reject", { ...NOTHING, block: removed, blocks: [removed, block(301, 1500, "edited")] })).toMatch(/no edit can reach/);
});

test("a split needs the cursor inside the block after its first frame", () => {
  const selected = block(301, 1500);
  expect(editFor("split", { ...NOTHING, block: selected, cursor: 301 })).toMatch(/inside the block/);
  expect(editFor("split", { ...NOTHING, block: selected, cursor: 1501 })).toMatch(/inside the block/);
  expect(editFor("split", { ...NOTHING, block: selected, cursor: 1500 })).toEqual({ op: "split", frame: 1500 });
});

test("accept all and flag need no block, flag needs a run under the cursor", () => {
  expect(editFor("accept-all", NOTHING)).toEqual({ op: "accept" });
  expect(editFor("flag", { ...NOTHING, run: RUN })).toEqual({ op: "flag", run: 3 });
  expect(editFor("flag", NOTHING)).toMatch(/no run/);
});

test("every edit has words for the toasts", () => {
  const edits: Edit[] = [{ op: "accept" }, { op: "confirm", frame: 1 }, { op: "drop", frame: 2 }, { op: "split", frame: 3 },
    { op: "move", frame: 4, edge: "end", at: 1 }, { op: "new", frame_start: 5, frame_end: 6 }, { op: "cut", frame_start: 7, frame_end: 8 }, { op: "flag", run: 9 }];
  expect(edits.map(label).every((text) => text.length > 0)).toBe(true);
  expect(label(edits[4])).toBe("move of the end to frame 4");
});

test("the selection follows the block it overlaps after an edit, a new block is selected", () => {
  const before = block(301, 1500);
  const split = [block(301, 799), block(800, 1500)];
  expect(reselected(before, split, { op: "split", frame: 800 })).toBe(split[1]);
  expect(reselected(before, [block(400, 1500)], { op: "move", frame: 400, edge: "start", at: 301 })?.frame_start).toBe(400);
  expect(reselected(before, [block(2000, 2500)], { op: "accept" })).toBeNull();
  expect(reselected(null, split, { op: "accept" })).toBeNull();
  const made = block(400, 700, "edited");
  expect(reselected(before, [block(301, 1500, "dropped"), made], { op: "new", frame_start: 400, frame_end: 700 })).toBe(made);
});

test("a removed block around the selected one does not take the selection, and no blocks left means none selected", () => {
  const made = block(399, 1299, "edited");
  const moved = block(449, 1299, "edited");
  expect(reselected(made, [block(301, 1500, "dropped"), moved], { op: "move", frame: 449, edge: "start", at: 399 })).toBe(moved);
  expect(reselected(made, [], { op: "accept" })).toBeNull();
});
