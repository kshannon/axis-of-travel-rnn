import type { CutPoint, SessionHeader, Span } from "../api/types";

export interface Cuts {
  pauses: number[];
  jumps: number[];
  gaps: Span[];
  margins: Span[];
}

/**
 * The spans cut where a pause falls inside them, so no span of frames runs across one. A pause is the time between two frames and
 * `pauses` gives the first frame after each, so a span that holds the frame before a pause and the frame after it becomes two.
 */
export function splitAtPauses(spans: Span[], pauses: readonly number[]): Span[] {
  const sorted = [...pauses].sort((a, b) => a - b);
  return spans.flatMap(([first, last]) => {
    const starts = [first, ...sorted.filter((pause) => pause > first && pause <= last)];
    return starts.map((start, i): Span => [start, i + 1 < starts.length ? starts[i + 1] - 1 : last]);
  });
}

/** The session's cut points as the lanes and tiles read them: the frames of the pauses and jumps, the first and last frame of the gaps and margins. */
export function cutsOf(header: Pick<SessionHeader, "cut_points" | "margins">): Cuts {
  const of = (reason: CutPoint["reason"]) => header.cut_points.filter((cut) => cut.reason === reason);
  return {
    pauses: of("pause").map((cut) => cut.frame),
    jumps: of("jump").map((cut) => cut.frame),
    gaps: of("gap").map((cut): Span => [cut.frame, cut.frame_end!]),
    margins: header.margins,
  };
}
