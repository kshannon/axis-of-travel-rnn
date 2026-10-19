import { expect, test } from "vitest";
import { pageFromHash, Visit } from "../src/router";

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

// A page as the shell runs it: init when it is shown, destroy when it is left, and a load that reports its failure through the visit.
function fakePage(load: () => Promise<void>, reported: string[]) {
  const visit = new Visit();
  return {
    async init() {
      try {
        await load();
      } catch (error) {
        visit.say(() => reported.push(String(error)));
      }
    },
    destroy: () => visit.hide(),
  };
}

test("a failing load is reported while its page is shown", async () => {
  const reported: string[] = [];
  const page = fakePage(() => Promise.reject("could not load"), reported);
  await page.init();
  expect(reported).toEqual(["could not load"]);
});

test("a load that fails after its page was left reports nothing, so no error lands on the page shown by then", async () => {
  const reported: string[] = [];
  let fail!: (reason: string) => void;
  const page = fakePage(() => new Promise<void>((_, reject) => (fail = reject)), reported);
  const loading = page.init();
  page.destroy();
  fail("could not load");
  await loading;
  expect(reported).toEqual([]);
});
