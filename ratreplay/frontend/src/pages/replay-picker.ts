import type { SessionRow } from "../api/types";
import { CHIP_ACCENT, CHIP_MUTED, CHIP_OK, CHIP_WARN } from "../ui/style";
import { sortRows } from "../ui/table";
import type { Column } from "../ui/table";
import { counted } from "../ui/text";
import { COLUMNS } from "./incoming-view";
import type { Chip } from "./replay-view";

export type Step = "previous" | "next";

const BY_ID: readonly Column<SessionRow>[] = [{ key: "id", label: "Session", value: (r) => r.session_id, text: (r) => r.session_id }];

/**
 * The sessions in the order the arrows walk them: the dataset first, each group by session id. The index itself puts the
 * reviewed sessions last, which would move a session under the arrows the moment it is saved.
 */
export function pickerOrder(rows: SessionRow[]): SessionRow[] {
  return sortRows(sortRows(rows, BY_ID, { key: "id", descending: false }), COLUMNS, { key: "dataset", descending: true });
}

/** The sessions before and after one in a list, none at an end, and whether the session is in the list at all. */
export function neighbours(list: readonly SessionRow[], sessionId: string): Record<Step, SessionRow | null> & { listed: boolean } {
  const at = list.findIndex((row) => row.session_id === sessionId);
  if (at < 0) return { previous: null, next: null, listed: false };
  return { previous: list[at - 1] ?? null, next: list[at + 1] ?? null, listed: true };
}

/** Why an arrow cannot step from the session, none when it can. `filtered` says the list is the typed filter's matches and not the whole index. */
export function stepReason(list: readonly SessionRow[], sessionId: string, step: Step, filtered: boolean): string {
  const where = filtered ? "the filtered list" : "the index";
  const found = neighbours(list, sessionId);
  if (!found.listed) return `${sessionId} is not in ${where}`;
  return found[step] ? "" : `${sessionId} is the ${step === "previous" ? "first" : "last"} session of ${where}`;
}

/** The marks of a row of the list: the session open, reviewed, excluded and left out of the dataset. */
export function chipsOf(row: SessionRow, openId: string): Chip[] {
  const chips: Chip[] = [];
  if (row.session_id === openId) chips.push({ text: "open", chip: CHIP_ACCENT, title: "the session open in the replay" });
  if (row.reviewed) chips.push({ text: "reviewed", chip: CHIP_OK, title: "a person has looked at this session" });
  if (row.excluded) chips.push({ text: "excluded", chip: CHIP_MUTED, title: "excluded in its review" });
  if (!row.in_dataset) chips.push({ text: "not in the dataset", chip: CHIP_WARN, title: row.reason ?? "" });
  return chips;
}

/** The question before leaving a session whose edits are not saved. */
export function leaveQuestion(sessionId: string, edits: number): string {
  const lost = edits ? `${counted(edits, "edit")} not saved` : "its edits cleared and not saved";
  return `${sessionId} has ${lost}. Leave it and lose them?`;
}
