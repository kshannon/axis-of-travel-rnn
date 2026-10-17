import type { ReviewBlock, SessionHeader, Span } from "../api/types";
import { colourOf } from "./layers";
import type { LayerKey, Layers } from "./layers";
import { FRAMES_LANE, runFill, runKind } from "./lanes";
import type { Bar, FrameLayer, LaneSpec, Scene } from "./lanes";

export const SESSION_LANES: readonly LaneSpec[] = [
  { name: "session", weight: 1 }, { name: "runs", weight: 2 }, { name: FRAMES_LANE, weight: 3 }, { name: "blocks", weight: 2 },
];

const EPOCH_COLOURS: Record<string, string> = { arena: "#38bdf8", track: "#4ade80" };
const OTHER_EPOCH_COLOUR = "#a1a1aa";
const BLOCK_FILLS: Record<ReviewBlock["status"], string> = { auto: "accent", confirmed: "ok", edited: "warn", dropped: "muted" };

// How strong the bars are drawn, and in the frames lane the band of the heading layers at the bottom (a fraction of the
// lane) and the length of a pause tick from the top. A margin is a dark band over the cut it trims.
const BAR_ALPHA = 0.8;
const GAP_ALPHA = 0.35;
const MARGIN_ALPHA = 0.85;
const HEADING_BAND = 0.14;
const PAUSE_TICK = 0.3;
const SECONDS_PER_MINUTE = 60;

export const blockName = (position: number): string => `block ${position + 1}`;

const framesOf = (first: number, last: number) => last - first + 1;

function epochBars(header: SessionHeader): Bar[] {
  return header.epochs.map((e) => ({
    lane: "session", first: e.frame_start, last: e.frame_end, fill: EPOCH_COLOURS[e.epoch] ?? OTHER_EPOCH_COLOUR, alpha: BAR_ALPHA, text: e.epoch,
    tip: `${e.epoch}, ${e.environment}, ${e.condition}, frames ${e.frame_start} to ${e.frame_end}, ${(framesOf(e.frame_start, e.frame_end) / header.rate_hz / SECONDS_PER_MINUTE).toFixed(1)} min`,
  }));
}

/** A run is hatched when dirty and outlined when flagged. */
function runBars(header: SessionHeader, flagged: Set<number>): Bar[] {
  return header.runs.map((r) => ({
    lane: "runs", first: r.frame_start, last: r.frame_end, fill: runFill(r.path_id), hatched: !r.clean, outline: flagged.has(r.run) ? "bad" : undefined,
    tip: `run ${r.run}, path ${r.path_id} ${runKind(r.path_id)}, ${r.clean ? "clean" : "dirty"}${flagged.has(r.run) ? ", flagged" : ""}, ${framesOf(r.frame_start, r.frame_end)} frames (${r.frame_start} to ${r.frame_end})`,
  }));
}

function blockBars(blocks: ReviewBlock[], rateHz: number): Bar[] {
  return blocks.map((b, position) => ({
    lane: "blocks", first: b.frame_start, last: b.frame_end, fill: BLOCK_FILLS[b.status], alpha: b.status === "dropped" ? GAP_ALPHA : BAR_ALPHA,
    text: blockName(position), pick: b.frame_start,
    tip: `${blockName(position)}, ${b.status}, frames ${b.frame_start} to ${b.frame_end}, ${(framesOf(b.frame_start, b.frame_end) / rateHz).toFixed(1)} s`,
  }));
}

/** The frames lane: the gaps and margins behind, the heading bands, the speed trace, then the jumps and pauses in front, each for the layers that are on. */
function frameLayers(header: SessionHeader, layers: Layers, speed: Float64Array, speedTop: number): FrameLayer[] {
  const span = (spans: Span[], key: LayerKey, from: number, alpha = 1): FrameLayer[] =>
    layers[key] ? [{ kind: "span", spans, colour: colourOf(key), alpha, from, to: 1 }] : [];
  const tick = (frames: number[], key: LayerKey, to: number): FrameLayer[] => (layers[key] ? [{ kind: "tick", frames, colour: colourOf(key), to }] : []);
  const { gaps, margins, jumps, pauses } = header.cuts;
  return [
    ...span(gaps, "gaps", 0, GAP_ALPHA), ...span(margins, "margins", 0, MARGIN_ALPHA),
    ...span(header.heading_filled, "filled", 1 - HEADING_BAND), ...span(header.heading_held, "held", 1 - HEADING_BAND),
    ...span(header.heading_lost, "lost", 1 - HEADING_BAND),
    ...(layers.speed ? [{ kind: "trace" as const, values: speed, top: speedTop }] : []),
    ...tick(jumps, "jumps", 1), ...tick(pauses, "pauses", PAUSE_TICK),
  ];
}

/** The session's timeline: its epochs, runs and the blocks as they stand after the edits, and the frames lane with the layers that are on. */
export function sessionScene(
  header: SessionHeader, blocks: ReviewBlock[], flaggedRuns: number[], layers: Layers, speed: Float64Array, speedTop: number,
): Scene {
  return {
    lanes: SESSION_LANES, rateHz: header.rate_hz, nFrames: header.n_frames,
    bars: [...epochBars(header), ...runBars(header, new Set(flaggedRuns)), ...blockBars(blocks, header.rate_hz)],
    frames: frameLayers(header, layers, speed, speedTop),
  };
}
