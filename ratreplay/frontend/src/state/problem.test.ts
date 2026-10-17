import { expect, test } from "vitest";
import type { Source, Sources } from "../api/types";
import { problemWith } from "./problem";

const OK: Source = { path: "/data/t", status: "ok", problems: [], counts: {}, manifest: null };
const BAD: Source = { path: null, status: "invalid", problems: ["TRANSFORMED_LAB_DATA is not set in configs/local.yaml"], counts: {}, manifest: null };
const sources = (transformed: Source, processed: Source): Sources => ({ transformed, processed, config_path: "configs/local.yaml" });

test("a page waits for the folders to be read", () => {
  expect(problemWith(null, ["processed"])).toBe("Reading the data folders.");
});

test("a page that needs a folder says what is wrong with it and ignores the one it does not need", () => {
  expect(problemWith(sources(BAD, OK), ["transformed", "processed"])).toBe(
    "The transformed lab data cannot be used: TRANSFORMED_LAB_DATA is not set in configs/local.yaml",
  );
  expect(problemWith(sources(BAD, OK), ["processed"])).toBe("");
  expect(problemWith(sources(OK, OK), ["transformed", "processed"])).toBe("");
});
