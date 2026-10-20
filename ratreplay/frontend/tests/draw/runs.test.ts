import { expect, test } from "vitest";
import type { Run } from "../../src/api/types";
import { LAB_PATHS, pathsOf, runFill, runText } from "../../src/draw/runs";

const run = (number: number, path_id: number, clean: boolean) => ({ run: number, path_id, clean, epoch: "track", frame_start: 1, frame_end: 10 }) as Run;

test("a run is coloured by its path: the outbound runs, the return runs and any other path each have their own", () => {
  expect([1, 4, 9, 10, 5].map((path) => runFill(path, LAB_PATHS))).toEqual(["accent", "accent", "soft", "soft", "neutral"]);
});

test("a run says which path it ran, whether the lab called it clean and whether it is flagged", () => {
  expect(runText(run(12, 1, true), LAB_PATHS)).toBe("run 12, outbound path 1, clean");
  expect(runText(run(23, 9, false), LAB_PATHS, true)).toBe("run 23, return path 9, not clean by the lab, flagged");
  expect(runText(run(14, 5, true), LAB_PATHS)).toBe("run 14, path 5, clean");
});

test("the paths are those of the rules the session was cut under, not fixed ones", () => {
  const paths = pathsOf({ rules: { outbound_paths: [5], return_paths: [1] } } as never);
  expect(runText(run(12, 1, true), paths)).toBe("run 12, return path 1, clean");
  expect(runText(run(14, 5, true), paths)).toBe("run 14, outbound path 5, clean");
  expect(runFill(5, paths)).toBe("accent");
});
