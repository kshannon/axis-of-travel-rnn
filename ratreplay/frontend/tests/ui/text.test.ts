import { expect, test } from "vitest";
import { counted } from "../../src/ui/text";

test("a noun is plural unless there is exactly one", () => {
  expect([0, 1, 2].map((n) => counted(n, "edit"))).toEqual(["0 edits", "1 edit", "2 edits"]);
});
