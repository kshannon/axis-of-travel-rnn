import { expect, test } from "vitest";
import type { MadeBlock, SessionHeader } from "../../src/api/types";
import { escapeClears, laneSelection, selectionText, toggled } from "../../src/pages/replay-selection";

const header = {
  rate_hz: 60,
  rules: { outbound_paths: [1, 2, 3, 4], return_paths: [9, 10] },
  epochs: [{ epoch: "track", environment: "triple_t", condition: "baseline", frame_start: 1, frame_end: 36_000, duration_s: 600 }],
  runs: [{ run: 12, path_id: 1, clean: true, frame_start: 6001, frame_end: 6186 }, { run: 13, path_id: 9, clean: false, frame_start: 7001, frame_end: 7060 }, { run: 14, path_id: 5, clean: true, frame_start: 8001, frame_end: 8060 }],
} as unknown as SessionHeader;
const block = { frame_start: 301, frame_end: 1500, status: "edited" } as MadeBlock;

test("a second click on the same epoch, run or frame lets go of it, a click on another thing picks that", () => {
  const run = { kind: "run", index: 0 } as const;
  expect(toggled(null, run)).toEqual(run);
  expect(toggled(run, run)).toBeNull();
  expect(toggled(run, { kind: "run", index: 1 })).toEqual({ kind: "run", index: 1 });
  expect(toggled(run, { kind: "epoch", index: 0 })).toEqual({ kind: "epoch", index: 0 });
  const frame = { kind: "frame", frame: 2341 } as const;
  expect(toggled(frame, { kind: "frame", frame: 2400 }, true)).toBeNull(); // the timeline says the click hit the frame selected
  expect(toggled(frame, { kind: "frame", frame: 2400 }, false)).toEqual({ kind: "frame", frame: 2400 });
});

test("escape lets go of the marks first and then of the selection", () => {
  expect(escapeClears(true, true)).toBe("marks");
  expect(escapeClears(true, false)).toBe("marks");
  expect(escapeClears(false, true)).toBe("selection");
  expect(escapeClears(false, false)).toBeNull();
});

test("what is selected is said in words and outlined in its own lane", () => {
  expect(selectionText(header, { kind: "run", index: 0 }, null, -1)).toBe("run 12, outbound path 1, 3.1 s, clean");
  expect(selectionText(header, { kind: "run", index: 1 }, null, -1)).toBe("run 13, return path 9, 1.0 s, not clean by the lab");
  expect(selectionText(header, { kind: "run", index: 2 }, null, -1)).toBe("run 14, path 5, 1.0 s, clean");
  expect(selectionText(header, { kind: "epoch", index: 0 }, null, -1)).toBe("epoch track, triple_t, baseline, 10.0 min");
  expect(selectionText(header, { kind: "frame", frame: 2341 }, null, -1)).toBe("frame 2341, at 0:39");
  expect(selectionText(header, null, block, 4)).toBe("block 5, edited, 20.0 s");
  expect(selectionText(header, null, null, -1)).toBe("nothing selected");
  expect(laneSelection(header, { kind: "run", index: 0 }, null)).toEqual({ lane: "runs", first: 6001, last: 6186 });
  expect(laneSelection(header, { kind: "epoch", index: 0 }, null)).toEqual({ lane: "session", first: 1, last: 36_000 });
  expect(laneSelection(header, { kind: "frame", frame: 2341 }, null)).toEqual({ lane: "frames", first: 2341, last: 2341 });
  expect(laneSelection(header, null, block)).toEqual({ lane: "blocks", first: 301, last: 1500 });
  expect(laneSelection(header, null, null)).toBeNull();
});
