import type { Edit, ReviewBlock, Run } from "../api/types";

export type Action = "accept-all" | "accept" | "reject" | "new-block" | "cut" | "start-to-cursor" | "end-to-cursor" | "split" | "flag";

const BURIED = "Every frame of this removed block lies under another block, so no edit can reach it.";
const MARK_FIRST = "Mark both ends of the range first.";
const ALREADY_ACCEPTED = "already accepted";
const RESTORE_FIRST = "restore the block first, Reject again";
export const NOTHING_CHANGED = "Nothing changed.";

/** What an action reads of the screen: the cursor as a lab frame, the block it targets among the blocks in time order, the marked range and the run under the cursor. */
export interface Target {
  cursor: number;
  block: ReviewBlock | null;
  blocks: ReviewBlock[];
  range: { frame_start: number; frame_end: number } | null;
  run: Run | null;
}

/** The frame that reaches a block. The server reaches a block that is not removed before a removed one, so a removed block is reached on its first frame that no block still standing holds, none when they cover it all. */
function anchorOf(block: ReviewBlock, blocks: ReviewBlock[]): number | null {
  let frame = block.frame_start;
  if (block.status === "dropped") {
    for (const other of blocks) {
      if (other.status !== "dropped" && other.frame_start <= frame && frame <= other.frame_end) frame = other.frame_end + 1;
    }
  }
  return frame <= block.frame_end ? frame : null;
}

/** The edit an action makes of what is on screen, or the text saying what the action still needs. */
export function editFor(action: Action, target: Target): Edit | string {
  const { cursor, block, blocks, range, run } = target;
  if (action === "accept-all") return { op: "accept" };
  if (action === "new-block") return range ? { op: "new", ...range } : MARK_FIRST;
  if (action === "cut") return range ? { op: "cut", ...range } : MARK_FIRST;
  if (action === "flag") return run ? { op: "flag", run: run.run } : "There is no run under the cursor.";
  if (!block) return "Select a block first.";
  const at = anchorOf(block, blocks);
  if (at === null) return BURIED;
  if (action === "accept") return { op: "confirm", frame: at };
  if (action === "reject") return { op: "drop", frame: at };
  if (action === "start-to-cursor") return { op: "move", frame: cursor, edge: "start", at };
  if (action === "end-to-cursor") return { op: "move", frame: cursor, edge: "end", at };
  return cursor > block.frame_start && cursor <= block.frame_end ? { op: "split", frame: cursor } : "Move the cursor inside the block, after its first frame, to split it there.";
}

/** Why a block with this status cannot be accepted, none when it can: an auto or an edited block is accepted, a confirmed one is already and a removed one comes back with Reject. */
export function acceptWhy(status: ReviewBlock["status"]): string {
  if (status === "confirmed") return ALREADY_ACCEPTED;
  return status === "dropped" ? RESTORE_FIRST : "";
}

/** What the toast says when an action changed nothing: the reason when the status of the block it acted on gives one, else the plain fact. */
export function unchangedText(action: Action, status: ReviewBlock["status"] | undefined): string {
  return (action === "accept" && status && acceptWhy(status)) || NOTHING_CHANGED;
}

/** An edit in words, for the toasts. */
export function label(edit: Edit): string {
  switch (edit.op) {
    case "accept": return "accept all";
    case "confirm": return `accept at frame ${edit.frame}`;
    case "drop": return `remove toggle at frame ${edit.frame}`;
    case "move": return `move of the ${edit.edge} to frame ${edit.frame}`;
    case "split": return `split at frame ${edit.frame}`;
    case "new": return `new block over frames ${edit.frame_start} to ${edit.frame_end}`;
    case "cut": return `cut of frames ${edit.frame_start} to ${edit.frame_end}`;
    case "flag": return `flag toggle on run ${edit.run}`;
  }
}

/** The block that stands for the selected one after an edit: a new block is selected, otherwise the overlapping block with the edges nearest the old ones, so a removed block around the selected one does not take the selection. */
export function reselected<B extends ReviewBlock>(old: B | null, blocks: B[], edit: Edit): B | null {
  if (edit.op === "new") return blocks.find((b) => b.frame_start === edit.frame_start && b.frame_end === edit.frame_end) ?? null;
  if (!old) return null;
  const apart = (b: B) => Math.abs(b.frame_start - old.frame_start) + Math.abs(b.frame_end - old.frame_end);
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
