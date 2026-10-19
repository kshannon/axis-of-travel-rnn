import type { Edit, HeadingSpan, MadeBlock, Preview, Refusal, Review, ReviewBlock, SavedBlocks, SessionArrays, SessionHeader, WindowSettings } from "../api/types";
import { HEAD_DIR } from "../draw/layers";
import { ALL_EPOCHS, FOLLOW_CURSOR } from "../draw/occupancy";
import { blockName } from "../draw/session-scene";
import { runAt } from "../session/at";
import { cutsOf } from "../session/cuts";
import { acceptWhy, label as editLabel } from "../session/editor";
import { percent } from "../ui/format";
import { CHIP_ACCENT, CHIP_MUTED, CHIP_OK, CHIP_WARN } from "../ui/style";
import { counted } from "../ui/text";
import { formatStamp, stampWithSince } from "../ui/time";
import { ANNOTATED_NOTE } from "./exclusion-view";

const SECONDS_PER_MINUTE = 60;
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
  /** The place of the block in the preview's time order, which tells two blocks apart that start on the same frame. */
  position: number;
  name: string;
  epoch: string;
  minutes: string;
  runs: number;
  /** The windows the manager counted at the settings, none for a removed block. */
  windows: number | null;
  windowsText: string;
  /** The manager's verdict on the block: ok, or every rule it breaks. Empty for a removed block. */
  verdict: string;
  ok: boolean;
  /** What is wrong with the block's frames, as the build found it. */
  problems: string[];
  /** The seconds of the block whose head direction RatReplay filled or that has none, empty when all of it was measured. */
  heading: string;
  status: ReviewBlock["status"];
  glyph: string;
  chip: string;
  selected: boolean;
  accepted: boolean;
  removed: boolean;
  acceptable: boolean;
  /** The words that stand in place of the Accept chip when the block cannot be accepted, with their hover. Empty when it can. */
  keptText: string;
  keptTitle: string;
}

const framesOf = (block: Pick<ReviewBlock, "frame_start" | "frame_end">) => block.frame_end - block.frame_start + 1;
const minutes = (seconds: number) => (seconds / SECONDS_PER_MINUTE).toFixed(1);

/** What the manager says a block yields: its windows and its verdict, nothing for a removed block. */
function yieldOf(block: MadeBlock) {
  if (!block.windows) return { windows: null, windowsText: "removed, yields nothing", verdict: "", ok: true };
  const { count, verdict } = block.windows;
  return { windows: count, windowsText: counted(count, "training window"), verdict: verdict.ok ? "ok" : verdict.reasons.join(", "), ok: verdict.ok };
}

const DECIMALS = 1;

/** The frames of a block that lie in the spans, both ends included. */
const framesIn = (spans: HeadingSpan[], block: Pick<ReviewBlock, "frame_start" | "frame_end">) =>
  spans.reduce((total, { first, last }) => total + Math.max(0, Math.min(last, block.frame_end) - Math.max(first, block.frame_start) + 1), 0);

/** What happened to the head direction inside a block, in seconds and in the words of the timeline's layers, nothing when all of it was measured. */
export function headingText(block: Pick<ReviewBlock, "frame_start" | "frame_end">, header: Pick<SessionHeader, "heading_spans" | "rate_hz">): string {
  const { heading_spans: spans } = header;
  const parts = (["filled", "held", "lost"] as const)
    .map((kind) => [framesIn(spans[kind], block), HEAD_DIR[kind]] as const)
    .filter(([frames]) => frames > 0)
    .map(([frames, words]) => `${(frames / header.rate_hz).toFixed(DECIMALS)} s ${words}`);
  return parts.length ? `head dir: ${parts.join(", ")}` : "";
}

const KEPT_WORDS: Partial<Record<ReviewBlock["status"], string>> = { edited: "kept as edited", dropped: "removed" };

/** The hover of the words in place of Accept: an edited block says why it needs no Accept, a removed one how it comes back. */
const keptTitle = (status: ReviewBlock["status"]) => (status === "edited" ? `${acceptWhy(status)}, Reject removes it` : status === "dropped" ? "Reject restores the block" : "");

/** One card per block in time order. Accepting needs an auto or accepted block, an edited block is kept already and a removed one is restored first, and the card says so in place of the Accept chip. */
export function blockCards(blocks: MadeBlock[], header: SessionHeader, selected: MadeBlock | null): BlockCard[] {
  return blocks.map((block, position) => ({
    position, name: blockName(position), epoch: block.epoch,
    minutes: (framesOf(block) / header.rate_hz / SECONDS_PER_MINUTE).toFixed(2),
    runs: header.runs.filter((r) => block.frame_start <= r.frame_start && r.frame_start <= block.frame_end).length,
    ...yieldOf(block), problems: block.problems, heading: headingText(block, header),
    status: block.status, glyph: STATUS_GLYPHS[block.status], chip: STATUS_CHIPS[block.status],
    selected: block === selected,
    accepted: block.status === "confirmed" || block.status === "edited", removed: block.status === "dropped",
    acceptable: block.status === "auto" || block.status === "confirmed",
    keptText: KEPT_WORDS[block.status] ?? "", keptTitle: keptTitle(block.status),
  }));
}

/** The stat tiles of the Summary card: the blocks by status, the time kept, the windows the manager counted at the settings, the cuts and the flagged runs. */
export function summaryTiles(preview: Preview, header: SessionHeader, settings: WindowSettings): Tile[] {
  const { blocks } = preview;
  const count = (status: ReviewBlock["status"]) => String(blocks.filter((b) => b.status === status).length);
  const kept = blocks.filter((b) => b.status !== "dropped");
  const keptS = kept.reduce((total, b) => total + framesOf(b), 0) / header.rate_hz;
  const epochS = header.epochs.filter((e) => header.selected_epochs.includes(e.epoch)).reduce((total, e) => total + e.duration_s, 0);
  const windows = kept.reduce((total, b) => total + (b.windows?.count ?? 0), 0);
  const trouble = kept.filter((b) => b.windows && !b.windows.verdict.ok).length;
  const { pauses, jumps, gaps } = cutsOf(header);
  const byStatus = (label: string, key: ReviewBlock["status"]): Tile => ({ label, value: count(key), note: "", title: "" });
  const keptNote = percent(epochS ? keptS / epochS : 0);
  return [
    byStatus("automatic", "auto"), byStatus("confirmed", "confirmed"), byStatus("edited", "edited"), byStatus("removed", "dropped"),
    { label: "kept", value: `${minutes(keptS)} min`, note: keptNote, title: `${keptNote} of the ${minutes(epochS)} min of ${header.selected_epochs.join(" and ")}` },
    { label: "windows", value: String(windows), note: `${settings.window_s} s each`, title: `${settings.window_s} s windows every ${settings.stride_s} s, ${counted(trouble, "block")} not ok` },
    { label: "flagged", value: String(preview.flagged_runs.length), note: `of ${header.runs.length} runs`, title: "runs flagged as mislabelled" },
    { label: "paused, jumped, lost", value: [pauses, jumps, gaps].map((cuts) => cuts.length).join(", "), note: "", title: "how often the recording paused, the position jumped and tracking was lost, which is where the rules cut", wide: true },
  ];
}

export function factsLine(header: SessionHeader): string {
  return `rat ${header.subject_id}, ${header.date}, ${header.protocol}, ${header.rate_hz} Hz, ${header.n_frames} frames, ${counted(header.n_initial_blocks, "block")} automatically derived`;
}

/** What the map card's title says is drawn: the session, the epochs of the scope (the one under the cursor when it is followed, and none when that epoch is not one the rules cut) and the block selected. */
export function mapTitle(sessionId: string, scope: string, kinds: string[], epochNow: string, selectedName: string): string {
  let epochs = scope;
  if (scope === FOLLOW_CURSOR) epochs = `${kinds.includes(epochNow) ? epochNow : "no epoch"} (following the cursor)`;
  else if (scope === ALL_EPOCHS) epochs = kinds.join(" and ");
  return [sessionId, epochs, selectedName].filter(Boolean).join(", ");
}

/** The window settings in use as one line, what the counts on the cards and tiles are at. */
export function settingsLine(s: WindowSettings): string {
  return `window ${s.window_s} s, stride ${s.stride_s} s, burn-in ${s.burn_in_s} s, horizon ${s.horizon_s} s, heading measured at least ${percent(s.min_heading_measured)}, ` +
    `at least ${counted(s.min_complete_trips, "complete trip")}, resampled at ${s.rate_hz} Hz`;
}

export interface Note {
  text: string;
  /** The text colour class: warn for what to read before trusting the session, muted for a fact. */
  tone: string;
}

const WARN = "text-warn";
const QUIET = "text-muted";

// The two warnings of the manager that the status header shows as chips, by the words the manager gives them and the words the chips say.
const FLAG_WARNINGS: Record<string, string> = {
  "reviewed under other rules": "reviewed under other rules",
  "saved blocks differ from the blocks today's rules give": "saved blocks differ from today's rules",
};

/** What the Session card says besides the facts and the status: why the tool cannot work with the session, the lab annotation that marks it excluded, the header's other warnings, the saved edits that no longer apply and the positions off the map. */
export function sessionNotes(header: SessionHeader, refusals: Refusal[], edits: Edit[]): Note[] {
  const notes: Note[] = [];
  if (!header.in_dataset) notes.push({ text: `Not in the dataset: ${header.reason}. It can be viewed and previewed, Save blocks is disabled.`, tone: WARN });
  if (header.annotated_exclude) notes.push({ text: ANNOTATED_NOTE, tone: QUIET });
  for (const warning of header.warnings) if (!(warning in FLAG_WARNINGS)) notes.push({ text: warning, tone: WARN });
  for (const { index, op, reason } of refusals) {
    notes.push({ text: `Edit ${index + 1} (${edits[index] ? editLabel(edits[index]) : op}) is not applied under the current rules: ${reason}`, tone: WARN });
  }
  if (header.occupancy.outside) notes.push({ text: `${counted(header.occupancy.outside, "position")} outside the room, drawn outside its outline.`, tone: QUIET });
  return notes;
}

export interface SaveToast {
  kind: "success" | "warning";
  text: string;
  /** The review file written, shown apart from the text. */
  path: string;
}

/** What a save tells: the review written and how many blocks were built from it, or what went wrong with the build, naming the blocks that failed and why. */
export function saveToast(saved: SavedBlocks): SaveToast {
  const wrote = `Saved, ${saved.replaced ? "replacing the earlier review" : "a new file"}`;
  const built = `built ${counted(saved.built, "block")}`;
  if (saved.build_error) return { kind: "warning", text: `${wrote}, but the build failed and nothing was built: ${saved.build_error}`, path: saved.file };
  if (saved.failed.length) {
    const failed = saved.failed.map((f) => `${f.block_id} (${f.problems.join(", ")})`).join(", ");
    return { kind: "warning", text: `${wrote}, ${built}, but ${saved.failed.length} failed: ${failed}`, path: saved.file };
  }
  return { kind: "success", text: `${wrote}, ${built}`, path: saved.file };
}

const STATE_BASE = "rounded-md border-2 px-3 py-1 text-base font-semibold";
const STATE_TONES = {
  warn: `${STATE_BASE} border-warn bg-warn/15 text-warn`,
  ok: `${STATE_BASE} border-ok bg-ok/15 text-ok`,
  muted: `${STATE_BASE} border-line bg-ink/5 text-muted`,
  neutral: `${STATE_BASE} border-ink/40 text-ink`,
};
const DATE_CHARS = 10;

export interface Chip {
  text: string;
  /** The classes that colour it. */
  chip: string;
  /** What it hovers as. */
  title: string;
}

export interface Status {
  /** The one chip that says where the review stands. */
  state: Chip;
  /** What else to know, beside it. */
  flags: Chip[];
}

const stateChip = (text: string, tone: keyof typeof STATE_TONES, title = ""): Chip => ({ text, chip: STATE_TONES[tone], title });

/**
 * Where the review stands as one strong chip, excluded, edits not saved, saved by whom and when, or automatic with nothing reviewed, and beside it
 * the edits the current rules skip and the manager's two warnings about the saved review.
 */
export function sessionStatus(header: Pick<SessionHeader, "warnings">, saved: Review | null, edits: number, dirty: boolean, skipped: number, excluded: boolean): Status {
  const unsaved = !edits && saved ? "edits cleared, the saved review is not loaded" : `${counted(edits, "edit")} not saved`;
  const reviewed = saved?.reviewed_at ? `saved by ${saved.reviewed_by} on ${formatStamp(saved.reviewed_at).slice(0, DATE_CHARS)}, ${counted(saved.edits.length, "edit")}` : "";
  const flags: Chip[] = [];
  let state: Chip;
  if (excluded) {
    state = stateChip("excluded", "muted", saved?.excluded_at ? `excluded by ${saved.excluded_by} ${stampWithSince(saved.excluded_at)}` : "");
    if (dirty) flags.push({ text: unsaved, chip: CHIP_WARN, title: "" });
  } else if (dirty) state = stateChip(unsaved, "warn", reviewed ? `the review on disk: ${reviewed}` : "");
  else if (reviewed) state = stateChip(reviewed, "ok", `saved ${stampWithSince(saved!.reviewed_at)}`);
  else state = stateChip("automatic, nothing reviewed yet", "neutral");
  if (skipped) flags.push({ text: `${counted(skipped, "edit")} skipped under today's rules`, chip: CHIP_WARN, title: "see the notes below for each one" });
  for (const warning of header.warnings) if (warning in FLAG_WARNINGS) flags.push({ text: FLAG_WARNINGS[warning], chip: CHIP_WARN, title: warning });
  return { state, flags };
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
    time: `${arrays.t[index].toFixed(2)} s`, frame: String(index + 1), speed: Number.isNaN(speed) ? "n/a" : `${speed.toFixed(2)} m/s`,
    lights: String(arrays.n_lights[index]), run: run ? `${run.run}, path ${run.path_id} ${run.clean ? "clean" : "dirty"}` : "none",
  };
}
