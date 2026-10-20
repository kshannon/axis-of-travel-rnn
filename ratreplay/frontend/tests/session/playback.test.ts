import { expect, test } from "vitest";
import { Clock } from "../../src/session/clock";
import { movePlayback } from "../../src/session/playback";

const RATE_HZ = 60;
const RUN_STARTS = [2200, 2400, 2600];

function clockAt(frame: number): Clock {
  const clock = new Clock(5400, RATE_HZ);
  clock.seek(frame - 1, 0);
  return clock;
}

test("the run keys go to the start of the previous or next run and stay put when there is none", () => {
  const clock = clockAt(2300);
  movePlayback("next-run", clock, RUN_STARTS, 0);
  expect(clock.index + 1).toBe(2400);
  movePlayback("previous-run", clock, RUN_STARTS, 0);
  expect(clock.index + 1).toBe(2200);
  movePlayback("previous-run", clock, RUN_STARTS, 0);
  expect(clock.index + 1).toBe(2200);
  clock.seek(2699, 0);
  clock.toggle(0);
  movePlayback("next-run", clock, RUN_STARTS, 0);
  expect([clock.index + 1, clock.playing]).toEqual([2700, true]);
});

test("a frame or a second moves the clock and a key that is not playback is left to the page", () => {
  const clock = clockAt(100);
  expect(movePlayback("forward", clock, [], 0)).toBe(true);
  expect(clock.index + 1).toBe(101);
  expect(movePlayback("back-second", clock, [], 0)).toBe(true);
  expect(clock.index + 1).toBe(41);
  expect(movePlayback("confirm", clock, [], 0)).toBe(false);
  expect(movePlayback("undo", clock, [], 0)).toBe(false);
  expect(clock.index + 1).toBe(41);
});
