import { expect, test } from "vitest";
import { endpoints, formatGroups } from "../../src/api/describe";
import type { FormatContract, OpenApiDocument } from "../../src/api/types";

const DOCUMENT: OpenApiDocument = {
  info: { title: "RatReplay", version: "0.1.0" },
  paths: {
    "/api/sources": {
      get: { summary: "List Sources", responses: { "200": { description: "Successful Response", content: { "application/json": { schema: {} } } } } },
      post: {
        summary: "Attach Source",
        requestBody: { content: { "application/json": { schema: { $ref: "#/components/schemas/AttachBody" } } } },
        responses: { "200": { description: "Successful Response" } },
      },
    },
    "/api/sources/{sid}": {
      delete: {
        parameters: [{ name: "sid", in: "path", required: true, schema: { type: "string" } }],
        responses: { "200": { description: "Successful Response" } },
      },
    },
  },
  components: {
    schemas: {
      AttachBody: {
        required: ["path", "kind"],
        properties: {
          path: { type: "string" },
          kind: { type: "string", enum: ["transformed", "processed"] },
          processed_path: { anyOf: [{ type: "string" }, { type: "null" }] },
        },
      },
    },
  },
};

test("a request body is listed by the fields of the schema it references", () => {
  const body = endpoints(DOCUMENT)[1].tables.find((table) => table.title === "Request body, AttachBody")!;
  expect(body.rows).toEqual([
    ["path", "string", "required"],
    ["kind", '"transformed" or "processed"', "required"],
    ["processed_path", "string or null", "optional"],
  ]);
});

test("the contract gives one table per file, marking the columns the tool reads, and the review file's vocabulary", () => {
  const contract = {
    transformed: { files: [{ path: "runs.csv", optional: false, columns: [{ name: "run", type: "int64", required: true }, { name: "notes", type: "string", required: false }] }] },
    processed: {
      files: [
        { path: "windows.json", optional: true, keys: ["settings", "totals"] },
        { path: "review/<session_id>.json", optional: true, keys: ["session_id"], block_keys: ["block_id"], statuses: ["auto"], edits: { move: ["frame", "edge", "at"] } },
      ],
    },
    synthetic: { files: [{ path: "sets/<set_id>/provenance.json", optional: false, keys: ["set_id", "seed"] }] },
    settings: { window_s: 40 },
  } as unknown as FormatContract;
  const [transformed, processed, review, synthetic, settings] = formatGroups(contract);
  expect(synthetic.tables.map((table) => table.title)).toEqual(["sets/<set_id>/provenance.json"]);
  expect(transformed.tables[0].rows).toEqual([["run", "int64", "used by RatReplay"], ["notes", "string", ""]]);
  expect(processed.tables.map((table) => table.title)).toEqual(["windows.json (optional)", "review/<session_id>.json (optional)"]);
  expect(processed.tables[0].rows).toEqual([["settings"], ["totals"]]);
  expect(review.tables[2].rows).toEqual([["move", "frame, edge, at"]]);
  expect(settings.tables[0].rows).toEqual([["window_s", "40"]]);
});
