import type { MadeBlock, SessionHeader, SessionRow } from "../api/types";
import { cutsOf } from "../session/cuts";
import type { Fact } from "../ui/facts";
import { degrees } from "../ui/format";
import type { Column } from "../ui/table";
import { counted } from "../ui/text";
import { stampWithSince } from "../ui/time";

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const NOTES_EXCERPT = 60;
const LISTED = 6;

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

/** The reviews in all: the sessions reviewed, the blocks confirmed and the hours confirmed per epoch kind. */
export function totalsLine(rows: SessionRow[]): string {
  const seconds: Record<string, number> = {};
  for (const row of rows) for (const [kind, s] of Object.entries(row.confirmed_s)) seconds[kind] = (seconds[kind] ?? 0) + s;
  const hours = Object.keys(seconds).sort().map((kind) => `${kind} ${(seconds[kind] / SECONDS_PER_HOUR).toFixed(2)}`);
  const blocks = rows.reduce((total, row) => total + row.n_confirmed, 0);
  return `${rows.filter((row) => row.reviewed).length} of ${counted(rows.length, "session")} reviewed, ${counted(blocks, "block")} confirmed, confirmed hours: ${hours.join(", ")}`;
}

/** Who reviewed the session and when and what the review kept, who excluded it and when, or that it is still to do. */
export function reviewText(row: SessionRow): string {
  const kept = Object.entries(row.confirmed_s).map(([kind, seconds]) => `${kind} ${(seconds / SECONDS_PER_MINUTE).toFixed(1)} min`);
  const reviewed = row.reviewed_at ? `reviewed by ${row.reviewed_by} on ${stampWithSince(row.reviewed_at)}, ${row.n_confirmed} blocks kept (${kept.join(", ")})` : "";
  const excluded = row.excluded ? `excluded by ${row.excluded_by} on ${stampWithSince(row.excluded_at)}` : "";
  return [reviewed, excluded].filter(Boolean).join(". ") || "not reviewed yet";
}
