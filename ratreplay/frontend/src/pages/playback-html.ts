import { BUTTON_PRIMARY, KBD, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";

const liveTile = (label: string, property: string) => `
  <div class="${TILE}"><p class="${TILE_LABEL}">${label}</p><p data-testid="tile-${property}" class="${TILE_VALUE}" x-text="${property}"></p></div>`;

/**
 * The body of a Playback card: play and pause, the speed and a live tile for each [label, property] pair, with what a
 * page adds under them. The page's Alpine data has `loading`, `playing`, `togglePlay()`, `speeds`, `speedIndex`, `speedLabel` and `setSpeed()`.
 */
export function playbackBody(tiles: readonly (readonly [label: string, property: string])[], extra = ""): string {
  return `
    <div class="flex flex-col gap-3">
      <div class="flex items-center gap-3">
        <button type="button" @click="togglePlay()" :disabled="loading" class="${BUTTON_PRIMARY} w-24" x-text="playing ? 'Pause' : 'Play'"></button>
        <kbd class="${KBD}">space</kbd>
      </div>
      <label class="flex items-center gap-2 text-xs text-muted">playback
        <input type="range" min="0" :max="speeds.length - 1" step="1" x-model.number="speedIndex" @input="setSpeed()" @change="$event.target.blur()"
          aria-label="Playback speed" class="min-w-0 flex-1 accent-accent" />
        <span class="w-9 text-right tabular-nums text-ink" x-text="speedLabel"></span>
      </label>
      <div class="grid grid-cols-2 gap-2">${tiles.map(([label, property]) => liveTile(label, property)).join("")}</div>
      ${extra}
    </div>`;
}
