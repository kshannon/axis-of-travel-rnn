import { card } from "../ui/card";
import { factsList } from "../ui/facts";
import { CHIP_MUTED, CHIP_WARN, TD, TH } from "../ui/style";
import { sortableTable } from "../ui/table";
import { HEIGHT_PX, WIDTH_PX } from "./environments-draw";

const CAPTION = `Plan view in metres, y up, every environment at one scale: walls solid, the centerline dotted, reward sites as circles. Drawn from the yaml, no recording.`;

// The warnings chip, after the table's columns, sorts like them.
const warningsColumn = {
  head: `
    <th class="${TH}">
      <button type="button" @click="sortBy('warnings')" class="uppercase tracking-wide hover:text-ink">
        <span>Warnings</span><span x-text="arrow('warnings')"></span>
      </button>
    </th>`,
  cell: `
    <td class="${TD}">
      <span :class="row.warnings.length ? '${CHIP_WARN}' : '${CHIP_MUTED}'" x-text="warningsText(row)"></span>
    </td>`,
};

const details = `
  <div class="flex flex-wrap items-start gap-x-16 gap-y-3 text-xs">
    ${factsList("facts(row)")}
    <ul x-show="row.warnings.length" class="list-disc space-y-0.5 pl-5 text-warn">
      <template x-for="warning in row.warnings"><li x-text="warning"></li></template>
    </ul>
  </div>`;

const geometryFigure = `<div x-init="draw($el, environment)" data-testid="geometry" style="width: ${WIDTH_PX}px; height: ${HEIGHT_PX}px" class="shrink-0 rounded-md bg-page"></div>`;

const environmentBody = `
  <div x-data="environmentSessions(environment)" data-testid="environment" class="flex h-full min-h-0 gap-6">
    <figure class="flex w-[25rem] shrink-0 flex-col gap-2 overflow-auto">
      <div class="flex items-start gap-4">
        ${geometryFigure}
        <div class="min-w-0 text-xs">${factsList("params")}</div>
      </div>
      <figcaption class="text-xs text-muted">${CAPTION}</figcaption>
    </figure>
    <div class="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
      <p x-show="!environment.sessions.length" data-testid="no-sessions" class="text-sm text-muted">No built session is registered in this environment.</p>
      <template x-if="environment.sessions.length">
        <div class="flex min-h-0 flex-1 flex-col gap-2 [&_table]:text-xs">
          <p data-testid="ranges" class="text-xs text-muted" x-text="line"></p>
          ${sortableTable({ rowKey: "rowId(row)", rowTitle: "rowTitle(row)", extra: warningsColumn, details })}
        </div>
      </template>
    </div>
  </div>`;

const environmentCard = card(
  `<span x-text="environment.name"></span>`,
  environmentBody,
  "",
  `<span class="${CHIP_MUTED}" x-text="environment.kind"></span>`,
);

// An environment with built sessions takes a row, one without shares a row with another, the grid packing the gaps.
const environmentCell = `<div :class="environment.sessions.length ? 'col-span-2' : 'col-span-1'" class="grid min-h-0 min-w-0">${environmentCard}</div>`;

/** The Environments page: a card per environment with its geometry, its yaml parameters and the sessions built in it. */
export const environmentsRoot = `
  <div x-data="environmentsPage" class="h-full overflow-auto">
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Loading the environments</p>
    <div class="grid h-full auto-rows-[minmax(18rem,1fr)] grid-flow-dense grid-cols-2 gap-4">
      <template x-for="environment in environments" :key="environment.name">${environmentCell}</template>
    </div>
  </div>`;
