import type { ReviewBlock, Review, ReviewPreview, SessionArrays, SessionHeader, WindowSettings } from "../api/types";
import { blockName } from "../draw/lanes";
import { runAt } from "../session/at";
import { windowCount } from "../session/windows";
import { CHIP_ACCENT, CHIP_MUTED, CHIP_OK, CHIP_WARN } from "../ui/style";
import { counted } from "../ui/text";
import { stampWithSince } from "../ui/time";

const SECONDS_PER_MINUTE = 60;
const PERCENT = 100;
const STATUS_GLYPHS: Record<ReviewBlock["status"], string> = { auto: "☐", confirmed: "☑", edited: "✎", dropped: "✕" };
const STATUS_CHIPS: Record<ReviewBlock["status"], string> = { auto: CHIP_ACCENT, confirmed: CHIP_OK, edited: CHIP_WARN, dropped: CHIP_MUTED };

export interface Tile {
  label: string;
  value: string;
  note: string;
  /** What the tile hovers as, when its note is cut short. */
  title: string;
  /** Twice the width, for a tile with three numbers. */
  wide?: boolean;
}

export interface BlockCard {
  first: number;
  name: string;
  epoch: string;
  minutes: string;
  runs: number;
  status: ReviewBlock["status"];
  glyph: string;
  chip: string;
  selected: boolean;
  accepted: boolean;
  removed: boolean;
  acceptable: boolean;
}

const framesOf = (block: Pick<ReviewBlock, "frame_start" | "frame_end">) => block.frame_end - block.frame_start + 1;
const minutes = (seconds: number) => (seconds / SECONDS_PER_MINUTE).toFixed(1);

/** One card per block in time order. Accepting needs an auto or accepted block, an edited block is kept already and a removed one is restored first. */
export function blockCards(blocks: ReviewBlock[], header: SessionHeader, selected: ReviewBlock | null): BlockCard[] {
  return blocks.map((block, position) => ({
    first: block.frame_start, name: blockName(position), epoch: block.epoch,
    minutes: (framesOf(block) / header.rate_hz / SECONDS_PER_MINUTE).toFixed(2),
    runs: header.runs.filter((r) => block.frame_start <= r.frame_start && r.frame_start <= block.frame_end).length,
    status: block.status, glyph: STATUS_GLYPHS[block.status], chip: STATUS_CHIPS[block.status],
    selected: block.frame_start === selected?.frame_start,
    accepted: block.status === "confirmed" || block.status === "edited", removed: block.status === "dropped",
    acceptable: block.status === "auto" || block.status === "confirmed",
  }));
}

/** The stat tiles of the Summary card: the blocks by status, the time kept, the windows at the settings, the cuts and the flagged runs. */
export function summaryTiles(preview: ReviewPreview, header: SessionHeader, settings: WindowSettings): Tile[] {
  const { blocks } = preview;
  const count = (status: ReviewBlock["status"]) => String(blocks.filter((b) => b.status === status).length);
  const kept = blocks.filter((b) => b.status !== "dropped");
  const keptS = kept.reduce((total, b) => total + framesOf(b), 0) / header.rate_hz;
  const epochS = header.epochs.filter((e) => header.block_epochs.includes(e.epoch)).reduce((total, e) => total + e.duration_s, 0);
  const windows = kept.reduce((total, b) => total + windowCount(framesOf(b), header.rate_hz, settings), 0);
  const { pauses, jumps, gaps } = header.cuts;
  const byStatus = (label: string, key: ReviewBlock["status"]): Tile => ({ label, value: count(key), note: "", title: "" });
  const keptNote = epochS ? `${Math.round((PERCENT * keptS) / epochS)}%` : "0%";
  return [
    byStatus("automatic", "auto"), byStatus("confirmed", "confirmed"), byStatus("edited", "edited"), byStatus("removed", "dropped"),
    { label: "kept", value: `${minutes(keptS)} min`, note: keptNote, title: `${keptNote} of the ${minutes(epochS)} min of ${header.block_epochs.join(" and ")}` },
    { label: "windows", value: String(windows), note: `${settings.window_s} s each`, title: `${settings.window_s} s windows every ${settings.stride_s} s` },
    { label: "flagged", value: String(preview.flagged_runs.length), note: `of ${header.runs.length} runs`, title: "runs flagged as mislabelled" },
    { label: "pauses, jumps, gaps", value: [pauses, jumps, gaps].map((cuts) => cuts.length).join(", "), note: "", title: "what the processor cuts at", wide: true },
  ];
}

export function factsLine(header: SessionHeader): string {
  return `rat ${header.subject_id}, ${header.date}, ${header.protocol}, ${header.rate_hz} Hz, ${header.n_frames} frames`;
}

/** Which state is on screen: the automatic blocks, or the saved review with its edit count, then what changed since. */
export function stateLine(saved: Review | null, edits: number, dirty: boolean, skipped: number): string {
  const base = saved ? `saved ${stampWithSince(saved.reviewed_at)} by ${saved.reviewed_by}, ${counted(saved.edits.length, "edit")}` : "automatic";
  const skips = skipped ? `, ${skipped} skipped under the current rules` : "";
  if (!dirty) return base + skips;
  if (!edits && saved) return "automatic, the saved review on disk is not loaded";
  return `${base}${skips}, now ${counted(edits, "edit")} not saved yet`;
}

export function marksLine(markIn: number | null, markOut: number | null, rateHz: number): string {
  if (markIn === null && markOut === null) return "No range marked.";
  if (markIn === null || markOut === null) return `Marked frame ${markIn ?? markOut}, mark the other end of the range.`;
  const [first, last] = [markIn, markOut].sort((a, b) => a - b);
  return `Marked frames ${first} to ${last}, ${((last - first + 1) / rateHz).toFixed(1)} s.`;
}

export interface Live {
  time: string;
  frame: string;
  speed: string;
  lights: string;
  run: string;
}

/** What the live tiles show at a frame index: the time in the session, the lab frame, the speed, the lights tracked and the run under the cursor. */
export function liveTiles(header: SessionHeader, arrays: SessionArrays, index: number): Live {
  const run = runAt(header.runs, index + 1);
  const speed = arrays.speed[index];
  return {
    time: `${arrays.t[index].toFixed(2)} s`, frame: String(index + 1), speed: Number.isNaN(speed) ? "n/a" : `${Math.round(speed)} px/s`,
    lights: String(arrays.n_lights[index]), run: run ? `${run.run}, path ${run.path_id} ${run.clean ? "clean" : "dirty"}` : "none",
  };
}
