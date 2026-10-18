import { expect, test } from "vitest";
import type { Folder } from "../../src/api/types";
import { folderStatus, worstStatus } from "../../src/ui/status";

const folder = (extra: Partial<Folder> = {}): Folder => ({ root: "/data", exists: true, problems: [], counts: {}, manifest: null, ...extra });

test("the worst state wins: a problem over nothing yet over ok, nothing yet when there are none", () => {
  expect(worstStatus(["ok", "nothing yet", "problem"])).toBe("problem");
  expect(worstStatus(["ok", "nothing yet"])).toBe("nothing yet");
  expect(worstStatus(["ok", "ok"])).toBe("ok");
  expect(worstStatus([])).toBe("nothing yet");
});

test("a folder is a problem with problems, nothing yet when it is set and exists but holds none, else ok", () => {
  expect(folderStatus(folder({ problems: ["x"] }), 3)).toBe("problem");
  expect(folderStatus(folder(), 0)).toBe("nothing yet");
  expect(folderStatus(folder(), undefined)).toBe("nothing yet");
  expect(folderStatus(folder(), 2)).toBe("ok");
  expect(folderStatus(folder({ exists: false }), 0)).toBe("ok");
  expect(folderStatus(folder({ root: null, exists: false }), 0)).toBe("ok");
});
