import { expect, test } from "vitest";
import { belongsToTarget, commandOf } from "../../src/ui/keys";

const press = (key: string, extra = {}) => commandOf({ key, shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, ...extra });

test("the essential keys map to their commands and nothing else does", () => {
  expect(["z", " ", "ArrowLeft", "ArrowRight", "[", "]", "Enter", "Escape"].map((key) => press(key))).toEqual([
    "undo", "play", "back", "forward", "previous-run", "next-run", "confirm", "clear",
  ]);
  for (const key of ["a", "i", "o", "n", "d", "s", "f", ",", ".", "{", "}", "Tab"]) expect(press(key)).toBeNull();
});

test("shift makes a left or right a second, and means nothing else", () => {
  expect(press("ArrowLeft", { shiftKey: true })).toBe("back-second");
  expect(press("ArrowRight", { shiftKey: true })).toBe("forward-second");
  expect(press("z", { shiftKey: true })).toBe("undo");
});

test("a browser shortcut is left alone", () => {
  expect(press("z", { metaKey: true })).toBeNull();
  expect(press("ArrowLeft", { altKey: true })).toBeNull();
  expect(press("[", { ctrlKey: true })).toBeNull();
});

test("typing in a field and activating a button keep their keys", () => {
  expect(belongsToTarget({ key: "z", target: { tagName: "TEXTAREA" } })).toBe(true);
  expect(belongsToTarget({ key: " ", target: { tagName: "BUTTON" } })).toBe(true);
  expect(belongsToTarget({ key: "Enter", target: { tagName: "A" } })).toBe(true);
  expect(belongsToTarget({ key: "ArrowLeft", target: { tagName: "BUTTON" } })).toBe(false);
  expect(belongsToTarget({ key: " ", target: { tagName: "BODY" } })).toBe(false);
  expect(belongsToTarget({ key: " ", target: null })).toBe(false);
});
