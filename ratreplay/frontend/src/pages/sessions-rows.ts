import type { SessionHeader, SessionRow } from "../api/types";
import { stampWithSince } from "../ui/time";

type Cell = string | number | null;

export interface Column {
  key: string;
  label: string;
  /** What sorting compares. */
  value: (row: SessionRow) => Cell;
  /** What the cell shows. */
  text: (row: SessionRow) => string;
  numeric?: boolean;
}

export interface Sort {
  key: string;
  descending: boolean;
}

export interface Fact {
  label: string;
  value: string;
}

const SECONDS_PER_MINUTE = 60;
const NOTES_EXCERPT = 60;
const LISTED = 6;
const NOT_AVAILABLE = "n/a";

/** Minutes of the arena, track and variant epochs, which is what the index lists of a session. */
export function minutesOf(row: SessionRow): number {
  return row.epochs.reduce((total, epoch) => total + epoch.duration_s, 0) / SECONDS_PER_MINUTE;
}

const excerpt = (notes: string) => (notes.length > NOTES_EXCERPT ? `${notes.slice(0, NOTES_EXCERPT)}...` : notes);

export const COLUMNS: readonly Column[] = [
  { key: "rat", label: "Rat", value: (r) => r.subject_id, text: (r) => r.subject_id },
  { key: "date", label: "Date", value: (r) => r.date, text: (r) => r.date },
  { key: "protocol", label: "Protocol", value: (r) => r.protocol, text: (r) => r.protocol },
  { key: "dataset", label: "In dataset", value: (r) => Number(r.in_dataset), text: (r) => (r.in_dataset ? "yes" : "no") },
  { key: "minutes", label: "Minutes", value: minutesOf, text: (r) => minutesOf(r).toFixed(1), numeric: true },
  { key: "runs", label: "Runs", value: (r) => r.n_runs, text: (r) => String(r.n_runs), numeric: true },
  { key: "automatic", label: "Automatic blocks", value: (r) => r.n_automatic, text: (r) => String(r.n_automatic ?? NOT_AVAILABLE), numeric: true },
  { key: "by", label: "Reviewed by", value: (r) => r.reviewed_by, text: (r) => r.reviewed_by ?? "" },
  { key: "at", label: "Reviewed", value: (r) => r.reviewed_at, text: (r) => stampWithSince(r.reviewed_at) },
  { key: "notes", label: "Notes", value: (r) => r.notes || null, text: (r) => excerpt(r.notes) },
];

/** The rows whose session id or rat contains the text. */
export function filterRows(rows: SessionRow[], text: string): SessionRow[] {
  const needle = text.trim().toLowerCase();
  return needle ? rows.filter((row) => `${row.session_id} ${row.subject_id}`.toLowerCase().includes(needle)) : rows;
}

function compare(a: Cell, b: Cell): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/** The rows by the sort, a missing value always last, or as the API gave them when there is no sort. */
export function sortRows(rows: SessionRow[], sort: Sort | null): SessionRow[] {
  const column = COLUMNS.find((c) => c.key === sort?.key);
  if (!sort || !column) return rows;
  const sign = sort.descending ? -1 : 1;
  return [...rows].sort((a, b) => {
    const [x, y] = [column.value(a), column.value(b)];
    if (x === null || y === null) return Number(x === null) - Number(y === null);
    return sign * compare(x, y);
  });
}

/** A click on a header: a new column sorts ascending, the same column again reverses. */
export function clickHeader(sort: Sort | null, key: string): Sort {
  return { key, descending: sort?.key === key && !sort.descending };
}

export function briefList(items: string[], limit = LISTED): string {
  return items.length <= limit ? items.join(", ") : `${items.slice(0, limit).join(", ")} and ${items.length - limit} more`;
}

const degrees = (radians: number) => `${Math.round((radians * 180) / Math.PI)} deg`;

function counted(items: string[], where: string): string {
  return items.length ? `${items.length}, ${where} ${briefList(items)}` : "none";
}

/** The facts of the details panel: those the index row has, then those the session header adds once it arrives. */
export function sessionFacts(row: SessionRow, header: SessionHeader | null): Fact[] {
  const facts = [
    { label: "group", value: row.group },
    { label: "frame rate", value: `${row.rate_hz} Hz` },
    { label: "runs", value: `${row.n_runs}, ${row.n_clean_runs} clean` },
  ];
  if (!header) return facts;
  const { pauses, jumps, gaps } = header.cuts;
  return [
    ...facts,
    { label: "frames", value: String(header.n_frames) },
    { label: "pauses", value: counted(pauses.map(String), "at frames") },
    { label: "gaps", value: counted(gaps.map(([first, last]) => `${first} to ${last}`), "frames") },
    { label: "jumps", value: counted(jumps.map(String), "at frames") },
    { label: "LED offset", value: `${degrees(header.led_offset.rad)}, concentration ${header.led_offset.r.toFixed(2)}` },
  ];
}

/** Who reviewed the session and when, and what the review kept, or that it is still to do. */
export function reviewText(row: SessionRow): string {
  if (!row.reviewed) return "not reviewed yet";
  const kept = Object.entries(row.confirmed_s).map(([kind, seconds]) => `${kind} ${(seconds / SECONDS_PER_MINUTE).toFixed(1)} min`);
  return `by ${row.reviewed_by} on ${stampWithSince(row.reviewed_at)}, ${row.n_confirmed} blocks kept (${kept.join(", ")})`;
}
