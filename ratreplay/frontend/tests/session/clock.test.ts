import { expect, test } from "vitest";
import { Clock, REAL_TIME, SPEEDS, stepSpeed } from "../../src/session/clock";

const RATE_HZ = 60;

function playing(nFrames = 10_000): Clock {
  const clock = new Clock(nFrames, RATE_HZ);
  clock.toggle(0);
  return clock;
}

test("the speed scales the frames per second, and changing it keeps the position", () => {
  const clock = playing();
  clock.setSpeed(0.25, 0);
  clock.advance(4000);
  expect(clock.index).toBe(RATE_HZ);
  clock.setSpeed(8, 4000);
  clock.advance(5000);
  expect(clock.index).toBe(RATE_HZ + 8 * RATE_HZ);
});

test("at 1x the index follows the wall clock, a second of it being the rate in frames, not the number of ticks", () => {
  const clock = playing();
  for (const now of [16, 33, 500]) clock.advance(now);
  expect(clock.index).toBe(RATE_HZ / 2);
});

test("a paused clock does not move, a seek or a step re-anchors it", () => {
  const clock = new Clock(1000, RATE_HZ);
  expect(clock.advance(5000)).toBe(false);
  clock.toggle(5000);
  clock.seek(100, 5000);
  clock.advance(5500);
  expect(clock.index).toBe(130);
  clock.step(-10, 6000);
  expect([clock.index, clock.playing]).toEqual([120, false]);
});

test("the clock stops on the last frame and plays again from the start", () => {
  const clock = playing(100);
  clock.advance(10_000);
  expect([clock.index, clock.playing]).toEqual([99, false]);
  clock.toggle(10_000);
  expect([clock.index, clock.playing]).toEqual([0, true]);
});

test("the speed steps one up or down the list and stays on the slowest and the fastest", () => {
  expect(SPEEDS[stepSpeed(REAL_TIME, 1)]).toBeGreaterThan(1);
  expect(SPEEDS[stepSpeed(REAL_TIME, -1)]).toBeLessThan(1);
  expect(stepSpeed(0, -1)).toBe(0);
  expect(stepSpeed(SPEEDS.length - 1, 1)).toBe(SPEEDS.length - 1);
});
