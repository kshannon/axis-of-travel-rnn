import { card } from "../ui/card";
import { factsList } from "../ui/facts";
import { CHIP_MUTED, CHIP_WARN, TD, TH } from "../ui/style";
import { sortableTable } from "../ui/table";
import { THUMBNAIL_HEIGHT_PX } from "./environments-draw";

const CAPTION = `Plan view in metres, y up: walls solid, the centerline dotted, reward sites as circles. Fitted to its room here, the thumbnails above share one scale.`;

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

// The strip: a tile per environment, the selected one marked with the accent, a click choosing it.
const thumbnail = `
  <button type="button" data-testid="thumbnail" @click="select(thumb.name)" :aria-pressed="thumb.selected"
    :class="thumb.selected ? 'border-accent bg-accent/10' : 'border-line bg-card hover:border-ink/40'"
    class="flex min-w-[13rem] flex-1 flex-col gap-1 rounded-xl border p-2 text-left">
    <span class="flex items-center justify-between gap-2">
      <span class="truncate text-sm font-medium" x-text="thumb.name"></span>
      <span class="${CHIP_MUTED}" x-text="thumb.kind"></span>
    </span>
    <span x-init="drawThumbnail($el, thumb.name)" class="relative block w-full rounded-md bg-page" style="height: ${THUMBNAIL_HEIGHT_PX}px"></span>
    <span class="text-xs text-muted" x-text="thumb.sessions"></span>
  </button>`;

const strip = `
  <div x-ref="strip" data-testid="strip" class="flex shrink-0 gap-3 overflow-x-auto">
    <template x-for="thumb in thumbs" :key="thumb.name">${thumbnail}</template>
  </div>`;

// The drawing takes the room the card has. An environment with sessions gives the right of the card to them, one without lets the drawing have it.
const figure = `
  <figure :class="environment.sessions.length ? 'w-[28rem] max-w-[40%] shrink-0' : 'min-w-0 flex-1'" class="flex min-h-0 flex-col gap-2">
    <div x-init="drawLarge($el, environment)" data-testid="geometry" class="relative min-h-32 flex-1 rounded-md bg-page"></div>
    <figcaption class="shrink-0 text-xs text-muted">${CAPTION} Drawn from the yaml of <span x-text="environment.name"></span>, no recording.</figcaption>
  </figure>`;

const params = `
  <dl class="grid shrink-0 grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-x-6 gap-y-1 text-xs">
    <template x-for="fact in params" :key="fact.label">
      <div class="flex gap-2"><dt class="text-muted" x-text="fact.label"></dt><dd x-text="fact.value"></dd></div>
    </template>
  </dl>`;

const sessions = `
  <div :class="environment.sessions.length ? 'min-w-0 flex-1' : 'w-72 shrink-0'" class="flex min-h-0 flex-col gap-3">
    <p x-show="!environment.sessions.length" data-testid="no-sessions" class="text-sm text-muted">No built session is registered in this environment.</p>
    <template x-if="environment.sessions.length">
      <p data-testid="ranges" class="shrink-0 text-sm" x-text="line"></p>
    </template>
    ${params}
    <template x-if="environment.sessions.length">
      <div class="flex min-h-0 flex-1 flex-col [&_table]:text-xs">
        ${sortableTable({ rowKey: "rowId(row)", rowTitle: "rowTitle(row)", extra: warningsColumn, details })}
      </div>
    </template>
  </div>`;

const environmentCard = card(
  `<span x-text="environment.name"></span>`,
  `<div class="flex h-full min-h-0 gap-4">${figure}${sessions}</div>`,
  "",
  `<span class="${CHIP_MUTED}" x-text="environment.kind"></span>`,
);

// The card is built again on every choice, keyed by the name, so its table starts unsorted and closed.
const selectedEnvironment = `
  <div x-data="environmentSessions(environment)" data-testid="environment" class="grid min-h-0 min-w-0 flex-1">${environmentCard}</div>`;

/** The Environments page: a strip of thumbnails to choose from over the chosen environment, large, with its parameters, the ranges of its registrations and the sessions built in it. */
export const environmentsRoot = `
  <div x-data="environmentsPage" class="flex h-full min-h-0 flex-col gap-4">
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Loading the environments</p>
    ${strip}
    <template x-for="environment in large" :key="environment.name">${selectedEnvironment}</template>
  </div>`;
