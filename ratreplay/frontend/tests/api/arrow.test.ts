import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { decodeColumns } from "../../src/api/arrow";

// Written by fixtures/make_columns.py with the backend's encoder.
const bytes = readFileSync(new URL("../fixtures/columns.arrow", import.meta.url));
const columns = decodeColumns(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));

test("each column comes back in its own typed array, a bool as 0 and 1", () => {
  expect(columns.x).toBeInstanceOf(Float64Array);
  expect(columns.n_lights).toBeInstanceOf(Int8Array);
  expect(columns.frame).toBeInstanceOf(Int32Array);
  expect(columns.filled).toBeInstanceOf(Uint8Array);
  expect(Array.from(columns.filled)).toEqual([1, 0, 1]);
  expect(Array.from(columns.n_lights)).toEqual([2, 1, 0]);
});

test("NaN stays NaN", () => {
  expect(columns.x[0]).toBe(1.5);
  expect(columns.x[1]).toBeNaN();
});
