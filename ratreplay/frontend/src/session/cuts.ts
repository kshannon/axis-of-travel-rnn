import type { CutPoint, SessionHeader, Span } from "../api/types";

export interface Cuts {
  pauses: number[];
  jumps: number[];
  gaps: Span[];
  margins: Span[];
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
