import type { ExclusionSaved } from "../api/types";

/** What the Sessions and Replay pages say of excluding a session, which is the person's decision and never a rule. */

/** The note shown when the lab's annotations mark a session excluded, which the tool shows and does not apply. */
export const ANNOTATED_NOTE = "the lab annotations mark this excluded";

/** Why Save blocks is disabled on an excluded session. */
export const EXCLUDED_SAVE = "excluded, include it first";

/** What the prompt asks before a session is excluded or included again, the answer being a short note kept in the session's notes. */
export function exclusionPrompt(sessionId: string, excluded: boolean): string {
  return excluded
    ? `Why is ${sessionId} excluded? A short note is added to the session's notes. Excluding is your decision, no rule makes it.`
    : `A short note for including ${sessionId} again, or leave it empty. The note is added to the session's notes.`;
}

export interface ExclusionToast {
  kind: "success" | "warning";
  text: string;
}

/** What the toast says of an exclusion or an inclusion: that its built blocks are gone, what is left to do, or that clearing them failed. The review file is shown apart from it. */
export function exclusionToast(sessionId: string, excluded: boolean, saved: ExclusionSaved): ExclusionToast {
  if (saved.build_error) return { kind: "warning", text: `${excluded ? "Excluded" : "Included"} ${sessionId}, but its build could not be changed: ${saved.build_error}` };
  if (excluded) return { kind: "success", text: `Excluded ${sessionId}. Its built blocks are removed.` };
  if (saved.deleted) return { kind: "success", text: `Included ${sessionId} again. Its review only recorded the exclusion, so the file is removed and the session is as before.` };
  return { kind: "success", text: `Included ${sessionId} again. Save blocks builds it, or Rebuild all.` };
}
