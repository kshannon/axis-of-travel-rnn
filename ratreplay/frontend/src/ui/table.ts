import { TABLE, TD, TH } from "./style";

type Cell = string | number | null;

export interface Column<R> {
  key: string;
  label: string;
  /** What sorting compares. */
  value: (row: R) => Cell;
  /** What the cell shows. */
  text: (row: R) => string;
  numeric?: boolean;
  /** Classes added to the cell, for a colour that depends on the row. */
  tone?: (row: R) => string;
}

export interface Sort {
  key: string;
  descending: boolean;
}

function compare(a: Cell, b: Cell): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/** The rows by the sort, a missing value always last, or as they came when there is no sort. */
export function sortRows<R>(rows: R[], columns: readonly Column<R>[], sort: Sort | null): R[] {
  const column = columns.find((c) => c.key === sort?.key);
  if (!sort || !column) return rows;
  const sign = sort.descending ? -1 : 1;
  return [...rows].sort((a, b) => {
    const [x, y] = [column.value(a), column.value(b)];
    if (x === null || y === null) return Number(x === null) - Number(y === null);
    return sign * compare(x, y);
  });
}

/** A click on a header: a new column sorts ascending, the same column again reverses. */
export function clickHeader(sort: Sort | null, key: string): Sort {
  return { key, descending: sort?.key === key && !sort.descending };
}

/** The arrow a header shows when the table is sorted by its column. */
export function sortArrow(sort: Sort | null, key: string): string {
  return sort?.key === key ? (sort.descending ? " ↓" : " ↑") : "";
}

export interface TableParts {
  /** Alpine expression of a row's key, `row` being the row. */
  rowKey: string;
  /** Alpine expression of a row's hover title. */
  rowTitle: string;
  /** Alpine expression of the classes a row adds, such as a muted row. */
  rowClass?: string;
  /** A header cell and a cell per row after the columns, for a column of buttons. */
  extra?: { head: string; cell: string };
  /** What fills the row under an open row, across the table. */
  details: string;
}

/**
 * The sortable table of a page whose Alpine data has `columns`, `shown` (the rows in order), `openId`, `sortBy`, `arrow`
 * and `toggle(row)`. A click on a row toggles its details.
 */
export function sortableTable(parts: TableParts): string {
  const { rowKey, rowTitle, rowClass = "''", extra, details } = parts;
  return `
    <div class="min-h-0 flex-1 overflow-auto">
      <table class="${TABLE}">
        <thead class="sticky top-0 z-10 bg-card">
          <tr>
            <template x-for="column in columns" :key="column.key">
              <th class="${TH}" :class="column.numeric ? 'text-right' : ''">
                <button type="button" @click="sortBy(column.key)" class="uppercase tracking-wide hover:text-ink">
                  <span x-text="column.label"></span><span x-text="arrow(column.key)"></span>
                </button>
              </th>
            </template>
            ${extra?.head ?? ""}
          </tr>
        </thead>
        <template x-for="row in shown" :key="${rowKey}">
          <tbody class="border-t border-line">
            <tr @click="toggle(row)" class="cursor-pointer hover:bg-ink/5" :class="${rowClass}" :title="${rowTitle}">
              <template x-for="column in columns" :key="column.key">
                <td class="${TD} whitespace-nowrap" :class="[column.numeric ? 'text-right tabular-nums' : '', column.tone ? column.tone(row) : '']"
                  x-text="column.text(row)"></td>
              </template>
              ${extra?.cell ?? ""}
            </tr>
            <template x-if="openId === ${rowKey}">
              <tr><td :colspan="columns.length + ${extra ? 1 : 0}" class="bg-page/60 px-4 py-3">${details}</td></tr>
            </template>
          </tbody>
        </template>
      </table>
    </div>`;
}
