import { expect, test } from "vitest";
import { pageFromHash } from "../src/router";

const PAGE_IDS = ["incoming", "settings", "replay"];

test("a hash naming a page gives that page, with or without the slash, and an empty or unknown hash gives the first page", () => {
  expect(pageFromHash("#/replay", PAGE_IDS)).toBe("replay");
  expect(pageFromHash("#settings", PAGE_IDS)).toBe("settings");
  expect(pageFromHash("", PAGE_IDS)).toBe("incoming");
  expect(pageFromHash("#/nowhere", PAGE_IDS)).toBe("incoming");
});

test("the hash of a page that was replaced, data or sessions, gives Incoming", () => {
  expect(pageFromHash("#/data", PAGE_IDS)).toBe("incoming");
  expect(pageFromHash("#/sessions", PAGE_IDS)).toBe("incoming");
});
