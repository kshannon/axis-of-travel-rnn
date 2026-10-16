import { expect, test } from "vitest";
import { endpoints, formatGroups, typeText } from "./describe";
import type { FormatContract, OpenApiDocument } from "./types";

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

test("every route becomes an endpoint with its method, in the document order", () => {
  expect(endpoints(DOCUMENT).map((e) => `${e.method} ${e.path}`)).toEqual(["GET /api/sources", "POST /api/sources", "DELETE /api/sources/{sid}"]);
});

test("a request body is listed by the fields of the schema it references", () => {
  const body = endpoints(DOCUMENT)[1].tables.find((table) => table.title === "Request body, AttachBody")!;
  expect(body.rows).toEqual([
    ["path", "string", "required"],
    ["kind", '"transformed" or "processed"', "required"],
    ["processed_path", "string or null", "optional"],
  ]);
});

test("a path parameter is listed as required and an empty response schema as any", () => {
  const [parameters] = endpoints(DOCUMENT)[2].tables;
  expect(parameters.rows).toEqual([["sid", "path", "string", "yes", ""]]);
  expect(endpoints(DOCUMENT)[0].tables[0].rows).toEqual([["200", "Successful Response", "application/json", "any"]]);
});

test("a list of alternatives reads as words", () => {
  expect(typeText({ type: "array", items: { oneOf: [{ $ref: "#/components/schemas/A" }, { $ref: "#/components/schemas/B" }] } })).toBe("list of A or B");
});

test("the contract gives one table per file, marking the columns the tool reads", () => {
  const contract = {
    transformed: { files: [{ path: "runs.csv", optional: false, columns: [{ name: "run", type: "int64", required: true }, { name: "notes", type: "string", required: false }] }] },
    processed: { kinds: ["track", "arena"], files: [{ path: "manifest.json", optional: false, keys: ["run.timestamp"] }] },
    review: { path: "review/<session_id>.json", keys: ["session_id"], block_keys: ["block_id"], statuses: ["auto"], edits: { move: ["frame", "edge", "at"] } },
    window_settings: { window_s: 40 },
  } as unknown as FormatContract;
  const [transformed, processed, review] = formatGroups(contract);
  expect(transformed.tables[0].rows).toEqual([["run", "int64", "read by the tool"], ["notes", "string", ""]]);
  expect(processed.title).toBe("Processed folder, kinds track and arena");
  expect(processed.tables[0].rows).toEqual([["run.timestamp"]]);
  expect(review.tables[3].rows).toEqual([["move", "frame, edge, at"]]);
});
