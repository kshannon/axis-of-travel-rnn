import type { Counts, Kind, Source, Sources } from "../api/types";

/** The path the data takes, left to right, and the step this tool is. */
export const FLOW = ["transformed lab data", "reviewed here", "built by the processor into processed data", "made into training datasets", "stored"];
export const HERE = "reviewed here";

const NOT_SET = "not set";
const NOT_BUILT = "Not built yet. Run pixi run process-lab-data to build it, the reviews saved here go in its review folder.";

const FOLDERS: Record<Kind, { direction: string; key: string; run: string }> = {
  transformed: { direction: "incoming", key: "TRANSFORMED_LAB_DATA", run: "converter run" },
  processed: { direction: "outbound", key: "PROCESSED_LAB_DATA", run: "processor run" },
};

const COUNT_LABELS: readonly [keyof Counts, string][] = [
  ["sessions", "sessions"], ["epochs", "epochs"], ["runs", "runs"], ["frames", "frames files"], ["blocks", "blocks"], ["reviews", "reviews"],
];

export interface FolderView {
  direction: string;
  key: string;
  path: string;
  status: Source["status"];
  problems: string[];
  note: string;
  counts: { label: string; value: number }[];
  times: { label: string; stamp: string }[];
}

/** The counts the folder has, in reading order. */
export function countEntries(counts: Counts): { label: string; value: number }[] {
  return COUNT_LABELS.filter(([key]) => counts[key] !== undefined).map(([key, label]) => ({ label, value: counts[key]! }));
}

/** What a folder card shows: where the folder comes from, its state, what it holds and when its manifest says it was made. */
export function folderView(kind: Kind, source: Source): FolderView {
  const { direction, key, run } = FOLDERS[kind];
  const { manifest } = source;
  return {
    direction, key, path: source.path ?? NOT_SET, status: source.status, problems: source.problems,
    note: source.status === "ok" && !manifest ? NOT_BUILT : "",
    counts: countEntries(source.counts),
    times: manifest ? [{ label: run, stamp: manifest.timestamp }, { label: "folder last changed", stamp: manifest.modified }] : [],
  };
}

export function foldersView(sources: Sources): Record<Kind, FolderView> {
  return { transformed: folderView("transformed", sources.transformed), processed: folderView("processed", sources.processed) };
}
