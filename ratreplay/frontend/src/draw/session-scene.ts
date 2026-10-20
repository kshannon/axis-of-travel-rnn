import type { HeadingSpan, MadeBlock, ReviewBlock, SessionHeader, Span } from "../api/types";
import { cutsOf, splitAtPauses } from "../session/cuts";
import { counted } from "../ui/text";
import { colourOf, HEAD_DIR } from "./layers";
import type { LayerKey, Layers } from "./layers";
import { FRAMES_LANE } from "./lanes";
import type { Bar, FrameLayer, LaneSpec, Scene } from "./lanes";
import { pathsOf, runFill, runText } from "./runs";

/** The lanes of the session timeline. The runs lane is as tall as the blocks lane, a run bar carries its path number, its hatching and its outline. */
export const SESSION_LANES: readonly LaneSpec[] = [
  { name: "session", weight: 1 }, { name: "runs", weight: 2 }, { name: FRAMES_LANE, weight: 3 }, { name: "blocks", weight: 2 },
];

// Palette colours. A block the person has not judged yet is the accent faint, a confirmed one the same blue strong.
const EPOCH_COLOURS: Record<string, string> = { arena: "arena", track: "track" };
const OTHER_EPOCH_COLOUR = "neutral";
const BLOCK_FILLS: Record<ReviewBlock["status"], string> = { auto: "accent", confirmed: "ok", edited: "warn", dropped: "muted" };

// How strong the bars are drawn, and in the frames lane the band of the heading layers at the bottom (a fraction of the
// lane). A margin is a grey band over the cut it trims, fainter than the bars so the cut shows through. The lost tracking
// is a striped bar, its fill under the stripes this faint.
const BAR_ALPHA = 0.8;
const AUTO_ALPHA = 0.45;
const DROPPED_ALPHA = 0.35;
const GAP_ALPHA = 0.3;
const MARGIN_ALPHA = 0.45;
const HEADING_BAND = 0.14;
const SECONDS_PER_MINUTE = 60;
const TIP_DECIMALS = 1;

export const blockName = (position: number): string => `block ${position + 1}`;
/** The number alone, what a block bar writes when its name does not fit. */
const blockNumber = (position: number): string => String(position + 1);

const BLOCK_ALPHAS: Record<ReviewBlock["status"], number> = { auto: AUTO_ALPHA, confirmed: BAR_ALPHA, edited: BAR_ALPHA, dropped: DROPPED_ALPHA };

const framesOf = (first: number, last: number) => last - first + 1;

function epochBars(header: SessionHeader): Bar[] {
  return header.epochs.map((e, pick) => ({
    lane: "session", first: e.frame_start, last: e.frame_end, fill: EPOCH_COLOURS[e.epoch] ?? OTHER_EPOCH_COLOUR, alpha: BAR_ALPHA, text: e.epoch, pick,
    tip: `${e.epoch}, ${e.environment}, ${e.condition}, frames ${e.frame_start} to ${e.frame_end}, ${(framesOf(e.frame_start, e.frame_end) / header.rate_hz / SECONDS_PER_MINUTE).toFixed(1)} min`,
  }));
}

/** A run is coloured by its path, which it writes inside when it fits, hatched when the lab did not call it clean and outlined in the warning colour when flagged. */
function runBars(header: SessionHeader, flagged: Set<number>): Bar[] {
  const paths = pathsOf(header);
  return header.runs.map((r, pick) => ({
    lane: "runs", first: r.frame_start, last: r.frame_end, fill: runFill(r.path_id, paths), text: String(r.path_id), hatched: !r.clean, outline: flagged.has(r.run) ? "warn" : undefined, pick,
    tip: `${runText(r, paths, flagged.has(r.run))}, ${framesOf(r.frame_start, r.frame_end)} frames (${r.frame_start} to ${r.frame_end})`,
  }));
}

/** What a block yields at the settings, as the manager counted it: its windows and its verdict, or that it is removed. */
export function yieldOf(block: MadeBlock): string {
  if (!block.windows) return "removed";
  const { count, verdict } = block.windows;
  return `${counted(count, "window")}, ${verdict.ok ? "ok" : verdict.reasons.join(", ")}`;
}

function blockBars(blocks: MadeBlock[], rateHz: number): Bar[] {
  return blocks.map((b, position) => ({
    lane: "blocks", first: b.frame_start, last: b.frame_end, fill: BLOCK_FILLS[b.status], alpha: BLOCK_ALPHAS[b.status],
    text: blockName(position), short: blockNumber(position), pick: position,
    tip: `${blockName(position)}, ${b.status}, frames ${b.frame_start} to ${b.frame_end}, ${(framesOf(b.frame_start, b.frame_end) / rateHz).toFixed(1)} s, ${yieldOf(b)}`,
  }));
}

/**
 * The hover of the heading spans: each is a bar nobody sees, over the heading band of the frames lane (its last row, as tall as the band),
 * saying its length, the layer's words and the reason the engine gave, so the client words no rule. It is cut at the pauses as the drawn
 * span is, each piece saying the whole span's tip. A layer that is off has no bar.
 */
function headingBars(header: SessionHeader, layers: Layers): Bar[] {
  const { pauses } = cutsOf(header);
  const rows = 1 / HEADING_BAND;
  return (["filled", "held", "lost"] as const).flatMap((key) =>
    !layers[key] ? [] : header.heading_spans[key].flatMap(({ first, last, seconds, reason }) =>
      splitAtPauses([[first, last]], pauses).map(([from, to]): Bar => ({
        lane: FRAMES_LANE, first: from, last: to, fill: colourOf(key), alpha: 0, rows, row: rows - 1,
        tip: `${seconds.toFixed(TIP_DECIMALS)} s ${HEAD_DIR[key]}, ${reason}`,
      }))));
}

/**
 * The frames lane: the lost tracking and margins behind, the heading bands, the speed trace, then the jumps in front, each for the
 * layers that are on. A span is in frames and a pause is between two frames, so every span is cut at the pauses before it is drawn.
 */
function frameLayers(header: SessionHeader, layers: Layers, speed: Float64Array, speedTop: number): FrameLayer[] {
  const { gaps, margins, jumps, pauses } = cutsOf(header);
  const span = (spans: Span[], key: LayerKey, from: number, alpha = 1, hatched = false): FrameLayer[] =>
    layers[key] ? [{ kind: "span", spans: splitAtPauses(spans, pauses), colour: colourOf(key), alpha, from, to: 1, hatched }] : [];
  const tick = (frames: number[], key: LayerKey, to: number): FrameLayer[] => (layers[key] ? [{ kind: "tick", frames, colour: colourOf(key), to }] : []);
  const { lost, filled, held } = header.heading_spans;
  const pairs = (found: HeadingSpan[]): Span[] => found.map(({ first, last }) => [first, last]);
  return [
    ...span(gaps, "gaps", 0, GAP_ALPHA, true), ...span(margins, "margins", 0, MARGIN_ALPHA),
    ...span(pairs(filled), "filled", 1 - HEADING_BAND), ...span(pairs(held), "held", 1 - HEADING_BAND), ...span(pairs(lost), "lost", 1 - HEADING_BAND),
    ...(layers.speed ? [{ kind: "trace" as const, values: speed, top: speedTop, colour: colourOf("speed") }] : []),
    ...tick(jumps, "jumps", 1),
  ];
}

/** The session's timeline: its epochs, runs and the blocks as they stand after the edits, and the frames lane with the layers that are on. */
export function sessionScene(
  header: SessionHeader, blocks: MadeBlock[], flaggedRuns: number[], layers: Layers, speed: Float64Array, speedTop: number,
): Scene {
  return {
    lanes: SESSION_LANES, rateHz: header.rate_hz, nFrames: header.n_frames,
    bars: [...epochBars(header), ...runBars(header, new Set(flaggedRuns)), ...blockBars(blocks, header.rate_hz), ...headingBars(header, layers)],
    frames: frameLayers(header, layers, speed, speedTop), breaks: [...cutsOf(header).pauses].sort((a, b) => a - b),
  };
}
