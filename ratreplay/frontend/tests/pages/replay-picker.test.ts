import { expect, test } from "vitest";
import type { SessionRow } from "../../src/api/types";
import { filterRows } from "../../src/pages/incoming-view";
import { chipsOf, leaveQuestion, neighbours, pickerOrder, stepReason } from "../../src/pages/replay-picker";

const row = (session_id: string, extra: Partial<SessionRow> = {}) =>
  ({ session_id, subject_id: session_id.slice(0, 4), in_dataset: true, reason: null, reviewed: false, excluded: false, ...extra }) as SessionRow;

// The index as the API sends it: the dataset first, then the sessions still to review before the reviewed ones.
const index = [row("NS16_rec6"), row("NS14_rec1", { reviewed: true }), row("NS14_rec2"), row("NS14_rec10"), row("NS5_rec1", { in_dataset: false, reason: "no frames" })];

test("the arrows' order is the dataset first and each group by session id, whether or not a session is reviewed", () => {
  const ids = (rows: SessionRow[]) => rows.map((r) => r.session_id);
  expect(ids(pickerOrder(index))).toEqual(["NS14_rec1", "NS14_rec2", "NS14_rec10", "NS16_rec6", "NS5_rec1"]);
  const saved = index.map((r) => (r.session_id === "NS14_rec2" ? { ...r, reviewed: true } : r));
  expect(ids(pickerOrder(saved))).toEqual(ids(pickerOrder(index)));
});

test("the neighbours of a session in a list are none at an end and none when it is not listed, and the filter narrows the list they are taken from", () => {
  const ordered = pickerOrder(index);
  expect(neighbours(ordered, "NS14_rec2")).toMatchObject({ previous: { session_id: "NS14_rec1" }, next: { session_id: "NS14_rec10" }, listed: true });
  expect(neighbours(ordered, "NS14_rec1").previous).toBeNull();
  expect(neighbours(ordered, "NS5_rec1").next).toBeNull();
  expect(neighbours(ordered, "elsewhere")).toEqual({ previous: null, next: null, listed: false });
  const ns14 = filterRows(ordered, "ns14");
  expect(neighbours(ns14, "NS14_rec10").next).toBeNull();
  expect(neighbours(ns14, "NS16_rec6").listed).toBe(false);
});

test("an arrow that cannot step says why, naming the list it walks", () => {
  const ordered = pickerOrder(index);
  expect(stepReason(ordered, "NS14_rec2", "previous", false)).toBe("");
  expect(stepReason(ordered, "NS14_rec1", "previous", false)).toBe("NS14_rec1 is the first session of the index");
  expect(stepReason(filterRows(ordered, "ns14"), "NS14_rec10", "next", true)).toBe("NS14_rec10 is the last session of the filtered list");
  expect(stepReason(filterRows(ordered, "ns14"), "NS16_rec6", "next", true)).toBe("NS16_rec6 is not in the filtered list");
});

test("a row is marked open, reviewed, excluded and not in the dataset, and leaving unsaved edits asks with their count", () => {
  const texts = (r: SessionRow, open = "") => chipsOf(r, open).map((c) => c.text);
  expect(texts(row("A", { reviewed: true, excluded: true }), "A")).toEqual(["open", "reviewed", "excluded"]);
  expect(chipsOf(row("B", { in_dataset: false, reason: "no frames" }), "A")).toMatchObject([{ text: "not in the dataset", title: "no frames" }]);
  expect(leaveQuestion("NS14_rec1", 1)).toBe("NS14_rec1 has 1 edit not saved. Leave it and lose them?");
  expect(leaveQuestion("NS14_rec1", 0)).toContain("edits cleared and not saved");
});
