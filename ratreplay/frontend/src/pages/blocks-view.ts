import type { BlockArrays, BlockHeader, BlockRow, BlockWindows, Readiness, ReadinessBlock, ReadinessTotals, Verdict } from "../api/types";
import type { Fact } from "../ui/facts";
import { degrees, percent } from "../ui/format";
import type { Column } from "../ui/table";
import { stampWithSince } from "../ui/time";
import { compareSettings } from "./settings-view";
import type { SettingRow } from "./settings-view";

const SECONDS_PER_MINUTE = 60;

/** The datasets the index can judge: the real blocks, and each synthetic set as the API names it, `set:{id}`. */
export const REAL = "real";
const SET = "set:";
const REAL_NAME = "real lab blocks";

export interface WhichChoice {
  value: string;
  label: string;
}

/** What the judged line and the dataset choice call a dataset: the real one is the lab's blocks, a set is named by its id. */
export const datasetName = (which: string): string => (which === REAL ? REAL_NAME : `synthetic set ${which.slice(SET.length)}`);

/** The choices of the dataset: the real blocks first, then every synthetic set in the order given. */
export function whichChoices(sets: readonly string[]): WhichChoice[] {
  return [REAL, ...sets.map((id) => `${SET}${id}`)].map((value) => ({ value, label: datasetName(value) }));
}

export function verdictText(verdict: Verdict): string {
  return verdict.ok ? "ok" : `trouble, ${verdict.reasons.join(", ")}`;
}

/** A row of the index: the readiness of a block and how its session was built. */
export interface IndexRow extends ReadinessBlock {
  builtAt: string;
  compare: SettingRow[];
  /** Whether the session was built at other settings than the ones being tried. Only the counts and verdicts recorded at the build differ, the blocks do not depend on the settings. */
  otherSettings: boolean;
}

/** The index rows of a readiness answer, each marked when its session's build settings differ from the settings the answer is at. */
export function indexRows({ blocks, built, settings }: Readiness): IndexRow[] {
  return blocks.map((block) => {
    const made = built[block.session_id];
    const compare = compareSettings(settings, made.settings);
    return { ...block, builtAt: made.built_at, compare, otherSettings: compare.some((setting) => setting.differs) };
  });
}

export const COLUMNS: readonly Column<IndexRow>[] = [
  { key: "session", label: "Session", value: (r) => r.session_id, text: (r) => r.session_id },
  { key: "kind", label: "Kind", value: (r) => r.kind, text: (r) => r.kind },
  { key: "status", label: "Status", value: (r) => r.status, text: (r) => r.status },
  { key: "minutes", label: "Minutes", value: (r) => r.duration_s, text: (r) => (r.duration_s / SECONDS_PER_MINUTE).toFixed(1), numeric: true },
  { key: "runs", label: "Runs", value: (r) => r.n_runs, text: (r) => String(r.n_runs), numeric: true },
  { key: "complete", label: "Complete trips", value: (r) => r.n_complete_trips, text: (r) => String(r.n_complete_trips), numeric: true },
  { key: "partial", label: "Partial trips", value: (r) => r.n_trips - r.n_complete_trips, text: (r) => String(r.n_trips - r.n_complete_trips), numeric: true },
  { key: "filled", label: "Filled", value: (r) => r.heading_filled_s / r.duration_s, text: (r) => percent(r.heading_filled_s / r.duration_s), numeric: true },
  { key: "held", label: "Held", value: (r) => r.heading_held_s / r.duration_s, text: (r) => percent(r.heading_held_s / r.duration_s), numeric: true },
  { key: "windows", label: "Windows", value: (r) => r.count, text: (r) => String(r.count), numeric: true },
  { key: "verdict", label: "Verdict", value: (r) => verdictText(r.verdict), text: (r) => verdictText(r.verdict), tone: (r) => (r.verdict.ok ? "text-ok" : "text-bad") },
  { key: "built", label: "Built with", value: (r) => Number(r.otherSettings), text: (r) => (r.otherSettings ? "built at other settings" : "as tried"), tone: (r) => (r.otherSettings ? "text-warn" : "text-muted") },
];

/** The facts the expanded row of a block adds to the columns. */
export function blockFacts(row: BlockRow): Fact[] {
  return [
    { label: "environment", value: row.environment },
    { label: "rat", value: `${row.subject_id}, ${row.date}, ${row.protocol}` },
    { label: "lab frames", value: `${row.frame_start} to ${row.frame_end}` },
    { label: "frame scale", value: `${row.scale_px_per_m.toFixed(1)} px per m` },
    { label: "rotation", value: degrees(row.rotation_rad, 1) },
    { label: "LED offset", value: degrees(row.led_offset_rad, 1) },
    { label: "kinematics version", value: String(row.kinematics_version) },
    { label: "reviewed by", value: row.reviewed_by ?? "nobody, the block is automatic" },
  ];
}

/** The facts of an index row's expanded details: those of the block and when its session was built. */
export function indexFacts(row: IndexRow): Fact[] {
  return [...blockFacts(row), { label: "session built", value: stampWithSince(row.builtAt) }];
}

/** The facts of the block open in the player: those of its row and the windows it yields at the settings. */
export function openBlockFacts(header: BlockHeader, found: BlockWindows): Fact[] {
  return [...blockFacts(header.row), { label: "rate", value: `${header.rate_hz} Hz` }, { label: "windows", value: String(found.count) }];
}

export interface TotalTile {
  label: string;
  value: string;
}

/** The stat tiles of the totals, as the API returns them. */
export function totalTiles(totals: ReadinessTotals): TotalTile[] {
  return [
    { label: "blocks", value: String(totals.blocks) }, { label: "ok", value: String(totals.ok) }, { label: "trouble", value: String(totals.trouble) },
    { label: "windows", value: String(totals.windows) }, { label: "windows, ok blocks", value: String(totals.windows_ok) },
  ];
}

export interface BlockLine {
  id: string;
  session: string;
  kind: string;
  status: string;
  minutes: string;
  ok: boolean;
  verdict: string;
}

/** The header line before a block is open, so the page has something to bind to. */
export const NO_LINE: BlockLine = { id: "", session: "", kind: "", status: "", minutes: "", ok: true, verdict: "" };

/** The block header line: its id, session, kind, status, minutes and its verdict with the reasons. */
export function blockLine(row: BlockRow, verdict: Verdict): BlockLine {
  const { block_id, session_id, kind, status, duration_s } = row;
  return { id: block_id, session: session_id, kind, status, minutes: (duration_s / SECONDS_PER_MINUTE).toFixed(1), ok: verdict.ok, verdict: verdictText(verdict) };
}

export interface Live {
  time: string;
  frame: string;
  speed: string;
  lights: string;
  run: string;
  phase: string;
}

const spanAt = <S extends { first: number; last: number }>(spans: S[], index: number): S | undefined => spans.find((s) => s.first <= index && index <= s.last);

/** What the live tiles show at a frame index of the block: its time, the lab frame, the speed, the lights, and the run and phase under the cursor. */
export function liveTiles(header: BlockHeader, arrays: BlockArrays, index: number): Live {
  const run = spanAt(header.runs, index);
  const speed = arrays.speed[index];
  return {
    time: `${arrays.t[index].toFixed(2)} s`, frame: String(arrays.frame[index]), speed: Number.isNaN(speed) ? "n/a" : `${speed.toFixed(2)} m/s`,
    lights: String(arrays.n_lights[index]), run: run ? `${run.run}, path ${run.path_id} ${run.clean ? "clean" : "dirty"}` : "none",
    phase: spanAt(header.phases, index)?.phase ?? "none",
  };
}
