import { card, foldedCard } from "../ui/card";
import { factsList } from "../ui/facts";
import { statusMark } from "../ui/status";
import { BUTTON, BUTTON_DANGER, BUTTON_ICON, BUTTON_PRIMARY, INPUT, TABLE, TD, TH, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { sortableTable } from "../ui/table";
import { ANNOTATED_NOTE } from "./exclusion-view";
import { formatBody, formatChip } from "./tables-html";

const SECONDS_PER_MINUTE = 60;
const RELOAD = "Reload config file";
const RELOAD_NOTE = "If you update the config file, or change its location, you will need to reload it to view data";

// The circular arrows glyph of the Reload button at the card's top right.
const reloadButton = `
  <button type="button" :disabled="busy" @click="reload()" aria-label="${RELOAD}" title="${RELOAD}" class="${BUTTON_ICON}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="size-4">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" />
    </svg>
  </button>`;

const stripBody = `
  <div data-testid="strip" class="flex flex-col gap-2">
    <p x-show="!lines.length" class="text-sm text-muted">Reading the data folders</p>
    <div class="grid grid-cols-[auto_15rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1.5 text-sm">
      <template x-for="line in lines" :key="line.label">
        <div class="contents">
          ${statusMark("line.status")}
          <span class="text-muted" x-text="line.label"></span>
          <div class="flex min-w-0 items-baseline gap-3">
            <code :data-testid="line.reloads ? 'config-path' : null" class="min-w-0 break-all font-mono text-xs" :title="line.path" x-text="line.path"></code>
            <span x-show="line.detail" class="shrink-0 text-xs text-muted" x-text="line.detail"></span>
          </div>
        </div>
      </template>
    </div>
    <ul x-show="problems.length" data-testid="strip-problems" class="list-disc space-y-0.5 pl-5 text-xs text-bad">
      <template x-for="problem in problems"><li><span x-text="problem.label + ': '"></span><span x-text="problem.text"></span></li></template>
    </ul>
    <p x-show="lines.length" class="text-xs text-muted">${RELOAD_NOTE}</p>
  </div>`;

const openButtons = `
  <template x-if="!confirming">
    <button type="button" @click="openInReplay(row)" class="${BUTTON_PRIMARY} self-start">Open in replay</button>
  </template>
  <template x-if="confirming">
    <div class="flex flex-col items-start gap-2">
      <p class="text-warn">The edits to <span x-text="confirming"></span> in the replay are not saved and would be lost.</p>
      <div class="flex gap-2">
        <button type="button" @click="openInReplay(row, true)" class="${BUTTON_DANGER}">Open and drop them</button>
        <button type="button" @click="confirming = ''" class="${BUTTON}">Cancel</button>
      </div>
    </div>
  </template>`;

const exclusionButton = `
  <button type="button" @click="changeExclusion(row)" :disabled="busy" class="${BUTTON} self-start" x-text="row.excluded ? 'Include' : 'Exclude'"></button>`;

const details = `
    <div class="grid grid-cols-2 gap-6 text-xs">
      <div class="flex flex-col gap-3">
        <table class="${TABLE} text-xs">
          <thead><tr>
            <th class="${TH}">Epoch</th><th class="${TH}">Environment</th><th class="${TH}">Condition</th>
            <th class="${TH}">Frames</th><th class="${TH}">Minutes</th>
          </tr></thead>
          <tbody>
            <template x-for="epoch in row.epochs" :key="epoch.epoch">
              <tr>
                <td class="${TD}" x-text="epoch.epoch"></td><td class="${TD}" x-text="epoch.environment"></td>
                <td class="${TD}" x-text="epoch.condition"></td>
                <td class="${TD} tabular-nums" x-text="epoch.frame_start + ' to ' + epoch.frame_end"></td>
                <td class="${TD} tabular-nums" x-text="(epoch.duration_s / ${SECONDS_PER_MINUTE}).toFixed(1)"></td>
              </tr>
            </template>
          </tbody>
        </table>
        ${factsList("facts(row)")}
        <ul x-show="header && header.warnings.length" class="list-disc space-y-0.5 pl-5 text-warn">
          <template x-for="warning in (header ? header.warnings : [])"><li x-text="warning"></li></template>
        </ul>
        <p x-show="detailsError" x-text="detailsError" class="text-bad"></p>
      </div>
      <div class="flex min-w-0 flex-col gap-3">
        <div>
          <h3 class="mb-1 font-medium">Blocks</h3>
          <p x-show="!header && !detailsError" class="text-muted">Loading</p>
          <p x-show="header" class="text-muted" x-text="blocksNote()"></p>
          <ul class="space-y-0.5">
            <template x-for="block in (header ? header.blocks : [])" :key="block.block_id">
              <li class="tabular-nums" x-text="blockText(block, row.rate_hz)"></li>
            </template>
          </ul>
        </div>
        <div>
          <h3 class="mb-1 font-medium">Review</h3>
          <p x-text="reviewOf(row)"></p>
          <p x-show="row.annotated_exclude" class="mt-1 text-muted">${ANNOTATED_NOTE}</p>
        </div>
        <div x-show="row.notes">
          <h3 class="mb-1 font-medium">Notes</h3>
          <p class="whitespace-pre-wrap break-words text-muted" x-text="row.notes"></p>
        </div>
        <div class="flex flex-wrap items-start gap-2">${openButtons}${exclusionButton}</div>
      </div>
    </div>`;

const sessionsTable = `
  <div x-data="incomingSessions" class="flex h-full flex-col gap-3">
    <div data-testid="totals" role="group" :aria-label="totalsLabel" x-show="rows.length" class="grid shrink-0 grid-cols-7 gap-2">
      <template x-for="tile in tiles" :key="tile.label">
        <div class="min-w-0 ${TILE}">
          <p class="truncate text-xl ${TILE_VALUE}" x-text="tile.value"></p>
          <p class="truncate ${TILE_LABEL}" :title="tile.label" x-text="tile.label"></p>
        </div>
      </template>
    </div>
    <div class="flex items-center gap-3">
      <input type="search" x-model="filter" aria-label="Filter sessions" placeholder="Filter by session id or rat" class="${INPUT} max-w-xs" />
      <span class="text-sm text-muted" x-text="summary"></span>
      <button type="button" x-show="sort" @click="sort = null" class="${BUTTON}">Dataset order</button>
    </div>
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Loading the sessions</p>
    <p x-show="!loading && !error && !rows.length" class="text-sm text-muted">The transformed lab data has no session with an arena or track epoch.</p>
    <template x-if="rows.length">
      ${sortableTable({ rowKey: "row.session_id", rowTitle: "titleOf(row)", rowClass: "row.in_dataset ? '' : 'text-muted'", details })}
    </template>
  </div>`;

// The sessions are listed once the three folders are usable. A processed folder in trouble is mended on the Outgoing page.
const sessionsGate = `
  <div class="h-full">
    <template x-if="blocked">
      <div class="flex flex-col items-start gap-2 text-sm">
        <p x-text="blocked"></p>
        <a x-show="$store.health.problem('processed')" href="#/outgoing" class="text-accent underline">Open the Outgoing page</a>
      </div>
    </template>
    <template x-if="!blocked">${sessionsTable}</template>
  </div>`;

/** The Incoming page: the strip of read paths, the sessions of the lab data with their tiles and details, and the transformed files' format folded at the bottom. */
export const incomingRoot = `
  <div x-data="incomingPage" class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,1fr)_auto] gap-4">
    ${card("Read from", stripBody, "col-span-12", reloadButton)}
    ${card("Sessions", sessionsGate, "col-span-12")}
    ${foldedCard("Incoming data format", formatBody, "col-span-12", formatChip)}
  </div>`;
