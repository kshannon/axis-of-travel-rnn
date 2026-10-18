import type { BlockArrays, BlockHeader, BlockRow, BlockWindows, Readiness, ReadinessBlock, ReadinessTotals, Selected, Verdict, WindowSettings } from "../api/types";
import type { Fact } from "../ui/facts";
import { degrees, percent } from "../ui/format";
import type { Column } from "../ui/table";
import { counted, settingsText } from "../ui/text";
import { stampWithSince } from "../ui/time";

const SECONDS_PER_MINUTE = 60;

/** The datasets the index can judge. The Synthetic page adds its sets to the choices. */
export const REAL = "real";
export const WHICH_CHOICES: readonly string[] = [REAL];

/** The window settings as inputs, each with its label and the step of its arrows. */
export const SETTING_FIELDS: readonly { key: keyof WindowSettings; label: string; step: string }[] = [
  { key: "window_s", label: "window (s)", step: "1" },
  { key: "stride_s", label: "stride (s)", step: "0.5" },
  { key: "burn_in_s", label: "burn-in (s)", step: "0.5" },
  { key: "horizon_s", label: "horizon (s)", step: "0.5" },
  { key: "rate_hz", label: "training rate (Hz)", step: "1" },
  { key: "min_heading_measured", label: "min measured heading", step: "0.05" },
  { key: "min_complete_trips", label: "min complete trips", step: "1" },
];

export function verdictText(verdict: Verdict): string {
  return verdict.ok ? "ok" : `trouble, ${verdict.reasons.join(", ")}`;
}

/** One setting being tried beside the one a block's session was built with. */
export interface SettingRow {
  label: string;
  tried: string;
  built: string;
  differs: boolean;
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
    const compare = SETTING_FIELDS.map(({ key, label }) => ({
      label, tried: String(settings[key]), built: String(made.settings[key]), differs: made.settings[key] !== settings[key],
    }));
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

/** The line over the index saying which settings its verdicts were tested at. */
export function testedLine(s: WindowSettings): string {
  return `Verdicts at a ${s.window_s} s window plus a ${s.horizon_s} s horizon every ${s.stride_s} s, measured heading at least ${percent(s.min_heading_measured)}, a track block with at least ${counted(s.min_complete_trips, "complete trip")}.`;
}

/** The line saying which settings the export reads, none when none were selected. */
export function selectedLine(selected: Selected["selected"]): string {
  if (!selected) return "No settings are selected for export yet.";
  const { settings, totals, selected_at, selected_by } = selected;
  return `Selected for export ${stampWithSince(selected_at)} by ${selected_by}: ${settingsText(settings)}. They gave ${totals.ok} of ${counted(totals.blocks, "block")} ok and ${counted(totals.windows_ok, "window")} in them.`;
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
