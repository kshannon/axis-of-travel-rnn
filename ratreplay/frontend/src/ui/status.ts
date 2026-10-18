import type { Folder } from "../api/types";

export type Status = "ok" | "problem" | "nothing yet";

/** The worst of the states, a problem over nothing yet over ok, and nothing yet when there are none. */
export function worstStatus(states: readonly Status[]): Status {
  if (states.includes("problem")) return "problem";
  return states.includes("nothing yet") || !states.length ? "nothing yet" : "ok";
}

/** A folder's state: a problem when it has any, nothing yet when its path is set and exists but `held` (what it should hold, counted) is none, else ok. */
export function folderStatus(folder: Folder, held: number | undefined): Status {
  if (folder.problems.length) return "problem";
  return folder.root && folder.exists && !held ? "nothing yet" : "ok";
}

// What each state looks like: its word and its solid dot in its colour, and the left edge of the card that owns it. A
// state the page does not name reads as nothing yet.
const STATES: Record<Status, { text: string; dot: string; edge: string }> = {
  ok: { text: "text-ok", dot: "bg-ok", edge: "border-l-4 border-l-ok" },
  problem: { text: "text-bad", dot: "bg-bad", edge: "border-l-4 border-l-bad" },
  "nothing yet": { text: "text-muted", dot: "bg-muted", edge: "border-l-4 border-l-muted" },
};

/** An Alpine expression that gives the classes of one part of the state, `status` being an Alpine expression that gives a state. */
function classesOf(status: string, part: "text" | "dot" | "edge"): string {
  const cases = Object.entries(STATES).map(([state, classes]) => `'${state}': '${classes[part]}'`);
  return `({ ${cases.join(", ")} })[${status}] ?? '${STATES["nothing yet"][part]}'`;
}

/** A solid 12 px dot and the word beside it in the same colour, bold and on the text baseline, `status` being an Alpine expression that gives "ok", "problem" or "nothing yet". */
export function statusMark(status: string): string {
  return `
    <span class="inline-flex shrink-0 items-baseline gap-2 text-sm font-semibold" :class="${classesOf(status, "text")}">
      <span class="size-3 shrink-0 rounded-full" :class="${classesOf(status, "dot")}"></span>
      <span x-text="${status}"></span>
    </span>`;
}

/** The Alpine expression for the class of the card that owns the state: a left edge in the colour of the mark. A card puts it in its `:class`. */
export function statusEdge(status: string): string {
  return classesOf(status, "edge");
}
