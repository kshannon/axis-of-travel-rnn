import type { Run, SessionHeader } from "../api/types";

/** The lab's path ids of the outbound runs and of the return runs. A session holds them in its rules. */
export interface RunPaths {
  outbound_paths: number[];
  return_paths: number[];
}

/** The engine's own paths, for a page whose header holds no rules, the Blocks page. */
export const LAB_PATHS: RunPaths = { outbound_paths: [1, 2, 3, 4], return_paths: [9, 10] };

// Palette colours: the blue and its paler shade, and the grey for any other path.
const RUN_COLOURS = { outbound: "accent", return: "soft", other: "neutral" };

/** The paths of the rules a session was cut under. The header carries every rule, SessionRules types only those the page reads, so the paths are read through one cast. */
export const pathsOf = (header: Pick<SessionHeader, "rules">): RunPaths => header.rules as unknown as RunPaths;

export function runKind(pathId: number, paths: RunPaths): "outbound" | "return" | "other" {
  if (paths.outbound_paths.includes(pathId)) return "outbound";
  return paths.return_paths.includes(pathId) ? "return" : "other";
}

/** The palette colour of a run's bar by its path. */
export const runFill = (pathId: number, paths: RunPaths): string => RUN_COLOURS[runKind(pathId, paths)];

/** A run's path in words: "outbound path 1", "return path 9", or just "path 5" for a path that is neither. */
export function pathText(pathId: number, paths: RunPaths): string {
  const kind = runKind(pathId, paths);
  return `${kind === "other" ? "" : `${kind} `}path ${pathId}`;
}

/** Whether the lab called the run clean, in the words every page uses. */
export const cleanText = (run: Pick<Run, "clean">): string => (run.clean ? "clean" : "not clean by the lab");

/** The run in words, such as "run 12, outbound path 1, clean" or "run 23, return path 9, not clean by the lab, flagged". */
export function runText(run: Run, paths: RunPaths, flagged = false): string {
  return `run ${run.run}, ${pathText(run.path_id, paths)}, ${cleanText(run)}${flagged ? ", flagged" : ""}`;
}
