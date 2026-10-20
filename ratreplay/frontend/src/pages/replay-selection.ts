import type { MadeBlock, Run, SessionHeader } from "../api/types";
import { timeLabel } from "../draw/lanes";
import { cleanText, pathsOf, pathText } from "../draw/runs";
import { blockName } from "../draw/session-scene";
import type { LaneSelection } from "../draw/timeline";

/** What a click on a lane other than the blocks lane picks: an epoch or a run by its place in the header, or a frame of the frames lane. */
export type Picked = { kind: "epoch" | "run"; index: number } | { kind: "frame"; frame: number };

type Drawn = Pick<SessionHeader, "epochs" | "runs" | "rate_hz" | "rules">;

const MINUTE_S = 60;

/** The pick after a click: the thing clicked, or nothing when it is the one already picked. A frame counts as the same when the timeline says the click hit it. */
export function toggled(current: Picked | null, clicked: Picked, sameFrame = false): Picked | null {
  if (!current || current.kind !== clicked.kind) return clicked;
  const same = "index" in current && "index" in clicked ? current.index === clicked.index : sameFrame;
  return same ? null : clicked;
}

/** What escape lets go of next: the marks first, then the selection, none when there is neither. */
export function escapeClears(hasMarks: boolean, hasSelection: boolean): "marks" | "selection" | null {
  if (hasMarks) return "marks";
  return hasSelection ? "selection" : null;
}

/** The run that is picked, none when something else is. */
export const pickedRun = (header: Pick<SessionHeader, "runs">, picked: Picked | null): Run | null => (picked?.kind === "run" ? header.runs[picked.index] : null);

/** The stretch of a lane the timeline outlines for what is selected, a selected block taking the place of a pick. */
export function laneSelection(header: Pick<SessionHeader, "epochs" | "runs">, picked: Picked | null, block: MadeBlock | null): LaneSelection | null {
  if (block) return { lane: "blocks", first: block.frame_start, last: block.frame_end };
  if (!picked) return null;
  if (picked.kind === "frame") return { lane: "frames", first: picked.frame, last: picked.frame };
  const { frame_start: first, frame_end: last } = picked.kind === "epoch" ? header.epochs[picked.index] : header.runs[picked.index];
  return { lane: picked.kind === "epoch" ? "session" : "runs", first, last };
}

const seconds = (header: Drawn, first: number, last: number) => ((last - first + 1) / header.rate_hz).toFixed(1);

/** What is selected in words, such as "run 12, outbound path 1, 3.1 s, clean", "block 5, edited, 20.0 s" or "frame 2341, at 0:39". */
export function selectionText(header: Drawn, picked: Picked | null, block: MadeBlock | null, position: number): string {
  if (block) return `${blockName(position)}, ${block.status}, ${seconds(header, block.frame_start, block.frame_end)} s`;
  if (!picked) return "nothing selected";
  if (picked.kind === "frame") return `frame ${picked.frame}, at ${timeLabel((picked.frame - 1) / header.rate_hz)}`;
  if (picked.kind === "epoch") {
    const e = header.epochs[picked.index];
    return `epoch ${e.epoch}, ${e.environment}, ${e.condition}, ${(e.duration_s / MINUTE_S).toFixed(1)} min`;
  }
  const r = header.runs[picked.index];
  return `run ${r.run}, ${pathText(r.path_id, pathsOf(header))}, ${seconds(header, r.frame_start, r.frame_end)} s, ${cleanText(r)}`;
}
