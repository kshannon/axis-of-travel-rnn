import { card } from "../ui/card";
import { factsList } from "../ui/facts";
import { helpPopover } from "../ui/help";
import { BUTTON, BUTTON_PRIMARY, CHIP_BAD, CHIP_MUTED, CHIP_OK, FIELD, INPUT, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { sortableTable } from "../ui/table";
import { playbackBody } from "./playback-html";

const MAP_HELP = `
  <p>The positions are the processed dataset's, in the room frame in metres with y up and equal axes. Under them the environment config: the walls as grey lines, the centerline dotted, the start and goal sites as circles, or the arena as a circle.</p>
  <p class="mt-2">The path lying on the drawn geometry is the check of the registration. The dots are the last 2 s of the path coloured by speed, the red dot is the current position and the red arrow the heading after the processor's fill and the LED offset.</p>`;

const TIMELINE_HELP = `
  <p>One time axis in minutes of the block. Runs: dark blue outbound, light blue return, hatched when dirty. Frames: the speed as a grey trace, the yellow band heading filled, the teal band heading held, the grey band above them one light alone giving the position. Trips: purple, hatched when partial.</p>
  <p class="mt-2">Windows at the settings tested: each window is its burn-in in a lighter shade, the rest of it, and its horizon hatched after it. A window in trouble is red. Windows overlap, so they are staggered in rows. Click a lane to move the cursor. The wheel zooms and a drag pans.</p>`;

const settingsBody = `
  <div class="flex flex-col gap-2">
    <div class="flex flex-wrap items-end gap-3">
      <template x-for="field in fields" :key="field.key">
        <label class="${FIELD} w-36">
          <span x-text="field.label"></span>
          <input type="number" min="0" :step="field.step" x-model.number="draft[field.key]" @keydown.enter="test()" class="${INPUT}" />
        </label>
      </template>
      <button type="button" @click="test()" :disabled="busy" class="${BUTTON_PRIMARY}">Test on all blocks</button>
      <button type="button" @click="saveSettings()" :disabled="busy" class="${BUTTON}">Save settings</button>
    </div>
    <p data-testid="tested" class="text-xs text-muted" x-text="verdictsAt"></p>
    <p class="text-xs text-muted">The training pipeline reads <span class="font-mono" x-text="settingsPath"></span> and nothing else.</p>
  </div>`;

const totalsBody = `
  <div data-testid="totals" class="grid grid-cols-3 gap-6">
    <template x-for="group in totals" :key="group.kind">
      <div class="flex items-center gap-2">
        <h3 class="w-14 shrink-0 text-sm font-medium capitalize" x-text="group.kind"></h3>
        <template x-for="tile in group.tiles" :key="tile.label">
          <div class="${TILE} min-w-0 flex-1"><p class="truncate ${TILE_LABEL}" x-text="tile.label"></p><p class="${TILE_VALUE}" x-text="tile.value"></p></div>
        </template>
      </div>
    </template>
  </div>`;

const openColumn = {
  head: `<th class="px-2 py-1.5"></th>`,
  cell: `<td class="px-2 py-1.5 text-right"><button type="button" @click.stop="open(row)" :disabled="opening" :aria-label="'Open ' + row.block_id" class="${BUTTON}">Open</button></td>`,
};

const indexBody = `
  <div class="flex h-full flex-col gap-3">
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Loading the blocks</p>
    <p x-show="!loading && !error && !rows.length" class="text-sm text-muted">The processed dataset has no block.</p>
    <template x-if="rows.length">
      ${sortableTable({ rowKey: "row.block_id", rowTitle: "row.block_id", extra: openColumn, details: factsList("facts(row)") })}
    </template>
  </div>`;

const indexActions = `
  <span class="text-sm text-muted" x-text="rows.length + (rows.length === 1 ? ' block' : ' blocks')"></span>
  <button type="button" x-show="sort" @click="sort = null" class="${BUTTON}">Index order</button>`;

const lineBody = `
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
    <span data-testid="block-id" class="font-mono" x-text="line.id"></span>
    <span class="${CHIP_MUTED}" x-text="'session ' + line.session"></span>
    <span class="${CHIP_MUTED}" x-text="line.kind"></span>
    <span class="${CHIP_MUTED}" x-text="line.status"></span>
    <span class="text-muted" x-text="line.minutes + ' min'"></span>
    <span data-testid="block-verdict" :class="line.ok ? '${CHIP_OK}' : '${CHIP_BAD}'" x-text="line.verdict"></span>
  </div>`;

const lineActions = `
  <button type="button" @click="back()" class="${BUTTON}">Back to the index</button>
  <a href="#/windows" class="${BUTTON}">Step through its windows</a>`;

const mapBody = `<div x-ref="map" data-testid="map" class="relative h-full min-h-0"></div>`;

const playbackCard = playbackBody([
  ["time in block", "time"], ["lab frame", "frame"], ["speed", "speed"], ["lights", "lights"], ["run", "run"], ["phase", "phase"],
]);

const timelineActions = `
  <button type="button" @click="zoomAll()" class="${BUTTON}">Whole block</button>
  <button type="button" @click="zoomIn()" class="${BUTTON}">Zoom in</button>
  <button type="button" @click="zoomOut()" class="${BUTTON}">Zoom out</button>
  ${helpPopover("About the block lanes", TIMELINE_HELP)}`;

const timelineBody = `
  <div class="flex h-full min-h-0 flex-col gap-2">
    <p class="text-xs text-muted">showing <span data-testid="shown" class="tabular-nums text-ink" x-text="viewing"></span></p>
    <div x-ref="timeline" data-testid="timeline" class="relative min-h-0 flex-1 overflow-hidden"></div>
  </div>`;

const indexView = `
  <div x-show="view === 'index'" class="grid h-full grid-cols-12 grid-rows-[auto_auto_minmax(0,1fr)] gap-4">
    ${card("Window settings", settingsBody, "col-span-12")}
    ${card("Totals", totalsBody, "col-span-12")}
    ${card("Index", indexBody, "col-span-12", indexActions)}
  </div>`;

const blockView = `
  <div x-show="view === 'block'" class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,4fr)_minmax(0,3fr)] gap-4">
    ${card("Block", lineBody, "col-span-12", lineActions)}
    ${card("Map", mapBody, "col-span-5", helpPopover("About the map", MAP_HELP))}
    ${card("Playback", playbackCard, "col-span-3")}
    ${card("Block facts", factsList("openFacts"), "col-span-4")}
    ${card("Timeline", timelineBody, "col-span-12", timelineActions)}
  </div>`;

/** The Blocks page: the settings, the totals and the index, or the block opened from it with its map, playback and lanes. */
export const blocksRoot = `
  <div x-data="blocksPage" @mousedown="$event.target.closest('button') && $event.preventDefault()" class="h-full">
    ${indexView}${blockView}
  </div>`;
