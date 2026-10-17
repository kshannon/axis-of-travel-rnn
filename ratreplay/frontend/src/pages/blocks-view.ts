import type { BlockArrays, BlockHeader, BlockRow, Totals, WindowSettings } from "../api/types";
import type { Fact } from "../ui/facts";
import { degrees, percent } from "../ui/format";
import type { Column } from "../ui/table";
import { counted } from "../ui/text";

const SECONDS_PER_MINUTE = 60;

/** The window settings as inputs, each with its label and the step of its arrows. */
export const SETTING_FIELDS: readonly { key: keyof WindowSettings; label: string; step: string }[] = [
  { key: "window_s", label: "window (s)", step: "1" },
  { key: "stride_s", label: "stride (s)", step: "0.5" },
  { key: "burn_in_s", label: "burn-in (s)", step: "0.5" },
  { key: "horizon_s", label: "horizon (s)", step: "0.5" },
  { key: "train_rate_hz", label: "training rate (Hz)", step: "1" },
  { key: "min_heading_measured", label: "min measured heading", step: "0.05" },
  { key: "min_complete_trips", label: "min complete trips", step: "1" },
];

export function verdictText(ok: boolean, reason: string | null): string {
  return ok ? "ok" : `trouble, ${reason}`;
}

export const COLUMNS: readonly Column<BlockRow>[] = [
  { key: "session", label: "Session", value: (r) => r.session_id, text: (r) => r.session_id },
  { key: "kind", label: "Kind", value: (r) => r.kind, text: (r) => r.kind },
  { key: "status", label: "Status", value: (r) => r.status, text: (r) => r.status },
  { key: "minutes", label: "Minutes", value: (r) => r.duration_s, text: (r) => (r.duration_s / SECONDS_PER_MINUTE).toFixed(1), numeric: true },
  { key: "runs", label: "Runs", value: (r) => r.n_runs, text: (r) => String(r.n_runs), numeric: true },
  { key: "complete", label: "Complete trips", value: (r) => r.n_complete_trips, text: (r) => String(r.n_complete_trips), numeric: true },
  { key: "partial", label: "Partial trips", value: (r) => r.n_trips - r.n_complete_trips, text: (r) => String(r.n_trips - r.n_complete_trips), numeric: true },
  { key: "measured", label: "Heading measured", value: (r) => r.heading_measured, text: (r) => percent(r.heading_measured), numeric: true },
  { key: "filled", label: "Filled", value: (r) => r.heading_filled_s / r.duration_s, text: (r) => percent(r.heading_filled_s / r.duration_s), numeric: true },
  { key: "held", label: "Held", value: (r) => r.heading_held_s / r.duration_s, text: (r) => percent(r.heading_held_s / r.duration_s), numeric: true },
  { key: "windows", label: "Windows", value: (r) => r.n_windows, text: (r) => String(r.n_windows), numeric: true },
  { key: "verdict", label: "Verdict", value: (r) => verdictText(r.ok, r.reason), text: (r) => verdictText(r.ok, r.reason), tone: (r) => (r.ok ? "text-ok" : "text-bad") },
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

export interface TotalsGroup {
  kind: string;
  tiles: { label: string; value: string }[];
}

/** The stat tiles of each kind and overall: the blocks ok and in trouble, the windows the ok ones yield and their hours. */
export function totalGroups(totals: Record<string, Totals>): TotalsGroup[] {
  return Object.entries(totals).map(([kind, t]) => ({
    kind,
    tiles: [
      { label: "blocks ok", value: String(t.blocks_ok) }, { label: "trouble", value: String(t.blocks_trouble) },
      { label: "windows", value: String(t.windows) }, { label: "hours ok", value: t.hours_ok.toFixed(2) },
    ],
  }));
}

/** The line over the index saying which settings its verdicts were tested at. */
export function testedLine(s: WindowSettings): string {
  return `Verdicts at a ${s.window_s} s window plus a ${s.horizon_s} s horizon every ${s.stride_s} s, measured heading at least ${percent(s.min_heading_measured)}, a track block with at least ${counted(s.min_complete_trips, "complete trip")}.`;
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

/** The block header line: its id, session, kind, status, minutes and its verdict with the reason. */
export function blockLine(header: BlockHeader): BlockLine {
  const { block_id, session_id, kind, status, duration_s, verdict } = header;
  return {
    id: block_id, session: session_id, kind, status, minutes: (duration_s / SECONDS_PER_MINUTE).toFixed(1), ok: verdict.ok,
    verdict: verdictText(verdict.ok, verdict.reason),
  };
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
