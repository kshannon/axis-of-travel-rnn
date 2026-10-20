import { CHIP_MUTED, TABLE, TD, TH } from "../ui/style";

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

/** The body of a format card, for a page whose Alpine data has `groups`: a heading per group over its tables, each folded under its file name. */
export const formatBody = `
  <p x-show="!groups.length" class="text-sm text-muted">Reading the data format</p>
  <div class="flex flex-col gap-3">
    <template x-for="group in groups" :key="group.title">
      <section class="flex flex-col gap-2">
        <h3 class="text-sm font-medium" x-text="group.title"></h3>
        <div class="grid grid-cols-4 items-start gap-3">
          <template x-for="table in group.tables" :key="table.title">${tableHtml}</template>
        </div>
      </section>
    </template>
  </div>`;

/** The chip beside a format card's title, for a page whose Alpine data has `version`. */
export const formatChip = `<span x-show="version" class="${CHIP_MUTED}" x-text="'format version ' + version"></span>`;

/** The settings beside the ones a session was built with, `rows` being the Alpine expression of a list of SettingRow and `tried` the head of the first value column. A setting that differs is warned. */
export function compareTable(rows: string, tried: string, testId: string): string {
  return `
    <table data-testid="${testId}" class="self-start text-xs">
      <thead><tr><th class="pr-8 text-left font-medium text-muted">setting</th><th class="pr-8 text-left font-medium text-muted">${tried}</th><th class="text-left font-medium text-muted">session built with</th></tr></thead>
      <tbody>
        <template x-for="setting in ${rows}" :key="setting.label">
          <tr :class="setting.differs ? 'text-warn' : ''">
            <td class="pr-8" x-text="setting.label"></td><td class="pr-8 tabular-nums" x-text="setting.tried"></td><td class="tabular-nums" x-text="setting.built"></td>
          </tr>
        </template>
      </tbody>
    </table>`;
}
