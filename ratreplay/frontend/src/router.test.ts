import { expect, test } from "vitest";
import { pageFromHash } from "./router";

const PAGE_IDS = ["data", "sessions", "replay"];

test("a hash naming a page gives that page, with or without the slash", () => {
  expect(pageFromHash("#/replay", PAGE_IDS)).toBe("replay");
  expect(pageFromHash("#sessions", PAGE_IDS)).toBe("sessions");
});

test("an empty or unknown hash gives the first page", () => {
  expect(pageFromHash("", PAGE_IDS)).toBe("data");
  expect(pageFromHash("#/nowhere", PAGE_IDS)).toBe("data");
});
