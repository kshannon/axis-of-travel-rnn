import { card, pageGrid } from "../ui/card";
import { helpPopover } from "../ui/help";
import { BUTTON, BUTTON_PRIMARY, CHIP_BAD, CHIP_MUTED, CHIP_OK, INPUT, KBD, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { blockLanesBody } from "./block-lanes-html";

const MAP_HELP = `
  <p>The window on the block's map in metres, y up, over the environment. The thin line is the whole path of the block. The burn-in is the lighter blue, the first seconds that only warm the network up. The darker blue is the rest of the window the network is shown, and the orange line after it is the horizon, the future position it has to predict.</p>`;

const TIMELINE_HELP = `
  <p>The lanes of the block zoomed to the window, which is outlined. Windows overlap, so they are staggered in rows, a window in trouble is red, its burn-in is lighter and its horizon hatched after it. A click on a window selects it. The wheel zooms and a drag pans.</p>`;

const LIGHTER_ACCENT = "bg-[color-mix(in_srgb,var(--accent),white_45%)]";
const swatch = (colour: string, label: string) => `<span class="${CHIP_MUTED} inline-flex items-center gap-1.5"><span class="size-2 rounded-full ${colour}"></span>${label}</span>`;

const windowBody = `
  <div class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span data-testid="block-id" class="font-mono" x-text="line.id"></span>
      <span class="${CHIP_MUTED}" x-text="line.kind"></span>
      <span class="${CHIP_MUTED}" x-text="line.status"></span>
      <span :class="line.ok ? '${CHIP_OK}' : '${CHIP_BAD}'" x-text="line.verdict"></span>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button type="button" @click="step(-1)" :disabled="!count || index === 0" class="${BUTTON}">Previous <kbd class="${KBD}">left</kbd></button>
      <label x-show="count" class="flex items-center gap-2 text-sm">window
        <input type="number" min="1" :max="count" x-model.number="jump" @change="goTo(jump)" aria-label="Window number" class="${INPUT} w-20" />
        of <span data-testid="window-count" x-text="count"></span>
      </label>
      <span x-show="!count" data-testid="no-window" class="${CHIP_BAD}">no window fits</span>
      <button type="button" @click="step(1)" :disabled="!count || index === count - 1" class="${BUTTON}">Next <kbd class="${KBD}">right</kbd></button>
      <span x-show="count" data-testid="window-verdict" :class="windowOk ? '${CHIP_OK}' : '${CHIP_BAD}'" x-text="verdict"></span>
    </div>
    <p x-show="count" data-testid="window-span" class="text-xs text-muted" x-text="span"></p>
    <p x-show="!count" class="text-sm text-muted">Nothing to step through at these settings. Change them on the Blocks page.</p>
  </div>`;

const totalsBody = `
  <div class="flex flex-col gap-2">
    <div class="grid grid-cols-3 gap-2">
      <div class="${TILE}"><p class="${TILE_LABEL}">windows ok</p><p data-testid="windows-ok" class="${TILE_VALUE}" x-text="okCount + ' of ' + count"></p></div>
      <div class="${TILE}"><p class="${TILE_LABEL}">in trouble</p><p class="${TILE_VALUE}" x-text="count - okCount"></p></div>
      <div class="${TILE}"><p class="${TILE_LABEL}">block</p><p data-testid="block-verdict" class="break-words ${TILE_VALUE}" x-text="line.verdict"></p></div>
    </div>
    <p class="text-xs text-muted" x-text="settingsLine"></p>
  </div>`;

const checksBody = `
  <ul x-show="count" class="flex flex-col gap-2">
    <template x-for="check in checks" :key="check.label">
      <li class="flex items-center justify-between gap-3 rounded-md bg-page px-3 py-2">
        <div class="min-w-0">
          <p class="text-sm font-medium" x-text="check.label"></p>
          <p class="text-xs text-muted" x-text="check.note"></p>
        </div>
        <span class="shrink-0 tabular-nums" x-text="check.value"></span>
      </li>
    </template>
  </ul>`;

const mapActions = `
  ${swatch(LIGHTER_ACCENT, "burn-in")}${swatch("bg-accent", "window")}${swatch("bg-warn", "horizon")}
  ${helpPopover("About the map", MAP_HELP)}`;

const timelineActions = `
  <button type="button" @click="fitWindow()" :disabled="!count" class="${BUTTON}">Fit window</button>
  <button type="button" @click="zoomAll()" class="${BUTTON}">Whole block</button>
  ${helpPopover("About the block lanes", TIMELINE_HELP)}`;

const windowsGrid = `
  <div class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,4fr)_minmax(0,3fr)] gap-4">
    ${card("Window", windowBody, "col-span-7")}
    ${card("Block totals", totalsBody, "col-span-5")}
    ${card("Map", `<div x-ref="map" data-testid="map" class="relative h-full min-h-0"></div>`, "col-span-7", mapActions)}
    ${card("Checks", checksBody, "col-span-5")}
    ${card("Timeline", blockLanesBody, "col-span-12", timelineActions)}
  </div>`;

const noBlock = `
  <div class="flex flex-col items-start gap-2 text-sm">
    <p>No block is open, open one on the Blocks page.</p>
    <a href="#/blocks" class="${BUTTON_PRIMARY}">Choose a block</a>
  </div>`;

/** The Windows page: one window of the block opened on the Blocks page at a time, or the way to open a block. */
export const windowsRoot = `
  <div x-data="windowsPage" @mousedown="$event.target.closest('button') && $event.preventDefault()" class="h-full">
    <template x-if="!ready">${pageGrid(card("Windows", noBlock))}</template>
    <template x-if="ready">${windowsGrid}</template>
  </div>`;
