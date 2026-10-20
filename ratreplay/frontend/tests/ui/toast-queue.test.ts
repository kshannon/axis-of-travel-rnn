import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ToastQueue } from "../../src/ui/toast-queue";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

test("a success fades near the end of its life and is then removed", () => {
  const queue = new ToastQueue();
  queue.push("success", "Attached");
  expect(queue.items.map((t) => [t.text, t.leaving])).toEqual([["Attached", false]]);
  vi.advanceTimersByTime(4600);
  expect(queue.items[0].leaving).toBe(true);
  vi.advanceTimersByTime(500);
  expect(queue.items).toEqual([]);
});

test("only the newest few successes stay and a success can be dismissed by hand", () => {
  const queue = new ToastQueue();
  for (const n of [1, 2, 3, 4, 5]) queue.push("success", `toast ${n}`);
  expect(queue.items.map((t) => t.text)).toEqual(["toast 2", "toast 3", "toast 4", "toast 5"]);
  queue.dismiss(queue.items[0].id);
  expect(queue.items).toHaveLength(3);
  vi.advanceTimersByTime(6000);
  expect(queue.items).toEqual([]);
});

test("warnings and errors are held newest first, with the time they happened, until each is closed by hand", () => {
  vi.setSystemTime(new Date(2026, 9, 18, 14, 5, 9));
  const queue = new ToastQueue();
  queue.push("error", "the API said no");
  vi.setSystemTime(new Date(2026, 9, 18, 14, 7, 30));
  queue.push("warning", "a kept block must last 10 s or more");
  queue.push("success", "Saved");
  expect(queue.problems.map((t) => [t.kind, t.text, t.time])).toEqual([["warning", "a kept block must last 10 s or more", "14:07:30"], ["error", "the API said no", "14:05:09"]]);
  vi.advanceTimersByTime(60 * 60 * 1000); // an hour later the success is long gone and the problems are still there
  expect(queue.items).toEqual([]);
  expect(queue.problems).toHaveLength(2);
  for (let n = 0; n < 10; n++) queue.push("error", `error ${n}`);
  expect(queue.problems).toHaveLength(12);
  queue.dismiss(queue.problems[0].id);
  expect(queue.problems.map((t) => t.text)).not.toContain("error 9");
  expect(queue.problems).toHaveLength(11);
});
