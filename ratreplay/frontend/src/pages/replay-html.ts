import { card } from "../ui/card";
import { helpPopover } from "../ui/help";
import { BUTTON, BUTTON_ICON, BUTTON_PRIMARY, CHIP_ON, CHIP_OFF, disabledWhy, GROUP_LABEL, INPUT, KBD, LAYER_TOGGLE, SEGMENT, SEGMENT_PRIMARY, SEGMENTS, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { EXCLUDED_SAVE } from "./exclusion-view";
import { playbackBody } from "./playback-html";

const MAP_HELP = `
  <p>The room in metres, north up, the same frame for every epoch. The checkboxes under the title switch each layer on or off. Occupancy is where the animal spent time in an epoch, darker is more. Geometry is the environment of the epoch: the walls, the boundary or circle of an arena, the dotted centerline and the reward sites. Arena and track choose which epochs are drawn, and following the cursor's epoch draws only the epoch under the cursor.</p>
  <p class="mt-2">The trail is the last 2 s of the path coloured by speed in m/s. The red dot is the cursor's position and the red arrow the head direction after the fill and the LED offset. The thin line is the path of what is selected on the timeline. Positions outside the room are drawn outside the outline, where a registration problem shows, and are counted in the Session card.</p>`;

const TIMELINE_HELP = `
  <p>One time axis in minutes of recording. A pause in the recording is dead time between two frames, so it is a gap across every lane, with no time in it, and nothing is drawn across it. The purple line is the cursor, the frame the playback is at. Session: the epochs. Runs: the lab's runs, dark blue outbound and light blue return, hatched when dirty, outlined red when flagged. Frames: what cut the session and what the review looks at, each layer a checkbox in the row under the lanes with its colour after the word, hover one for what it means. Tracking lost is the striped violet bar. Blocks: the blocks as they stand after the edits, coloured by status, a hover tells their windows and verdict.</p>
  <p class="mt-2">A block is cut at every pause, jump, gap and epoch bound, a margin is trimmed beside each cut and a piece that is too short is dropped. The cuts, margins and fills are the engine's, the same call that builds the blocks, so a confirmed block is the block it builds.</p>
  <p class="mt-2">Click an epoch, a run, a block or a frame of the frames lane to select it, and click it again or press escape to let go. Click empty space in a lane to move the cursor. The wheel zooms and a drag pans. The buttons above the lanes act on the cursor, the marks and the selected block.</p>`;

const toggle = (pressed: string, on: string, off: string) => `:class="${pressed} ? '${on}' : '${off}'"`;

const sessionActions = `
  <button type="button" @click="save()" :disabled="loading || busy || !inDataset || excluded"
    :title="loading ? 'session still loading' : busy ? 'wait, still working' : excluded ? '${EXCLUDED_SAVE}' : inDataset ? 'Save the blocks and the review' : 'Not in the dataset: ' + reason" class="${BUTTON_PRIMARY}">Save blocks</button>
  <button type="button" @click="changeExclusion()" :disabled="loading || busy" :title="loading ? 'session still loading' : busy ? 'wait, still working' : ''" class="${BUTTON}"
    x-text="excluded ? 'Include' : 'Exclude'"></button>`;

const stepButton = (step: "previous" | "next", glyph: string) => `
  <button type="button" @click="step('${step}')" :disabled="!!stepWhy('${step}')" :title="stepWhy('${step}') || stepTitle('${step}')" aria-label="${step === "previous" ? "Previous" : "Next"} session" class="${BUTTON_ICON}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="size-4"><path d="${glyph}" /></svg>
  </button>`;

const pickerRow = `
  <li>
    <button type="button" @click="openFromList(row.session_id)" :aria-current="row.session_id === sessionId" :title="row.in_dataset ? row.session_id : row.session_id + ', not in the dataset: ' + row.reason"
      class="flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-ink/10" :class="[row.session_id === sessionId ? 'bg-accent/10' : '', row.in_dataset ? '' : 'text-muted']">
      <span class="w-52 shrink-0 truncate font-mono" x-text="row.session_id"></span>
      <span class="w-24 shrink-0 whitespace-nowrap tabular-nums text-muted" x-text="row.date"></span>
      <span class="w-14 shrink-0 text-muted" x-text="row.subject_id"></span>
      <span class="flex min-w-0 flex-1 flex-wrap gap-1"><template x-for="chip in chipsOf(row)" :key="chip.text"><span :class="chip.chip" :title="chip.title" class="whitespace-nowrap" x-text="chip.text"></span></template></span>
    </button>
  </li>`;

// The session id is a button that opens the list of the sessions index under it, fixed so the card does not clip it, with the arrows to the sessions before and after beside it.
const sessionPicker = `
  <div class="flex items-center gap-2" @click.outside="closePicker()" @keydown.escape.stop="closePicker()">
    ${stepButton("previous", "M15 18l-6-6 6-6")}
    <button type="button" x-ref="pickerButton" @click="togglePicker()" :aria-expanded="pickerOpen" title="Choose another session" class="flex min-w-0 items-center gap-2 rounded-md px-2 py-0.5 hover:bg-ink/10">
      <span data-testid="session-id" class="truncate font-mono text-xl font-semibold" x-text="sessionId"></span>
      <span class="text-xs text-muted" aria-hidden="true">&#9662;</span>
    </button>
    ${stepButton("next", "M9 18l6-6-6-6")}
    <div x-show="pickerOpen" x-cloak data-testid="picker" class="fixed z-30 w-[38rem] rounded-lg border border-line bg-card p-2 shadow-lg" :style="{ top: pickerTop + 'px', left: pickerLeft + 'px' }">
      <input x-ref="pickerFilter" type="search" x-model="filter" @keydown.enter.prevent="openFirst()" aria-label="Find a session" placeholder="Filter by session id or rat, enter opens the first" class="${INPUT}" />
      <p class="mt-1 px-1 text-xs" :class="indexError ? 'text-bad' : 'text-muted'" x-text="listedText"></p>
      <ul class="mt-1 max-h-72 overflow-auto">
        <template x-for="row in listed" :key="row.session_id">${pickerRow}</template>
      </ul>
    </div>
  </div>`;

// The status header: the session id large as a picker, the facts under it, then where the review stands as one strong chip with the warnings beside it, and what is selected.
const sessionBody = `
  <div class="flex flex-col gap-2">
    ${sessionPicker}
    <p class="text-sm" x-text="facts"></p>
    <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span data-testid="state" :class="status.state.chip" :title="status.state.title" x-text="status.state.text"></span>
      <template x-for="flag in status.flags" :key="flag.text">
        <span data-testid="flag" :class="flag.chip" :title="flag.title" x-text="flag.text"></span>
      </template>
      <p class="ml-auto text-sm"><span class="text-muted">selected </span><span data-testid="selection" x-text="selectionLine"></span></p>
    </div>
    <ul data-testid="notices" x-show="notices.length" class="max-h-12 space-y-0.5 overflow-auto text-xs">
      <template x-for="notice in notices"><li :class="notice.tone" x-text="notice.text"></li></template>
    </ul>
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
    <p x-show="block.heading" class="text-muted" x-text="block.heading"></p>
    <p x-show="block.verdict" data-testid="verdict" :class="block.ok ? 'text-ok' : 'text-warn'" x-text="block.verdict"></p>
    <template x-for="problem in block.problems"><p class="text-bad" x-text="problem"></p></template>
    <div class="mt-1.5 flex gap-1.5">
      <button type="button" @click.stop="act('accept', block.position)" ${disabledWhy("!block.acceptable", "an edited or removed block cannot be accepted", "Accept this block")} :aria-pressed="block.accepted"
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

const checkbox = (model: string, label: string, title = "") => `
  <label class="inline-flex cursor-pointer items-center gap-1.5" title="${title}">
    <input type="checkbox" x-model="${model}" @change="mapLayersChanged()" class="accent-accent" /><span>${label}</span>
  </label>`;

// A layer each on its own: the occupancy, the geometry, the epoch kinds of the session, the trail, and whether only the epoch under the cursor is drawn.
const mapBody = `
  <div class="flex h-full min-h-0 flex-col gap-2">
    <div role="group" aria-label="Map layers" class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      ${checkbox("mapLayers.occupancy", "occupancy", "Where the animal spent time, darker is more")}
      ${checkbox("mapLayers.geometry", "geometry", "The walls, boundary, centerline and reward sites of the environment")}
      <template x-for="kind in epochKinds" :key="kind">
        <label class="inline-flex cursor-pointer items-center gap-1.5" :title="'Draw the ' + kind + ' epoch'">
          <input type="checkbox" x-model="mapLayers.kinds[kind]" @change="mapLayersChanged()" class="accent-accent" /><span x-text="kind"></span>
        </label>
      </template>
      ${checkbox("mapLayers.trail", "trail", "The last 2 s of the path coloured by speed, with the speed colours")}
      ${checkbox("mapLayers.follow", "follow the cursor's epoch", "Draw only the epoch under the cursor")}
    </div>
    <div x-ref="map" data-testid="map" class="relative min-h-0 flex-1"></div>
  </div>`;

// Under the playback: the run the flag acts on and the notes of the session.
const flagAndNotes = `
  <div class="flex items-center gap-2">
    <button type="button" @click="act('flag')" ${disabledWhy("runNow === null", "select or hover a run", "Flag or unflag the run under the cursor")} class="${BUTTON}" x-text="runFlagged ? 'Unflag run' : 'Flag run'"></button>
    <span class="min-w-0 truncate text-xs text-muted" x-text="runLine"></span>
  </div>
  <textarea x-model="notes" rows="2" placeholder="Notes on the session" aria-label="Notes on the session" class="${INPUT} min-h-10 flex-1 resize-none"></textarea>`;

const playbackCard = playbackBody([["time", "time"], ["lab frame", "frame"], ["speed", "speed"], ["lights", "lights"]], flagAndNotes, "grid-cols-4");

// The zoom controls as one block of segments.
const zoomBlock = `
  <div role="group" aria-label="Zoom" class="${SEGMENTS}">
    <button type="button" @click="zoomAll()" ${disabledWhy("loading", "session still loading", "Show the whole session")} class="${SEGMENT}">Reset view</button>
    <button type="button" @click="zoomIn()" ${disabledWhy("loading", "session still loading", "Zoom in")} aria-label="Zoom in" class="${SEGMENT}">+</button>
    <button type="button" @click="zoomOut()" ${disabledWhy("loading", "session still loading", "Zoom out")} aria-label="Zoom out" class="${SEGMENT}">-</button>
    <button type="button" @click="fitBlock()" ${disabledWhy("!hasSelection", "select a block first", "Zoom to the selected block")} class="${SEGMENT}">Zoom to block</button>
  </div>`;

const timelineActions = `
  <span class="text-xs text-muted">showing <span data-testid="shown" class="tabular-nums text-ink" x-text="shown"></span></span>
  ${zoomBlock}
  ${helpPopover("About the timeline", TIMELINE_HELP)}`;

const group = (name: string, buttons: string) => `
  <div role="group" aria-label="${name}" class="flex shrink-0 items-center gap-2">
    <span class="${GROUP_LABEL}">${name}</span><div class="${SEGMENTS}">${buttons}</div>
  </div>`;

// The editing buttons in one row above the lanes: the marks, the cuts at the cursor, and the status of the selected block with undo and reset.
const SCROLL_X = "overflow-x-auto [scrollbar-width:thin]";

const editRow = `
  <div class="flex shrink-0 items-center gap-x-3 pb-1 ${SCROLL_X}">
    ${group("marks", `
      <button type="button" @click="mark('in')" ${disabledWhy("loading", "session still loading", "Mark the start of a range at the cursor")} class="${SEGMENT_PRIMARY}">Mark in</button>
      <button type="button" @click="mark('out')" ${disabledWhy("loading", "session still loading", "Mark the end of a range at the cursor")} class="${SEGMENT}">Mark out</button>
      <button type="button" @click="act('new-block')" ${disabledWhy("!hasRange", "no range marked", "Make a block of the marked range")} class="${SEGMENT}">New block from marks</button>`)}
    ${group("cuts", `
      <button type="button" @click="act('split')" ${disabledWhy("!hasSelection", "select a block first", "Split the selected block at the cursor")} class="${SEGMENT_PRIMARY}">Split here</button>
      <button type="button" @click="act('start-to-cursor')" ${disabledWhy("!hasSelection", "select a block first", "Move the start of the selected block to the cursor")} class="${SEGMENT}">Start here</button>
      <button type="button" @click="act('end-to-cursor')" ${disabledWhy("!hasSelection", "select a block first", "Move the end of the selected block to the cursor")} class="${SEGMENT}">End here</button>`)}
    ${group("status", `
      <button type="button" @click="act('accept')" ${disabledWhy("!hasSelection", "select a block first", "Accept the selected block, again to take it back")} class="${SEGMENT_PRIMARY}">Accept</button>
      <button type="button" @click="act('reject')" ${disabledWhy("!hasSelection", "select a block first", "Reject the selected block, which removes it, again to restore it")} class="${SEGMENT}">Reject</button>
      <button type="button" @click="undo()" ${disabledWhy("!editCount", "nothing to undo", "Take the last edit back")} class="${SEGMENT}">Undo <kbd class="${KBD}" title="press z to undo">z</kbd></button>
      <button type="button" @click="reset()" ${disabledWhy("!editCount", "no edits to clear", "Clear every edit so the blocks are automatic again. A saved review stays on disk until you save.")} class="${SEGMENT}">Reset</button>`)}
    <span x-show="hasMarks" data-testid="marks" :title="marksLine" class="min-w-0 truncate text-xs text-muted" x-text="marksLine"></span>
  </div>`;

// The layers of the frames lane in one row along the bottom, each a checkbox with its name and what it means, with the numbers of the rules the session was cut under, as its hover.
const layerRow = `
  <div aria-label="Timeline layers" role="group" class="flex shrink-0 items-center gap-x-2 pb-1 ${SCROLL_X}">
    <template x-for="layer in layerList" :key="layer.key">
      <label class="${LAYER_TOGGLE}" :title="meanings[layer.key]">
        <input type="checkbox" :checked="layers[layer.key]" @change="toggleLayer(layer.key)" class="accent-accent" />
        <span x-text="layer.label"></span><span class="size-2.5 shrink-0 rounded-full" :style="{ background: layer.colour }"></span>
      </label>
    </template>
  </div>`;

// The editing buttons above the lanes and the layers below them, the lanes across the whole card.
const timelineBody = `
  <div class="flex h-full min-h-0 flex-col gap-2">
    ${editRow}
    <div x-ref="timeline" data-testid="timeline" class="relative min-h-0 flex-1 overflow-hidden"></div>
    ${layerRow}
  </div>`;

const mapTitle = `Map <span class="normal-case" x-text="mapTitle"></span>`;

/** The Replay page's cards in a grid of three rows: the session status and its summary, the blocks with the map and the playback, the timeline with the editing buttons above the lanes and the layers below them. */
export const replayGrid = `
  <div x-data="replayPage" @mousedown="$event.target.closest('button, label, input[type=checkbox]') && $event.preventDefault()"
    class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,5fr)_minmax(0,6fr)] gap-4">
    ${card("Session", sessionBody, "col-span-5", sessionActions)}
    ${card("Summary", summaryBody, "col-span-7")}
    ${card("Blocks", blocksBody, "col-span-3", `<button type="button" @click="act('accept-all')" ${disabledWhy("loading", "session still loading", "Accept every block")} class="${BUTTON}">Accept all</button>`)}
    ${card(mapTitle, mapBody, "col-span-5", helpPopover("About the map", MAP_HELP))}
    ${card("Playback", playbackCard, "col-span-4")}
    ${card("Timeline", timelineBody, "col-span-12", timelineActions)}
  </div>`;
