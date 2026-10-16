import type { Edit, ReviewBlock, Run } from "../api/types";

export type Action = "accept-all" | "accept" | "reject" | "new-block" | "start-to-cursor" | "end-to-cursor" | "split" | "flag";

/** What an action reads of the screen: the cursor as a lab frame, the block it targets, the marked range and the run under the cursor. */
export interface Target {
  cursor: number;
  block: ReviewBlock | null;
  range: { frame_start: number; frame_end: number } | null;
  run: Run | null;
}

/** The edit an action makes of what is on screen, or the text saying what the action still needs. */
export function editFor(action: Action, target: Target): Edit | string {
  const { cursor, block, range, run } = target;
  if (action === "accept-all") return { op: "accept" };
  if (action === "new-block") return range ? { op: "new", ...range } : "Mark both ends of the range first.";
  if (action === "flag") return run ? { op: "flag", run: run.run } : "There is no run under the cursor.";
  if (!block) return "Select a block first.";
  const at = block.frame_start;
  if (action === "accept") return { op: "confirm", frame: at };
  if (action === "reject") return { op: "drop", frame: at };
  if (action === "start-to-cursor") return { op: "move", frame: cursor, edge: "start", at };
  if (action === "end-to-cursor") return { op: "move", frame: cursor, edge: "end", at };
  return cursor > at && cursor <= block.frame_end ? { op: "split", frame: cursor } : "Move the cursor inside the block, after its first frame, to split it there.";
}

/** An edit in words, for the toasts. */
export function label(edit: Edit): string {
  switch (edit.op) {
    case "accept": return "accept all";
    case "confirm": return `accept toggle at frame ${edit.frame}`;
    case "drop": return `remove toggle at frame ${edit.frame}`;
    case "move": return `move of the ${edit.edge} to frame ${edit.frame}`;
    case "split": return `split at frame ${edit.frame}`;
    case "new": return `new block over frames ${edit.frame_start} to ${edit.frame_end}`;
    case "cut": return `cut of frames ${edit.frame_start} to ${edit.frame_end}`;
    case "flag": return `flag toggle on run ${edit.run}`;
  }
}

/** The block that stands for the selected one after an edit: a new block is selected, otherwise the overlapping block with the edges nearest the old ones, so a removed block around the selected one does not take the selection. */
export function reselected(old: ReviewBlock | null, blocks: ReviewBlock[], edit: Edit): ReviewBlock | null {
  if (edit.op === "new") return blocks.find((b) => b.frame_start === edit.frame_start && b.frame_end === edit.frame_end) ?? null;
  if (!old) return null;
  const apart = (b: ReviewBlock) => Math.abs(b.frame_start - old.frame_start) + Math.abs(b.frame_end - old.frame_end);
  const overlapping = blocks.filter((b) => b.frame_start <= old.frame_end && b.frame_end >= old.frame_start);
  return overlapping.sort((a, b) => apart(a) - apart(b))[0] ?? null;
}

/** The edits made in a session, as the API expects them, with the marks and what was last saved. */
export class Editor {
  edits: Edit[];
  markIn: number | null = null;
  markOut: number | null = null;
  private saved: string;

  constructor(edits: Edit[] = []) {
    this.edits = edits;
    this.saved = JSON.stringify(edits);
  }

  /** Whether the edits differ from the ones last saved or loaded. */
  get dirty(): boolean {
    return JSON.stringify(this.edits) !== this.saved;
  }

  /** The marked range in lab frames whichever mark came first, none until both are set. */
  get range(): { frame_start: number; frame_end: number } | null {
    if (this.markIn === null || this.markOut === null) return null;
    return { frame_start: Math.min(this.markIn, this.markOut), frame_end: Math.max(this.markIn, this.markOut) };
  }

  push(edit: Edit): void {
    this.edits = [...this.edits, edit];
  }

  /** Take the last edit back and return it, none when there is nothing to undo. */
  undo(): Edit | undefined {
    const last = this.edits.at(-1);
    this.edits = this.edits.slice(0, -1);
    return last;
  }

  reset(): void {
    this.edits = [];
    this.clearMarks();
  }

  clearMarks(): void {
    this.markIn = this.markOut = null;
  }

  markSaved(): void {
    this.saved = JSON.stringify(this.edits);
  }
}
