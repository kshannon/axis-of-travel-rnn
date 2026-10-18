import type { Counts, Folder, Health, Kind, Rebuilt, WindowSettings } from "../api/types";
import { counted, settingsText } from "../ui/text";

const NOT_SET = "not set";
const NOT_CREATED = "Does not exist yet, the first save in Replay creates it.";
const NOTHING_SAVED = "Nothing saved yet, saving blocks in Replay writes here.";
const ENVIRONMENTS_NOTE = "The repository's configs/environments, the config file does not name it.";

const FOLDERS: Record<Kind, { direction: string; key: string }> = {
  transformed: { direction: "incoming", key: "TRANSFORMED_LAB_DATA" },
  processed: { direction: "outbound", key: "PROCESSED_LAB_DATA" },
  environments: { direction: "geometry", key: "" },
};

const COUNT_LABELS: Record<Kind, readonly [keyof Counts, string][]> = {
  transformed: [["sessions", "sessions"], ["epochs", "epochs"], ["runs", "runs"], ["frames", "frames files"]],
  processed: [["reviews", "reviews"], ["blocks", "blocks"], ["sessions", "built sessions"]],
  environments: [["environments", "environments"]],
};

export interface FolderView {
  direction: string;
  key: string;
  root: string;
  status: "ok" | "problem";
  problems: string[];
  note: string;
  counts: { label: string; value: number }[];
  times: { label: string; stamp: string }[];
}

/** The counts the folder has, in reading order. */
export function countEntries(kind: Kind, counts: Counts): { label: string; value: number }[] {
  return COUNT_LABELS[kind].filter(([key]) => counts[key] !== undefined).map(([key, label]) => ({ label, value: counts[key]! }));
}

/** The note under a folder's path: what its absence or emptiness means, since the processed folder is created by the first save. */
function noteOf(kind: Kind, folder: Folder): string {
  if (kind === "environments") return ENVIRONMENTS_NOTE;
  if (kind !== "processed" || folder.problems.length) return "";
  if (!folder.exists) return NOT_CREATED;
  return folder.manifest ? "" : NOTHING_SAVED;
}

/** What a folder card shows: where the folder comes from, its state, what it holds and the times it reports. */
export function folderView(kind: Kind, folder: Folder): FolderView {
  const { direction, key } = FOLDERS[kind];
  const { manifest } = folder;
  const times: FolderView["times"] = [];
  if (manifest?.timestamp) times.push({ label: "converter run", stamp: manifest.timestamp });
  if (manifest) times.push({ label: "folder last changed", stamp: manifest.modified });
  return {
    direction, key, root: folder.root ?? NOT_SET, status: folder.problems.length ? "problem" : "ok", problems: folder.problems,
    note: noteOf(kind, folder), counts: countEntries(kind, folder.counts), times,
  };
}

export function foldersView(health: Health): Record<Kind, FolderView> {
  return {
    transformed: folderView("transformed", health.transformed),
    processed: folderView("processed", health.processed),
    environments: folderView("environments", health.environments),
  };
}

/** What the confirmation says before every reviewed session is built again: how many, at which settings, into which folder. */
export function rebuildPrompt(reviews: number, settings: WindowSettings, root: string): string {
  return `Build the blocks of ${counted(reviews, "reviewed session")} again at ${settingsText(settings)}? ` +
    `Their built blocks and metadata in ${root} are replaced, the reviews are not changed.`;
}

/** What the toast says of a rebuild: the totals, the first review skipped with its reason and the first error when a build stopped. */
export function rebuildSummary(result: Rebuilt): string {
  const { sessions, built, failed, errors, skipped } = result.totals;
  const [left] = Object.entries(result.skipped);
  const stopped = Object.entries(result.sessions).find(([, build]) => build.build_error);
  const first = (left ? `. Skipped ${left[0]}: ${left[1]}` : "") + (stopped ? `. ${stopped[0]}: ${stopped[1].build_error}` : "");
  return `Rebuilt ${counted(sessions, "session")}, ${counted(built, "block")} built, ${failed} failed, ${skipped} skipped (not in the dataset), ${counted(errors, "error")}${first}`;
}
