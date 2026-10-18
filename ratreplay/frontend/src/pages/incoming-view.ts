import type { FormatGroup } from "../api/describe";
import type { Folder, Health, MadeBlock, SessionHeader, SessionRow } from "../api/types";
import { cutsOf } from "../session/cuts";
import type { Fact } from "../ui/facts";
import { degrees } from "../ui/format";
import { folderStatus, worstStatus } from "../ui/status";
import type { Status } from "../ui/status";
import type { Column } from "../ui/table";
import { counted } from "../ui/text";
import { formatStamp, stampWithSince } from "../ui/time";

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const NOTES_EXCERPT = 60;
const LISTED = 6;
const NOT_SET = "not set";
const TRANSFORMED_FORMAT = "Transformed folder";

/** One line of the strip over the page: where something is read from, whether it is usable, and what is wrong with it. */
export interface StripLine {
  label: string;
  path: string;
  status: Status;
  problems: string[];
  detail: string;
  /** Whether the line carries the Reload button, which reads the config file again. */
  reloads: boolean;
}

/** What the converter's folder holds, in one muted phrase. */
function transformedDetail(folder: Folder): string {
  const sessions = folder.counts.sessions;
  const run = folder.manifest?.timestamp;
  return [sessions === undefined ? "" : counted(sessions, "session"), run ? `converter run ${formatStamp(run)}` : ""].filter(Boolean).join(", ");
}

/** The three lines of the strip: the lab data, the environment geometry and the config file that names them. */
export function stripLines(health: Health): StripLine[] {
  const { transformed, environments } = health;
  return [
    { label: "lab data read from", path: transformed.root ?? NOT_SET, status: folderStatus(transformed, transformed.counts.sessions), problems: transformed.problems, detail: transformedDetail(transformed), reloads: false },
    {
      label: "environment geometry read from", path: environments.root ?? NOT_SET, status: environments.problems.length ? "problem" : "ok", problems: environments.problems,
      detail: environments.counts.environments === undefined ? "" : counted(environments.counts.environments, "environment"), reloads: false,
    },
    { label: "config file", path: health.config_path, status: "ok", problems: [], detail: "", reloads: true },
  ];
}

/** The state of the card holding the strip: the worst of its lines. */
export const stripStatus = (lines: StripLine[]): Status => worstStatus(lines.map((line) => line.status));

/** The problems found under the strip, each with the line it belongs to. */
export function stripProblems(lines: StripLine[]): { label: string; text: string }[] {
  return lines.flatMap((line) => line.problems.map((text) => ({ label: line.label, text })));
}

/** The tables of the transformed files out of the format's groups. */
export function incomingGroups(groups: FormatGroup[]): FormatGroup[] {
  return groups.filter((group) => group.title === TRANSFORMED_FORMAT);
}

/** Minutes of the arena, track and variant epochs, which is what the index lists of a session. */
export function minutesOf(row: SessionRow): number {
  return row.epochs.reduce((total, epoch) => total + epoch.duration_s, 0) / SECONDS_PER_MINUTE;
}

const excerpt = (notes: string) => (notes.length > NOTES_EXCERPT ? `${notes.slice(0, NOTES_EXCERPT)}...` : notes);

export const COLUMNS: readonly Column<SessionRow>[] = [
  { key: "rat", label: "Rat", value: (r) => r.subject_id, text: (r) => r.subject_id },
  { key: "date", label: "Date", value: (r) => r.date, text: (r) => r.date },
  { key: "protocol", label: "Protocol", value: (r) => r.protocol, text: (r) => r.protocol },
  { key: "dataset", label: "In dataset", value: (r) => Number(r.in_dataset), text: (r) => (r.in_dataset ? "yes" : "no") },
  { key: "excluded", label: "Excluded", value: (r) => Number(r.excluded), text: (r) => (r.excluded ? "yes" : "") },
  { key: "minutes", label: "Minutes", value: minutesOf, text: (r) => minutesOf(r).toFixed(1), numeric: true },
  { key: "runs", label: "Runs", value: (r) => r.n_runs, text: (r) => String(r.n_runs), numeric: true },
  { key: "confirmed", label: "Confirmed blocks", value: (r) => r.n_confirmed, text: (r) => String(r.n_confirmed), numeric: true },
  { key: "built", label: "Built blocks", value: (r) => r.built, text: (r) => String(r.built), numeric: true },
  { key: "by", label: "Reviewed by", value: (r) => r.reviewed_by, text: (r) => r.reviewed_by ?? "" },
  { key: "at", label: "Reviewed", value: (r) => r.reviewed_at, text: (r) => stampWithSince(r.reviewed_at) },
  { key: "notes", label: "Notes", value: (r) => r.notes || null, text: (r) => excerpt(r.notes) },
];

/** The rows whose session id or rat contains the text. */
export function filterRows(rows: SessionRow[], text: string): SessionRow[] {
  const needle = text.trim().toLowerCase();
  return needle ? rows.filter((row) => `${row.session_id} ${row.subject_id}`.toLowerCase().includes(needle)) : rows;
}

export function briefList(items: string[], limit = LISTED): string {
  return items.length <= limit ? items.join(", ") : `${items.slice(0, limit).join(", ")} and ${items.length - limit} more`;
}

function numbered(items: string[], where: string): string {
  return items.length ? `${items.length}, ${where} ${briefList(items)}` : "none";
}

/** The hover title of a row: the session, and why the tool cannot work with it when it cannot. */
export function rowTitle(row: SessionRow): string {
  return row.in_dataset ? row.session_id : `${row.session_id}, not in the dataset: ${row.reason}`;
}

/** The facts of the details panel: those the index row has, then those the session header adds once it arrives. */
export function sessionFacts(row: SessionRow, header: SessionHeader | null): Fact[] {
  const facts = [
    { label: "in dataset", value: row.in_dataset ? "yes" : `no, ${row.reason}` },
    { label: "group", value: row.group },
    { label: "frame rate", value: `${row.rate_hz} Hz` },
    { label: "runs", value: `${row.n_runs}, ${row.n_clean_runs} clean` },
  ];
  if (!header) return facts;
  const { pauses, jumps, gaps } = cutsOf(header);
  return [
    ...facts,
    { label: "frames", value: String(header.n_frames) },
    { label: "pauses", value: numbered(pauses.map(String), "at frames") },
    { label: "gaps", value: numbered(gaps.map(([first, last]) => `${first} to ${last}`), "frames") },
    { label: "jumps", value: numbered(jumps.map(String), "at frames") },
    { label: "LED offset", value: `${degrees(header.frame.led_offset_rad)}, concentration ${header.frame.led_offset_r.toFixed(2)}` },
  ];
}

/** A block of the session header in one line: its name, frames, seconds and status. */
export function blockText(block: MadeBlock, rateHz: number): string {
  const seconds = (block.frame_end - block.frame_start + 1) / rateHz;
  return `${block.epoch} ${block.block_id.slice(-2)}, frames ${block.frame_start} to ${block.frame_end}, ${seconds.toFixed(0)} s, ${block.status}`;
}

const sum = (rows: SessionRow[], value: (row: SessionRow) => number) => rows.reduce((total, row) => total + value(row), 0);

/** The numbers of the totals row: the sessions in the dataset, reviewed and excluded, the blocks confirmed, the hours confirmed per epoch kind and the blocks built. */
function totals(rows: SessionRow[]) {
  const hours = (kind: string) => sum(rows, (row) => row.confirmed_s[kind] ?? 0) / SECONDS_PER_HOUR;
  return {
    sessions: rows.length,
    inDataset: rows.filter((row) => row.in_dataset).length,
    reviewed: rows.filter((row) => row.reviewed).length,
    excluded: rows.filter((row) => row.excluded).length,
    confirmed: sum(rows, (row) => row.n_confirmed),
    arenaHours: hours("arena"),
    trackHours: hours("track"),
    built: sum(rows, (row) => row.built),
  };
}

export interface Tile {
  label: string;
  value: string;
}

/** The tiles across the top of the sessions index, in the order they are read. */
export function tiles(rows: SessionRow[]): Tile[] {
  const t = totals(rows);
  return [
    { label: "in the dataset", value: `${t.inDataset} of ${t.sessions}` },
    { label: "reviewed", value: String(t.reviewed) },
    { label: "excluded", value: String(t.excluded) },
    { label: "blocks confirmed", value: String(t.confirmed) },
    { label: "arena hours confirmed", value: t.arenaHours.toFixed(2) },
    { label: "track hours confirmed", value: t.trackHours.toFixed(2) },
    { label: "built blocks", value: String(t.built) },
  ];
}

/** The tiles as a sentence, which is the label of the row for a screen reader. */
export function totalsText(rows: SessionRow[]): string {
  const t = totals(rows);
  return `${t.inDataset} of ${counted(t.sessions, "session")} in the dataset, ${t.reviewed} reviewed, ${t.excluded} excluded, ${counted(t.confirmed, "block")} confirmed, ` +
    `confirmed hours arena ${t.arenaHours.toFixed(2)}, track ${t.trackHours.toFixed(2)}, ${counted(t.built, "block")} built`;
}

/** Who reviewed the session and when and what the review kept, who excluded it and when, or that it is still to do. */
export function reviewText(row: SessionRow): string {
  const kept = Object.entries(row.confirmed_s).map(([kind, seconds]) => `${kind} ${(seconds / SECONDS_PER_MINUTE).toFixed(1)} min`);
  const reviewed = row.reviewed_at ? `reviewed by ${row.reviewed_by} on ${stampWithSince(row.reviewed_at)}, ${row.n_confirmed} blocks kept (${kept.join(", ")})` : "";
  const excluded = row.excluded ? `excluded by ${row.excluded_by} on ${stampWithSince(row.excluded_at)}` : "";
  return [reviewed, excluded].filter(Boolean).join(". ") || "not reviewed yet";
}
