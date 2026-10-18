import { card } from "../ui/card";
import { helpPopover } from "../ui/help";
import { BUTTON, BUTTON_PRIMARY, CHIP_OFF, CHIP_ON, INPUT, KBD, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { playbackBody } from "./playback-html";

const MAP_HELP = `
  <p>The room in metres, north up, the same frame for every epoch. The outlines are the environment of the epoch chosen under occupancy: the walls, the boundary or circle of an arena, the dotted centerline and the reward sites. The grey shading is where the animal spent time in that epoch, darker is more.</p>
  <p class="mt-2">The trail is the last 2 s of the path coloured by speed in m/s. The red dot is the current position and the red arrow the heading after the fill and the LED offset. The thin line is the whole path of the selected block. Positions outside the room are drawn outside the outline, where a registration problem shows, and are counted in the Session card.</p>`;

const TIMELINE_HELP = `
  <p>One time axis in minutes of recording, a pause is a mark and not a stretch. Session: the epochs. Runs: the lab's runs, dark blue outbound and light blue return, hatched when dirty, outlined red when flagged. Frames: what cut the session and what the review looks at, each layer a chip above (pauses, gaps, jumps, margins, heading lost, filled and held, speed). Blocks: the blocks as they stand after the edits, coloured by status, a hover tells their windows and verdict.</p>
  <p class="mt-2">A block is cut at every pause, jump, gap and epoch bound, a margin is trimmed beside each cut and a piece that is too short is dropped. The cuts, margins and fills are the engine's, the same call that builds the blocks, so a confirmed block is the block it builds.</p>
  <p class="mt-2">Click a lane to move the cursor, click a block bar to select it. The wheel zooms and a drag pans.</p>`;

const toggle = (pressed: string, on: string, off: string) => `:class="${pressed} ? '${on}' : '${off}'"`;

const sessionActions = `
  <button type="button" @click="save()" :disabled="loading || busy || !inDataset" :title="inDataset ? '' : 'Not in the dataset: ' + reason" class="${BUTTON_PRIMARY}">Save blocks</button>
  <button type="button" @click="undo()" :disabled="!editCount" class="${BUTTON}">Undo <kbd class="${KBD}">z</kbd></button>
  <button type="button" @click="reset()" :disabled="!editCount" class="${BUTTON}">Reset to automatic</button>`;

const sessionBody = `
  <div class="flex items-end justify-between gap-3">
    <div class="flex min-w-0 flex-col gap-1">
      <p data-testid="session-id" class="truncate font-mono text-sm" x-text="sessionId"></p>
      <p class="text-xs" x-text="facts"></p>
      <p data-testid="state" class="text-xs text-muted" x-text="stateLine"></p>
      <ul data-testid="notices" x-show="notices.length" class="max-h-14 space-y-0.5 overflow-auto text-xs">
        <template x-for="notice in notices"><li :class="notice.tone" x-text="notice.text"></li></template>
      </ul>
      <p x-show="error" x-text="error" role="alert" class="text-xs text-bad"></p>
    </div>
    <button type="button" @click="wholeSession()" :disabled="loading" class="${BUTTON} shrink-0">Whole session</button>
  </div>`;

const summaryBody = `
  <div class="grid grid-cols-9 gap-2">
    <template x-for="tile in summary" :key="tile.label">
      <div class="${TILE}" :class="tile.wide ? 'col-span-2' : ''" :title="tile.title">
        <p class="truncate ${TILE_LABEL}" x-text="tile.label"></p>
        <p class="truncate ${TILE_VALUE}" x-text="tile.value"></p>
        <p class="truncate text-xs text-muted" x-text="tile.note"></p>
      </div>
    </template>
  </div>
  <p data-testid="settings" class="mt-2 text-xs text-muted" title="The window settings the counts are at. The Blocks page changes them.">settings in use: <span class="text-ink" x-text="settingsLine"></span></p>`;

const blockCard = `
  <article @click="select(block.position)" :aria-current="block.selected" class="cursor-pointer rounded-lg border p-2 text-xs"
    :class="[block.selected ? 'border-accent bg-accent/10' : 'border-line hover:border-muted', block.removed || block.windows === 0 ? 'opacity-60' : '']">
    <div class="flex items-center justify-between gap-2">
      <h3 class="text-sm font-medium" x-text="block.name"></h3>
      <span :class="block.chip" x-text="block.glyph + ' ' + block.status"></span>
    </div>
    <p class="mt-0.5 text-muted" x-text="block.epoch + ', ' + block.minutes + ' min, ' + block.runs + ' runs'"></p>
    <p class="text-muted" x-text="block.windowsText"></p>
    <p x-show="block.verdict" data-testid="verdict" :class="block.ok ? 'text-ok' : 'text-warn'" x-text="block.verdict"></p>
    <template x-for="problem in block.problems"><p class="text-bad" x-text="problem"></p></template>
    <div class="mt-1.5 flex gap-1.5">
      <button type="button" @click.stop="act('accept', block.position)" :disabled="!block.acceptable" :aria-pressed="block.accepted"
        :aria-label="'Accept ' + block.name" ${toggle("block.accepted", CHIP_ON, CHIP_OFF)}>Accept</button>
      <button type="button" @click.stop="act('reject', block.position)" :aria-pressed="block.removed"
        :aria-label="'Reject ' + block.name" ${toggle("block.removed", CHIP_ON, CHIP_OFF)}>Reject</button>
    </div>
  </article>`;

const blocksBody = `
  <p x-show="!loading && !blocks.length" class="text-sm text-muted">The rules cut no block from this session.</p>
  <div class="flex flex-col gap-2">
    <template x-for="block in blocks" :key="block.position">${blockCard}</template>
  </div>`;

const mapBody = `<div x-ref="map" data-testid="map" class="relative h-full min-h-0"></div>`;

const occupancyChips = `
  <div class="flex flex-wrap items-center gap-1.5">
    <span class="text-xs text-muted">occupancy</span>
    <template x-for="choice in occupancyChoices" :key="choice">
      <button type="button" @click="setOccupancy(choice)" :aria-pressed="occupancy === choice" x-text="choice"
        ${toggle("occupancy === choice", CHIP_ON, CHIP_OFF)}></button>
    </template>
  </div>`;

const playbackCard = playbackBody([["time", "time"], ["lab frame", "frame"], ["speed", "speed"], ["lights", "lights"]], occupancyChips);

const reviewBody = `
  <div class="flex flex-col gap-2">
    <p class="text-xs text-muted" x-text="marksLine"></p>
    <div class="flex flex-wrap gap-2">
      <button type="button" @click="mark('in')" :disabled="loading" class="${BUTTON}">Mark in</button>
      <button type="button" @click="mark('out')" :disabled="loading" class="${BUTTON}">Mark out</button>
      <button type="button" @click="act('new-block')" :disabled="!hasRange" class="${BUTTON}">New block from marks</button>
    </div>
    <div class="flex flex-wrap gap-2">
      <button type="button" @click="act('start-to-cursor')" :disabled="!hasSelection" class="${BUTTON}">Start to cursor</button>
      <button type="button" @click="act('end-to-cursor')" :disabled="!hasSelection" class="${BUTTON}">End to cursor</button>
      <button type="button" @click="act('split')" :disabled="!hasSelection" class="${BUTTON}">Split at cursor</button>
    </div>
    <div class="flex items-center gap-2">
      <button type="button" @click="act('flag')" :disabled="runNow === null" class="${BUTTON}" x-text="runFlagged ? 'Unflag run' : 'Flag run'"></button>
      <span class="text-xs text-muted" x-text="runLine"></span>
    </div>
    <textarea x-model="notes" rows="2" placeholder="Notes on the session" aria-label="Notes on the session" class="${INPUT} resize-none"></textarea>
  </div>`;

const timelineActions = `
  <button type="button" @click="zoomAll()" :disabled="loading" class="${BUTTON}">Zoom all</button>
  <button type="button" @click="zoomIn()" :disabled="loading" class="${BUTTON}">Zoom in</button>
  <button type="button" @click="zoomOut()" :disabled="loading" class="${BUTTON}">Zoom out</button>
  <button type="button" @click="fitBlock()" :disabled="!hasSelection" class="${BUTTON}">Fit block</button>
  ${helpPopover("About the timeline", TIMELINE_HELP)}`;

const timelineBody = `
  <div class="flex h-full min-h-0 flex-col gap-2">
    <div class="flex flex-wrap items-center gap-1.5">
      <template x-for="layer in layerList" :key="layer.key">
        <button type="button" @click="toggleLayer(layer.key)" :aria-pressed="layers[layer.key]" class="inline-flex items-center gap-1.5"
          ${toggle("layers[layer.key]", CHIP_ON, CHIP_OFF)}>
          <span class="size-2 rounded-full border border-line" :style="{ background: layer.colour }"></span><span x-text="layer.label"></span>
        </button>
      </template>
      <span class="ml-auto text-xs text-muted">showing <span data-testid="shown" class="tabular-nums text-ink" x-text="shown"></span></span>
    </div>
    <div x-ref="timeline" data-testid="timeline" class="relative min-h-0 flex-1 overflow-hidden"></div>
  </div>`;

const mapTitle = `Map <span class="normal-case" x-text="mapTitle"></span>`;

/** The Replay page's cards in a grid of three rows: the session and its summary, the blocks with the map, the playback and the review, the timeline. */
export const replayGrid = `
  <div x-data="replayPage" @mousedown="$event.target.closest('button') && $event.preventDefault()"
    class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,4fr)_minmax(0,3fr)] gap-4">
    ${card("Session", sessionBody, "col-span-5", sessionActions)}
    ${card("Summary", summaryBody, "col-span-7")}
    ${card("Blocks", blocksBody, "col-span-2", `<button type="button" @click="act('accept-all')" :disabled="loading" class="${BUTTON}">Accept all</button>`)}
    ${card(mapTitle, mapBody, "col-span-4", helpPopover("About the map", MAP_HELP))}
    ${card("Playback", playbackCard, "col-span-3")}
    ${card("Review", reviewBody, "col-span-3")}
    ${card("Timeline", timelineBody, "col-span-12", timelineActions)}
  </div>`;
