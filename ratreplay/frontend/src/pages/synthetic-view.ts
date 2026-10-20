import type { Generated, Quantiles, Recipe, Recipes, SessionRow, SetRow } from "../api/types";
import { counted } from "../ui/text";
import { stampWithSince } from "../ui/time";

const SECONDS_PER_MINUTE = 60;
const DECIMALS = 2;
const NONE = "n/a";
const SEED_RANGE = 1_000_000;

/** The epoch kinds a set is generated of, in the order the generator lays them out, with the minutes each defaults to. */
export const KINDS = ["arena", "track"] as const;
export const DEFAULT_MINUTES: Record<string, number> = { arena: 10, track: 20 };

/** The quantiles of a distribution as the recipe names them, with the words a row shows. */
const QUANTILE_ROWS: readonly (readonly [keyof Quantiles, string])[] = [["q05", "5%"], ["q25", "25%"], ["q50", "median"], ["q75", "75%"], ["q95", "95%"], ["mean", "mean"]];

/** A seed drawn for the Generate card, so two sets made in a row differ unless the person asks for the same one. */
export const randomSeed = (): number => Math.floor(Math.random() * SEED_RANGE);

/** The sessions a set can be generated from: those with built blocks, in session order. */
export function sourceChoices(sessions: SessionRow[]): SessionRow[] {
  return sessions.filter((row) => row.built > 0);
}

/** The seconds per kind of a generate, from the minutes typed, a kind at zero minutes left out. */
export function lengthsOf(minutes: Record<string, number>): Record<string, number> {
  return Object.fromEntries(KINDS.filter((kind) => minutes[kind] > 0).map((kind) => [kind, minutes[kind] * SECONDS_PER_MINUTE]));
}

/** Why a set cannot be generated from the form as it stands, none when it can. */
export function generateBlocked(sources: string[], seed: number, minutes: Record<string, number>): string {
  if (!sources.length) return "choose at least one source session";
  if (!Number.isInteger(seed) || seed < 0) return "the seed must be a whole number, 0 or more";
  if (!Object.keys(lengthsOf(minutes)).length) return "give at least one kind some minutes";
  return "";
}

/** What the toast says of a generate: the set, how many blocks were built and failed, and the first warning. */
export function generatedText(result: Generated): string {
  const first = result.warnings.length ? `. ${result.warnings[0]}` : "";
  return `Generated set ${result.set_id}: ${counted(result.built, "block")} built (${result.kinds.join(", ")}), ${result.failed.length} failed${first}`;
}

/** What the confirmation says before a set is deleted. */
export const deletePrompt = (setId: string): string => `Delete set ${setId}? Its blocks and guesses go with it.`;

/** A row of the sets table, every cell as words. */
export interface SetLine {
  set_id: string;
  created: string;
  by: string;
  sources: string;
  seed: string;
  /** The minutes generated per kind, such as "arena 10, track 20". */
  minutes: string;
  blocks: string;
  /** The guesses with how many were right, such as "4, 3 correct", or none. */
  guesses: string;
}

const minutesText = (length_s: Record<string, number>): string =>
  Object.entries(length_s).map(([kind, seconds]) => `${kind} ${+(seconds / SECONDS_PER_MINUTE).toFixed(1)}`).join(", ");

/** The sets as the table shows them, newest first. */
export function setLines(rows: SetRow[]): SetLine[] {
  return [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at)).map((row) => ({
    set_id: row.set_id, created: stampWithSince(row.created_at), by: row.created_by, sources: row.sources.join(", "), seed: String(row.seed),
    minutes: minutesText(row.length_s), blocks: `${row.n_blocks} (${row.kinds.join(", ")})`,
    guesses: row.n_guesses ? `${row.n_guesses}, ${row.n_correct} correct` : "none",
  }));
}

/** One line of the comparison: a recipe number of the real blocks beside the same number of the synthetic ones. */
export interface CompareRow {
  label: string;
  real: string;
  synthetic: string;
}

/** The comparison of one kind: its rows, or why there are none. */
export interface CompareTable {
  kind: string;
  rows: CompareRow[];
  note: string;
}

/** A number to two decimals, n/a when there is none, and a value that rounds to zero shown without a minus sign. */
export function fixed(value: number | null | undefined): string {
  if (value === null || value === undefined) return NONE;
  const text = value.toFixed(DECIMALS);
  return Number(text) === 0 ? text.replace("-", "") : text;
}

type Numbers = Record<string, number | null | undefined>;

/** The union of both recipes' keys under a nested record, in the order they first appear, so a path or phase one side lacks still has its row. */
function keysOf(real: Record<string, unknown> | undefined, synthetic: Record<string, unknown> | undefined): string[] {
  return [...new Set([...Object.keys(real ?? {}), ...Object.keys(synthetic ?? {})])];
}

/** The rows of every statistic in `numbers`, the label of each prefixed. */
function numberRows(prefix: string, real: Numbers | undefined, synthetic: Numbers | undefined, labels: readonly (readonly [string, string])[]): CompareRow[] {
  return labels.map(([key, word]) => ({ label: `${prefix} ${word}`, real: fixed(real?.[key]), synthetic: fixed(synthetic?.[key]) }));
}

const quantileRows = (prefix: string, real: Quantiles | undefined, synthetic: Quantiles | undefined): CompareRow[] =>
  numberRows(prefix, real as Numbers | undefined, synthetic as Numbers | undefined, QUANTILE_ROWS);

/** A number or a distribution times a factor, for a unit two decimals can show (metres as centimetres or millimetres). */
const times = (value: number | null | undefined, factor: number): number | null | undefined => (value === null || value === undefined ? value : value * factor);
const scaled = (q: Quantiles | undefined, factor: number): Quantiles | undefined =>
  q && (Object.fromEntries(Object.entries(q).map(([key, value]) => [key, times(value, factor)])) as unknown as Quantiles);
const CM_PER_M = 100;
const MM_PER_M = 1000;

/** The rows of a record of plain numbers, one per key of either side. */
function recordRows(prefix: string, real: Record<string, number> | undefined, synthetic: Record<string, number> | undefined): CompareRow[] {
  return keysOf(real, synthetic).map((key) => ({ label: `${prefix} ${key}`, real: fixed(real?.[key]), synthetic: fixed(synthetic?.[key]) }));
}

/** The rows of one kind's recipes side by side: the counts, the speed and turn rate quantiles, the still fraction, the heading spread, the tracking noise, the pauses, the track's runs, speed variation, centreline distance, dwells, trips and goal shares, the arena's speed variation and boundary distance, and the phase shares. */
export function compareRows(real: Recipe | undefined, synthetic: Recipe | undefined): CompareRow[] {
  const rows: CompareRow[] = [
    { label: "blocks", real: String(real?.counts.blocks ?? NONE), synthetic: String(synthetic?.counts.blocks ?? NONE) },
    { label: "seconds", real: fixed(real?.counts.seconds), synthetic: fixed(synthetic?.counts.seconds) },
    ...quantileRows("speed (m/s)", real?.speed, synthetic?.speed),
    ...quantileRows("turn rate (rad/s)", real?.turn_rate, synthetic?.turn_rate),
    { label: "turn rate, mean of the absolute value", real: fixed(real?.turn_rate_abs_mean), synthetic: fixed(synthetic?.turn_rate_abs_mean) },
    { label: "still fraction", real: fixed(real?.still_fraction), synthetic: fixed(synthetic?.still_fraction) },
    { label: "heading spread (rad)", real: fixed(real?.heading_spread_rad), synthetic: fixed(synthetic?.heading_spread_rad) },
    { label: "tracking noise (mm)", real: fixed(times(real?.tracking_noise_m, MM_PER_M)), synthetic: fixed(times(synthetic?.tracking_noise_m, MM_PER_M)) },
    { label: "pauses per minute", real: fixed(real?.pauses.per_min), synthetic: fixed(synthetic?.pauses.per_min) },
    ...quantileRows("pause duration (s)", real?.pauses.duration_s, synthetic?.pauses.duration_s),
  ];
  for (const path of keysOf(real?.runs, synthetic?.runs)) {
    rows.push({ label: `runs on path ${path}`, real: String(real?.runs?.[path]?.count ?? NONE), synthetic: String(synthetic?.runs?.[path]?.count ?? NONE) });
    rows.push(...quantileRows(`run duration on path ${path} (s)`, real?.runs?.[path]?.duration_s, synthetic?.runs?.[path]?.duration_s));
  }
  if (real?.speed_cv_run !== undefined || synthetic?.speed_cv_run !== undefined) {
    rows.push({ label: "speed variation within a run (sd over mean)", real: fixed(real?.speed_cv_run), synthetic: fixed(synthetic?.speed_cv_run) });
  }
  if (real?.lateral_m || synthetic?.lateral_m) rows.push(...quantileRows("distance from the centreline (cm)", scaled(real?.lateral_m, CM_PER_M), scaled(synthetic?.lateral_m, CM_PER_M)));
  for (const site of keysOf(real?.dwell_s, synthetic?.dwell_s)) rows.push(...quantileRows(`dwell at ${site} (s)`, real?.dwell_s?.[site], synthetic?.dwell_s?.[site]));
  if (real?.trips_per_min !== undefined || synthetic?.trips_per_min !== undefined) {
    rows.push({ label: "trips per minute", real: fixed(real?.trips_per_min), synthetic: fixed(synthetic?.trips_per_min) });
  }
  rows.push(...recordRows("goal share, path", real?.goal_share, synthetic?.goal_share));
  if (real?.speed_cv !== undefined || synthetic?.speed_cv !== undefined) {
    rows.push({ label: "speed variation within a running stretch (sd over mean)", real: fixed(real?.speed_cv), synthetic: fixed(synthetic?.speed_cv) });
  }
  if (real?.boundary_distance_m || synthetic?.boundary_distance_m) rows.push(...quantileRows("boundary distance (m)", real?.boundary_distance_m, synthetic?.boundary_distance_m));
  rows.push(...recordRows("phase share", real?.phase_share, synthetic?.phase_share));
  return rows;
}

/** The comparison per kind, every kind either recipe has, in the generator's order: a kind one side lacks says so and still shows the other side's numbers. */
export function compareTables(real: Recipes, synthetic: Recipes): CompareTable[] {
  const kinds = [...KINDS.filter((kind) => kind in real || kind in synthetic), ...keysOf(real, synthetic).filter((kind) => !(KINDS as readonly string[]).includes(kind))];
  return kinds.map((kind) => ({
    kind, rows: compareRows(real[kind], synthetic[kind]),
    note: !(kind in real) ? `the sources have no ${kind} blocks` : !(kind in synthetic) ? `the set has no ${kind} blocks` : "",
  }));
}

/** The caption under the comparison: what the two columns are and which set and sources made them. */
export function compareCaption(setId: string, sources: string[], seed: number): string {
  return `Each row is one recipe number, measured the same way on the real blocks of ${sources.join(", ")} (left) and on the blocks of set ${setId} (right, seed ${seed}). ` +
    `Numbers to ${DECIMALS} decimals, ${NONE} where a side has no value. A close pair of columns means the generator reproduced that statistic.`;
}
