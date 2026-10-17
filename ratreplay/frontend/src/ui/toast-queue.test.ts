import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ToastQueue } from "./toast-queue";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

test("a toast fades near the end of its life and is then removed", () => {
  const queue = new ToastQueue();
  queue.push("success", "Attached");
  expect(queue.items.map((t) => [t.text, t.leaving])).toEqual([["Attached", false]]);
  vi.advanceTimersByTime(4600);
  expect(queue.items[0].leaving).toBe(true);
  vi.advanceTimersByTime(500);
  expect(queue.items).toEqual([]);
});

test("a toast can carry the path of the file a save wrote apart from its text", () => {
  const queue = new ToastQueue();
  queue.push("success", "Saved, a new file", "/a/review/S1.json");
  queue.push("warning", "Careful");
  expect(queue.items.map((t) => [t.text, t.path])).toEqual([["Saved, a new file", "/a/review/S1.json"], ["Careful", ""]]);
});

test("only the newest few stay and a toast can be dismissed by hand", () => {
  const queue = new ToastQueue();
  for (const n of [1, 2, 3, 4, 5]) queue.push("warning", `toast ${n}`);
  expect(queue.items.map((t) => t.text)).toEqual(["toast 2", "toast 3", "toast 4", "toast 5"]);
  queue.dismiss(queue.items[0].id);
  expect(queue.items).toHaveLength(3);
  vi.advanceTimersByTime(6000);
  expect(queue.items).toEqual([]);
});
