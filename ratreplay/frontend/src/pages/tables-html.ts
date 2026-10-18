import { TABLE, TD, TH } from "../ui/style";

/** The table of `table` (a Table of api/describe), for an x-for over tables. */
export const tableMarkup = `
  <div class="overflow-x-auto">
    <table class="${TABLE} text-xs">
      <thead><tr><template x-for="name in table.head" :key="name"><th class="${TH}" x-text="name"></th></template></tr></thead>
      <tbody>
        <template x-for="(cells, index) in table.rows" :key="index">
          <tr class="border-t border-line">
            <template x-for="(cell, column) in cells" :key="column"><td class="${TD}" x-text="cell"></td></template>
          </tr>
        </template>
      </tbody>
    </table>
  </div>`;

/** The table of `table` folded under its title, open on a click. */
export const tableHtml = `
  <details class="rounded-md border border-line">
    <summary class="cursor-pointer select-none px-3 py-1.5 text-sm" x-text="table.title"></summary>
    <div class="px-3 pb-2">${tableMarkup}</div>
  </details>`;
