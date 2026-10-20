import { DataType, tableFromIPC } from "apache-arrow";

export type Column = Float64Array | Float32Array | Int32Array | Int8Array | Uint8Array;

/** An Arrow IPC stream as one typed array per column, a bool column as 0 and 1 in a Uint8Array. */
export function decodeColumns(bytes: ArrayBuffer): Record<string, Column> {
  const table = tableFromIPC(new Uint8Array(bytes));
  const columns: Record<string, Column> = {};
  for (const field of table.schema.fields) {
    const vector = table.getChild(field.name)!;
    columns[field.name] = DataType.isBool(field.type) ? Uint8Array.from(vector, Number) : vector.toArray();
  }
  return columns;
}
