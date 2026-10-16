import type { FormatContract, FormatFile, OpenApiDocument, OpenApiOperation, SchemaNode } from "./types";

/** Something the API page shows as a titled table. */
export interface Table {
  title: string;
  head: string[];
  rows: string[][];
}

export interface FormatGroup {
  title: string;
  tables: Table[];
}

export interface Endpoint {
  method: string;
  path: string;
  summary: string;
  description: string;
  tables: Table[];
}

const METHODS = ["get", "post", "put", "delete"];
const ANY = "any";

function fileTable(file: FormatFile): Table {
  const title = file.optional ? `${file.path} (optional)` : file.path;
  if (file.keys) return { title, head: ["key"], rows: file.keys.map((key) => [key]) };
  const rows = (file.columns ?? []).map((column) => [column.name, column.type, column.required ? "read by the tool" : ""]);
  return { title, head: ["column", "type", "use"], rows };
}

/** The data format contract as groups of tables, one table per file. */
export function formatGroups(contract: FormatContract): FormatGroup[] {
  const { review, window_settings: settings } = contract;
  return [
    { title: "Transformed folder", tables: contract.transformed.files.map(fileTable) },
    { title: `Processed folder, kinds ${contract.processed.kinds.join(" and ")}`, tables: contract.processed.files.map(fileTable) },
    {
      title: "Review file",
      tables: [
        { title: review.path, head: ["key"], rows: review.keys.map((key) => [key]) },
        { title: "block keys", head: ["key"], rows: review.block_keys.map((key) => [key]) },
        { title: "block statuses", head: ["status"], rows: review.statuses.map((status) => [status]) },
        { title: "edits", head: ["op", "fields"], rows: Object.entries(review.edits).map(([op, fields]) => [op, fields.join(", ")]) },
      ],
    },
    {
      title: "Window settings",
      tables: [{ title: "defaults", head: ["setting", "value"], rows: Object.entries(settings).map(([name, value]) => [name, String(value)]) }],
    },
  ];
}

/** A schema node as words: a type, a reference's name, alternatives, a list of something. */
export function typeText(node: SchemaNode): string {
  if (node.$ref) return node.$ref.split("/").pop()!;
  if (node.enum) return node.enum.map((value) => JSON.stringify(value)).join(" or ");
  const alternatives = node.anyOf ?? node.oneOf;
  if (alternatives) return alternatives.map(typeText).join(" or ");
  if (node.type === "array") return `list of ${node.items ? typeText(node.items) : ANY}`;
  return node.type ?? ANY;
}

function propertyTable(title: string, schema: SchemaNode): Table {
  const rows = Object.entries(schema.properties ?? {}).map(([name, node]) => [
    name, typeText(node), schema.required?.includes(name) ? "required" : "optional",
  ]);
  return { title, head: ["field", "type", "required"], rows };
}

function operationTables(operation: OpenApiOperation, schemas: Record<string, SchemaNode>): Table[] {
  const tables: Table[] = [];
  if (operation.parameters?.length) {
    tables.push({
      title: "Parameters",
      head: ["name", "in", "type", "required", "default"],
      rows: operation.parameters.map((p) => [
        p.name, p.in, typeText(p.schema), p.required ? "yes" : "no", p.schema.default === undefined ? "" : String(p.schema.default),
      ]),
    });
  }
  const body = operation.requestBody?.content["application/json"]?.schema;
  if (body) {
    const name = typeText(body);
    tables.push(propertyTable(`Request body, ${name}`, schemas[name] ?? body));
  }
  tables.push({
    title: "Responses",
    head: ["status", "description", "content type", "shape"],
    rows: Object.entries(operation.responses).map(([status, response]) => {
      const [contentType, content] = Object.entries(response.content ?? {})[0] ?? ["", undefined];
      return [status, response.description, contentType, content ? typeText(content.schema) : ""];
    }),
  });
  return tables;
}

/** The routes of the OpenAPI document in its order, each with its parameter, body and response tables. */
export function endpoints(document: OpenApiDocument): Endpoint[] {
  const schemas = document.components?.schemas ?? {};
  return Object.entries(document.paths).flatMap(([path, operations]) =>
    METHODS.filter((method) => method in operations).map((method) => {
      const operation = operations[method];
      return {
        method: method.toUpperCase(),
        path,
        summary: operation.summary ?? "",
        description: operation.description ?? "",
        tables: operationTables(operation, schemas),
      };
    }),
  );
}

/** Every named schema of the document as a table of its fields. */
export function schemaTables(document: OpenApiDocument): Table[] {
  return Object.entries(document.components?.schemas ?? {}).map(([name, schema]) => propertyTable(name, schema));
}
