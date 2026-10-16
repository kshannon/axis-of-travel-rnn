import { expect, test } from "vitest";
import { timeSince } from "./time";

const NOW = Date.parse("2026-10-16T12:00:00+00:00");

test("the time since is in days, hours or minutes, whichever is the largest that fits", () => {
  expect(timeSince("2026-10-13T12:00:00+00:00", NOW)).toBe("3 d ago");
  expect(timeSince("2026-10-16T09:30:00+00:00", NOW)).toBe("2 h ago");
  expect(timeSince("2026-10-16T11:15:00+00:00", NOW)).toBe("45 min ago");
});

test("under a minute is just now", () => {
  expect(timeSince("2026-10-16T11:59:30+00:00", NOW)).toBe("just now");
});
