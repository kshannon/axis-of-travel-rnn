import type { PairArrays, PairHeader, Reveal, SetRow, Side, Tally } from "../api/types";
import { colourOf } from "../draw/layers";
import { FRAMES_LANE } from "../draw/lanes";
import type { LaneSpec, Scene } from "../draw/lanes";
import { counted } from "../ui/text";

/** The two sides a pair is shown on, in the order the cards stand. */
export const SIDES: readonly Side[] = ["left", "right"];
const SIDE_WORDS: Record<Side, string> = { left: "left", right: "right" };
const OTHER: Record<Side, Side> = { left: "right", right: "left" };

/** What each side is called once revealed. */
export const REAL = "real";
export const SYNTHETIC = "synthetic";

/** The kinds a pair can be asked for, any kind the set has first. */
export const ANY_KIND = "";
const ANY_LABEL = "any kind";

/** The one lane under each map: the speed trace, named for what it shows. */
const SPEED_LANE: readonly LaneSpec[] = [{ name: FRAMES_LANE, label: "speed", weight: 1 }];

/** The lane with nothing in it, drawn while no pair is open. */
export const EMPTY_SCENE: Scene = { lanes: SPEED_LANE, rateHz: 1, nFrames: 0, bars: [], breaks: [], frames: [] };

/** The tally of a set no one has answered on. */
export const EMPTY_TALLY: Tally = { n: 0, correct: 0, by: {} };

const PERCENT = 100;

/** Where the quiz stands: no pair yet, one being read, one open for an answer, or one answered and revealed. */
export type Phase = "empty" | "loading" | "open" | "answered";

export interface Choice {
  value: string;
  label: string;
}

/** The sets to quiz on, newest first, each named with what it holds. */
export function setChoices(rows: SetRow[]): Choice[] {
  return [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at)).map((row) => ({
    value: row.set_id, label: `${row.set_id} (${counted(row.n_blocks, "block")}, ${row.kinds.join(", ")})`,
  }));
}

/** The kinds a pair can be drawn of: any, then each kind the set has. */
export function kindChoices(kinds: readonly string[]): Choice[] {
  return [{ value: ANY_KIND, label: ANY_LABEL }, ...kinds.map((kind) => ({ value: kind, label: kind }))];
}

/** Why a new pair cannot be opened, none when it can. */
export function newPairBlocked(setId: string, phase: Phase): string {
  if (!setId) return "there is no synthetic set to quiz on, generate one on Synthetic";
  if (phase === "loading") return "a pair is being read";
  return "";
}

/** Why the person cannot answer yet, none while a pair is open. */
export function guessBlocked(phase: Phase): string {
  if (phase === "empty") return "open a pair first";
  if (phase === "loading") return "the pair is being read";
  if (phase === "answered") return "answered, open a new pair";
  return "";
}

/** The chip on a side's card once the pair is revealed: real or synthetic, none before. */
export function sideChip(reveal: Reveal | null, side: Side): string {
  if (!reveal) return "";
  return reveal.real_side === side ? REAL : SYNTHETIC;
}

/** The verdict line after an answer: right or wrong, which side was real and which blocks they were. */
export function revealLine(reveal: Reveal): string {
  const real = SIDE_WORDS[reveal.real_side];
  const synthetic = SIDE_WORDS[OTHER[reveal.real_side]];
  return `${reveal.correct ? "Right" : "Wrong"}, the ${real} block is real (${reveal.real_block}) and the ${synthetic} one is synthetic (${reveal.synthetic_block}).`;
}

/** The tally of a set as one line: how many pairs were answered, how many right and the share. */
export function tallyLine(tally: Tally): string {
  if (!tally.n) return "No pair answered yet.";
  return `${counted(tally.n, "pair")} answered, ${tally.correct} right, ${Math.round((PERCENT * tally.correct) / tally.n)} percent.`;
}

export interface TallyRow {
  by: string;
  answered: string;
  right: string;
  share: string;
}

/** The tally per person, most answered first. */
export function tallyRows(tally: Tally): TallyRow[] {
  return Object.entries(tally.by).sort(([, a], [, b]) => b.n - a.n).map(([by, { n, correct }]) => ({
    by, answered: String(n), right: String(correct), share: `${Math.round((PERCENT * correct) / n)}%`,
  }));
}

/** The frames the shared clock runs over at its rate: the longer side's time, so both play to their end, the shorter side holding its last frame. */
export function sharedFrames(headers: readonly PairHeader[], clockRateHz: number): number {
  return Math.max(...headers.map((header) => Math.round((header.row.n_frames * clockRateHz) / header.rate_hz)));
}

/** The frame a side shows at the shared clock's index, by time so a side at another rate plays at the right speed, its last once the clock has run past it. */
export function sideIndex(index: number, clockRateHz: number, header: PairHeader): number {
  return Math.min(Math.round((index * header.rate_hz) / clockRateHz), header.row.n_frames - 1);
}

/** The timeline under a side's map: the speed trace alone, no runs, trips or windows, since those would tell the sides apart. */
export function speedScene(header: PairHeader, arrays: PairArrays, speedTop: number): Scene {
  return {
    lanes: SPEED_LANE, rateHz: header.rate_hz, nFrames: header.row.n_frames, bars: [], breaks: [],
    frames: [{ kind: "trace", values: arrays.speed, top: speedTop, colour: colourOf("speed") }],
  };
}
