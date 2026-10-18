import { card } from "../ui/card";
import { factsList } from "../ui/facts";
import { helpPopover } from "../ui/help";
import { BUTTON, CHIP_BAD, CHIP_MUTED, CHIP_OK, INPUT, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { sortableTable } from "../ui/table";
import { blockLanesBody } from "./block-lanes-html";
import { playbackBody } from "./playback-html";
import { compareTable } from "./tables-html";

const MAP_HELP = `
  <p>The positions are the processed dataset's, in the room frame in metres with y up and equal axes. Under them the environment config: the walls as grey lines, the centerline dotted, the start and goal sites as circles, or the arena as a circle.</p>
  <p class="mt-2">The path lying on the drawn geometry is the check of the registration. The dots are the last 2 s of the path coloured by speed, the red dot is the current position and the red arrow the heading after the heading fill and the LED offset.</p>`;

const TIMELINE_HELP = `
  <p>One time axis in minutes of the block. Runs: dark blue outbound, light blue return, hatched when dirty. Frames: the speed as a grey trace, the yellow band heading filled, the teal band heading held, the grey band above them one light alone giving the position. Trips: purple, hatched when partial.</p>
  <p class="mt-2">Windows at the settings tested: each window is its burn-in in a lighter shade, the rest of it, and its horizon hatched after it. A window in trouble is red. Windows overlap, so they are staggered in rows. Click a lane to move the cursor. The wheel zooms and a drag pans.</p>`;

const judgedBody = `
  <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
    <label class="flex items-center gap-2 text-xs text-muted">
      <span>dataset</span>
      <select x-model="which" @change="change()" aria-label="Dataset" class="${INPUT} w-28">
        <template x-for="choice in choices" :key="choice"><option :value="choice" :selected="choice === which" x-text="choice"></option></template>
      </select>
    </label>
    <p data-testid="judged" class="text-sm" x-text="judgedLine"></p>
    <a href="#/settings" class="text-sm text-accent underline">Change on the Settings page</a>
  </div>`;

const totalsBody = `
  <div data-testid="totals" class="grid grid-cols-5 gap-3">
    <template x-for="tile in totals" :key="tile.label">
      <div class="${TILE}"><p class="truncate ${TILE_LABEL}" x-text="tile.label"></p><p class="${TILE_VALUE}" x-text="tile.value"></p></div>
    </template>
  </div>`;

const detailsBody = `<div class="flex flex-wrap items-start gap-x-16 gap-y-3">${factsList("facts(row)")}${compareTable("row.compare", "being tried", "built-with")}</div>`;

const openColumn = {
  head: `<th class="px-2 py-1.5"></th>`,
  cell: `<td class="px-2 py-1.5 text-right"><button type="button" @click.stop="open(row)" :disabled="opening" :aria-label="'Open ' + row.block_id" class="${BUTTON}">Open</button></td>`,
};

const indexBody = `
  <div class="flex h-full flex-col gap-3">
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Loading the blocks</p>
    <p x-show="!loading && !error && !rows.length" class="text-sm text-muted">The dataset has no block.</p>
    <template x-if="rows.length">
      ${sortableTable({ rowKey: "row.block_id", rowTitle: "row.block_id", extra: openColumn, details: detailsBody })}
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

const indexView = `
  <div x-show="view === 'index'" class="grid h-full grid-cols-12 grid-rows-[auto_auto_minmax(0,1fr)] gap-4">
    ${card("Judged at", judgedBody, "col-span-12")}
    ${card("Totals", totalsBody, "col-span-12")}
    ${card("Index", indexBody, "col-span-12", indexActions)}
  </div>`;

const blockView = `
  <div x-show="view === 'block'" class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,4fr)_minmax(0,3fr)] gap-4">
    ${card("Block", lineBody, "col-span-12", lineActions)}
    ${card("Map", mapBody, "col-span-5", helpPopover("About the map", MAP_HELP))}
    ${card("Playback", playbackCard, "col-span-3")}
    ${card("Block facts", factsList("openFacts"), "col-span-4")}
    ${card("Timeline", blockLanesBody, "col-span-12", timelineActions)}
  </div>`;

/** The Blocks page: the settings, the totals and the index, or the block opened from it with its map, playback and lanes. */
export const blocksRoot = `
  <div x-data="blocksPage" @mousedown="$event.target.closest('button') && $event.preventDefault()" class="h-full">
    ${indexView}${blockView}
  </div>`;
