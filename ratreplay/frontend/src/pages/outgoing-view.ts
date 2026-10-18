import type { FormatGroup } from "../api/describe";
import type { BuiltSession, Folder, Readiness, Rebuilt, SessionRow, WindowSettings } from "../api/types";
import type { Column } from "../ui/table";
import { counted, settingsText } from "../ui/text";
import { stampWithSince } from "../ui/time";
import { compareSettings, settingsLine } from "./settings-view";
import type { SettingRow } from "./settings-view";

const NOT_SET = "not set";
const NOT_CREATED = "Does not exist yet, the first save in Replay creates it.";
const NOTHING_SAVED = "Nothing saved yet, saving blocks in Replay writes here.";
const PROCESSED_FORMATS = ["Processed folder", "Review file"];
const NOT_BUILT = "not built yet";

/** What the card of the write path shows: where blocks are written, its state, what it holds and when it last changed. */
export interface WriteView {
  root: string;
  status: "ok" | "problem";
  problems: string[];
  note: string;
  counts: { label: string; value: number }[];
  times: { label: string; stamp: string }[];
}

/** The note under the path: what its absence or emptiness means, since the first save creates the folder. */
function noteOf(folder: Folder): string {
  if (folder.problems.length) return "";
  if (!folder.exists) return NOT_CREATED;
  return folder.manifest ? "" : NOTHING_SAVED;
}

/** The processed folder as the Outgoing page shows it. */
export function writeView(folder: Folder): WriteView {
  const { reviews, blocks, sessions } = folder.counts;
  const counts = [["reviews", reviews], ["blocks", blocks], ["built sessions", sessions]] as const;
  return {
    root: folder.root ?? NOT_SET, status: folder.problems.length ? "problem" : "ok", problems: folder.problems, note: noteOf(folder),
    counts: counts.flatMap(([label, value]) => (value === undefined ? [] : [{ label, value }])),
    times: folder.manifest ? [{ label: "folder last changed", stamp: folder.manifest.modified }] : [],
  };
}

/** The tables of the processed files out of the format's groups. */
export function outgoingGroups(groups: FormatGroup[]): FormatGroup[] {
  return groups.filter((group) => PROCESSED_FORMATS.includes(group.title));
}

/** What the confirmation says before every reviewed session is built again: how many, at which settings, into which folder. */
export function rebuildPrompt(reviews: number, settings: WindowSettings, root: string): string {
  return `Build the blocks of ${counted(reviews, "reviewed session")} again at ${settingsText(settings)}? ` +
    `Their built blocks and metadata in ${root} are replaced, the reviews are not changed.`;
}

/** What the toast says of a rebuild: the totals, the first review skipped with its reason, the first session you excluded with its note and the first error when a build stopped. */
export function rebuildSummary(result: Rebuilt): string {
  const { sessions, built, failed, errors, skipped, excluded } = result.totals;
  const [out] = Object.entries(result.skipped);
  const [left] = Object.entries(result.excluded);
  const stopped = Object.entries(result.sessions).find(([, build]) => build.build_error);
  const note = left?.[1].trim().replace(/\s*\n\s*/g, ", ");
  const first = (out ? `. Skipped ${out[0]}: ${out[1]}` : "") + (left ? `. Excluded ${left[0]}${note ? `: ${note}` : ""}` : "") +
    (stopped ? `. ${stopped[0]}: ${stopped[1].build_error}` : "");
  return `Rebuilt ${counted(sessions, "session")}, ${counted(built, "block")} built, ${failed} failed, ${skipped} skipped (not in the dataset), ` +
    `${excluded} excluded by you, ${counted(errors, "error")}${first}`;
}

/** A row of the table of what is built: a session with a build, or a reviewed session that has none. */
export interface OutRow {
  session_id: string;
  blocks: number;
  failed: BuiltSession["failed"];
  excluded: boolean;
  /** The settings the session was built with, none when nothing is built for it. */
  settings: WindowSettings | null;
  built_at: string | null;
  /** Why a reviewed session has no build, blank for a built one. */
  waiting: string;
  /** The settings in use beside the ones the session was built with, empty when nothing is built. */
  compare: SettingRow[];
}

/** Every built session with its blocks, then each reviewed session that is not built with why, in session order. The sessions the readiness answer has and the index's excluded flag come together here. */
export function outRows({ blocks, built, settings }: Readiness, sessions: SessionRow[]): OutRow[] {
  const index = new Map(sessions.map((row) => [row.session_id, row]));
  const counts = new Map<string, number>();
  for (const { session_id } of blocks) counts.set(session_id, (counts.get(session_id) ?? 0) + 1);
  const made: OutRow[] = Object.entries(built).map(([sid, build]) => ({
    session_id: sid, blocks: counts.get(sid) ?? 0, failed: build.failed, excluded: build.excluded || index.get(sid)?.excluded === true,
    settings: build.settings, built_at: build.built_at, waiting: "", compare: compareSettings(settings, build.settings),
  }));
  const waiting: OutRow[] = sessions.filter((row) => row.reviewed && !(row.session_id in built)).map((row) => ({
    session_id: row.session_id, blocks: 0, failed: [], excluded: row.excluded, settings: null, built_at: null, compare: [],
    waiting: row.in_dataset || row.excluded ? NOT_BUILT : `skipped, not in the dataset: ${row.reason}`,
  }));
  return [...made, ...waiting].sort((a, b) => a.session_id.localeCompare(b.session_id));
}

/** Whether the session was built at other settings than the ones in use. */
export const builtElsewhere = (row: OutRow): boolean => row.compare.some((setting) => setting.differs);

const builtWith = (row: OutRow) => (row.settings ? settingsLine(row.settings) : row.waiting);

export const COLUMNS: readonly Column<OutRow>[] = [
  { key: "session", label: "Session", value: (r) => r.session_id, text: (r) => r.session_id },
  { key: "blocks", label: "Blocks built", value: (r) => r.blocks, text: (r) => String(r.blocks), numeric: true },
  { key: "failed", label: "Failed", value: (r) => r.failed.length, text: (r) => String(r.failed.length), numeric: true, tone: (r) => (r.failed.length ? "text-bad" : "text-muted") },
  { key: "excluded", label: "Excluded", value: (r) => Number(r.excluded), text: (r) => (r.excluded ? "yes" : "") },
  { key: "settings", label: "Built with", value: builtWith, text: builtWith, tone: (r) => (builtElsewhere(r) ? "text-warn" : r.settings ? "" : "text-muted") },
  { key: "at", label: "Built at", value: (r) => r.built_at, text: (r) => stampWithSince(r.built_at) },
];

/** The failed blocks of a row, each with its problems in one line. */
export function failedLines(row: OutRow): string[] {
  return row.failed.map(({ block_id, problems }) => `${block_id}: ${problems.join(", ")}`);
}

/** The line under an open row: what is wrong or missing in it, or that nothing is. */
export function rowNote(row: OutRow): string {
  if (row.waiting) return row.waiting;
  if (row.failed.length) return `${counted(row.failed.length, "block")} failed and ${row.failed.length === 1 ? "was" : "were"} not written`;
  return row.excluded ? "Built excluded, no block is written for it." : "Every block was written.";
}
