import { expect, test } from "vitest";
import type { Folder, Health } from "../api/types";
import { problemWith } from "./problem";

const OK: Folder = { root: "/data/t", exists: true, problems: [], counts: {}, manifest: null };
const NOT_SET: Folder = { root: null, exists: false, problems: ["TRANSFORMED_LAB_DATA is not set in configs/local.yaml"], counts: {}, manifest: null };
const NOT_CREATED: Folder = { root: "/data/p", exists: false, problems: [], counts: {}, manifest: null };
const health = (transformed: Folder, processed: Folder, environments: Folder = OK): Health => (
  { transformed, processed, environments, config_path: "configs/local.yaml" }
);

test("a page waits for the folders to be read", () => {
  expect(problemWith(null, ["processed"])).toBe("Reading the data folders.");
});

test("a page that needs a folder says what is wrong with it and ignores the one it does not need", () => {
  expect(problemWith(health(NOT_SET, OK), ["transformed", "processed"])).toBe(
    "The transformed lab data cannot be used: TRANSFORMED_LAB_DATA is not set in configs/local.yaml",
  );
  expect(problemWith(health(NOT_SET, OK), ["processed"])).toBe("");
  expect(problemWith(health(OK, OK), ["transformed", "processed", "environments"])).toBe("");
});

test("the environments folder is one of the three", () => {
  const broken = { ...OK, exists: false, problems: ["/repo/configs/environments does not exist"] };
  expect(problemWith(health(OK, OK, broken), ["environments"])).toBe("The environments cannot be used: /repo/configs/environments does not exist");
});

test("a processed folder that is not created yet is usable, the first save creates it", () => {
  expect(problemWith(health(OK, NOT_CREATED), ["transformed", "processed"])).toBe("");
});
