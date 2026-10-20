import { expect, test } from "vitest";
import { clickHeader, sortRows } from "../../src/ui/table";
import type { Column } from "../../src/ui/table";

interface Row {
  rat: string;
  runs: number;
  at: string | null;
}

const COLUMNS: Column<Row>[] = [
  { key: "rat", label: "Rat", value: (r) => r.rat, text: (r) => r.rat },
  { key: "runs", label: "Runs", value: (r) => r.runs, text: (r) => String(r.runs), numeric: true },
  { key: "at", label: "Reviewed", value: (r) => r.at, text: (r) => r.at ?? "" },
];

const ROWS: Row[] = [
  { rat: "NS14", runs: 4, at: "2026-10-16" },
  { rat: "NS5", runs: 10, at: null },
  { rat: "NS16", runs: 7, at: "2026-10-15" },
];
const rats = (rows: Row[]) => rows.map((r) => r.rat);

test("a number sorts as a number and a name as a name with its digits in order", () => {
  expect(rats(sortRows(ROWS, COLUMNS, { key: "runs", descending: false }))).toEqual(["NS14", "NS16", "NS5"]);
  expect(rats(sortRows(ROWS, COLUMNS, { key: "rat", descending: false }))).toEqual(["NS5", "NS14", "NS16"]);
});

test("a missing value goes last whichever way the sort runs", () => {
  expect(rats(sortRows(ROWS, COLUMNS, { key: "at", descending: false }))).toEqual(["NS16", "NS14", "NS5"]);
  expect(rats(sortRows(ROWS, COLUMNS, { key: "at", descending: true }))).toEqual(["NS14", "NS16", "NS5"]);
});

test("a header click sorts ascending first and reverses on the second click", () => {
  const first = clickHeader(null, "runs");
  expect(first).toEqual({ key: "runs", descending: false });
  expect(clickHeader(first, "runs")).toEqual({ key: "runs", descending: true });
  expect(clickHeader({ key: "runs", descending: true }, "rat")).toEqual({ key: "rat", descending: false });
});
