import { BUTTON_PRIMARY, disabledWhy, KBD, SEGMENT, SEGMENTS, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";

const liveTile = (label: string, property: string) => `
  <div class="${TILE}"><p class="${TILE_LABEL}">${label}</p><p data-testid="tile-${property}" class="${TILE_VALUE}" x-text="${property}"></p></div>`;

/**
 * The body of a Playback card: play and pause, the speed and a live tile for each [label, property] pair, with what a
 * page adds under them. The page's Alpine data has `loading`, `playing`, `togglePlay()`, `speeds`, `speedIndex`, `speedLabel` and `changeSpeed(direction)`.
 * The tiles sit in a grid of the given Tailwind columns class, two across unless the page asks for more.
 */
export function playbackBody(tiles: readonly (readonly [label: string, property: string])[], extra = "", columns = "grid-cols-2"): string {
  return `
    <div class="flex h-full flex-col gap-2">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div class="flex items-center gap-3">
          <button type="button" @click="togglePlay()" ${disabledWhy("loading", "session still loading", "Play or pause")} class="${BUTTON_PRIMARY} w-24" x-text="playing ? 'Pause' : 'Play'"></button>
          <kbd class="${KBD}" title="press space to play or pause">space</kbd>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-muted">speed</span>
          <div role="group" aria-label="Playback speed" class="${SEGMENTS}">
            <button type="button" @click="changeSpeed(-1); $el.blur()" ${disabledWhy("speedIndex === 0", "already the slowest speed", "Play slower")} aria-label="Slower" class="${SEGMENT}">&minus;</button>
            <span data-testid="speed-value" title="Playback speed" class="w-14 bg-page px-2.5 py-1.5 text-center text-sm tabular-nums text-ink" x-text="speedLabel"></span>
            <button type="button" @click="changeSpeed(1); $el.blur()" ${disabledWhy("speedIndex === speeds.length - 1", "already the fastest speed", "Play faster")} aria-label="Faster" class="${SEGMENT}">+</button>
          </div>
        </div>
      </div>
      <div class="grid ${columns} gap-2">${tiles.map(([label, property]) => liveTile(label, property)).join("")}</div>
      ${extra}
    </div>`;
}
