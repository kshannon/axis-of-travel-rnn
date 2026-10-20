import { card } from "../ui/card";
import { helpPopover } from "../ui/help";
import { BUTTON_PRIMARY, CHIP_ACCENT, CHIP_MUTED, disabledWhy, FIELD, INPUT, SEGMENT, SEGMENTS, TABLE, TD, TH } from "../ui/style";
import { SIDES } from "./quiz-view";

const QUIZ_HELP = `
  <p>Each pair is one real block from the set's source sessions and one synthetic block of the set, of the same kind, in a random order. Each side is drawn as it is on the Blocks page: the environment, the whole path as a thin line, the last 2 s as a trail coloured by speed, the red dot and heading arrow, and under it the speed trace alone. Nothing else is shown, since ids, runs or phases would give the sides away.</p>
  <p class="mt-2">Play runs both sides together from the start, the shorter one holds its last frame. Space, left and right work as on Replay. Say which side is real, the server reveals it and records your guess with the set, and the tally is every guess made against the set.</p>`;

const NO_SET = "No synthetic set yet. Generate one on the Synthetic page.";

const chooser = (label: string, model: string, choices: string, change: string) => `
  <label class="${FIELD}">
    <span>${label}</span>
    <select x-model="${model}" ${change ? `@change="${change}"` : ""} aria-label="${label}" class="${INPUT} w-auto max-w-md">
      <template x-for="choice in ${choices}" :key="choice.value"><option :value="choice.value" :selected="choice.value === ${model}" x-text="choice.label"></option></template>
    </select>
  </label>`;

const playback = `
  <div class="flex items-center gap-3">
    <button type="button" @click="togglePlay()" ${disabledWhy("!loaded", "open a pair first", "Play or pause both sides")} class="${BUTTON_PRIMARY} w-24" x-text="playing ? 'Pause' : 'Play'"></button>
    <div class="flex items-center gap-2">
      <span class="text-xs text-muted">speed</span>
      <div role="group" aria-label="Playback speed" class="${SEGMENTS}">
        <button type="button" @click="changeSpeed(-1); $el.blur()" ${disabledWhy("!loaded || speedIndex === 0", "already the slowest speed", "Play slower")} aria-label="Slower" class="${SEGMENT}">&minus;</button>
        <span data-testid="speed-value" title="Playback speed" class="w-14 bg-page px-2.5 py-1.5 text-center text-sm tabular-nums text-ink" x-text="speedLabel"></span>
        <button type="button" @click="changeSpeed(1); $el.blur()" ${disabledWhy("!loaded || speedIndex === speeds.length - 1", "already the fastest speed", "Play faster")} aria-label="Faster" class="${SEGMENT}">+</button>
      </div>
    </div>
    <span class="text-xs text-muted">time <span data-testid="time" class="tabular-nums text-ink" x-text="time"></span></span>
  </div>`;

const tallyTable = `
  <table class="${TABLE} text-xs">
    <thead><tr><th class="${TH}">By</th><th class="${TH} text-right">Answered</th><th class="${TH} text-right">Right</th><th class="${TH} text-right">Share</th></tr></thead>
    <tbody>
      <template x-for="row in tallyRows" :key="row.by">
        <tr class="border-t border-line">
          <td class="${TD}" x-text="row.by"></td>
          <td class="${TD} text-right tabular-nums" x-text="row.answered"></td>
          <td class="${TD} text-right tabular-nums" x-text="row.right"></td>
          <td class="${TD} text-right tabular-nums" x-text="row.share"></td>
        </tr>
      </template>
    </tbody>
  </table>`;

const pairBody = `
  <div class="flex h-full flex-col gap-3 text-sm">
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Reading the sets</p>
    <p x-show="!loading && !error && !sets.length" class="text-sm text-muted">${NO_SET}</p>
    <div x-show="sets.length" class="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
      <div class="flex flex-col gap-3">
        <div class="flex flex-wrap items-end gap-3">
          ${chooser("Set", "setId", "sets", "changeSet()")}
          ${chooser("Kind", "kind", "kinds", "")}
          <div class="flex items-center gap-3">
            <button type="button" @click="newPair()" :disabled="newPairBlocked !== ''" :title="newPairBlocked || 'Open a new pair of the set'" class="${BUTTON_PRIMARY}"
              x-text="phase === 'loading' ? 'Reading' : 'New pair'"></button>
            <span x-show="newPairBlocked" class="text-xs text-muted" x-text="newPairBlocked"></span>
          </div>
        </div>
        ${playback}
      </div>
      <div class="flex min-w-64 flex-col gap-1">
        <p data-testid="tally" class="text-sm" x-text="tallyText"></p>
        <div x-show="tallyRows.length">${tallyTable}</div>
      </div>
    </div>
  </div>`;

const pairActions = `
  <span x-show="phase !== 'empty'" data-testid="pair-kind" class="${CHIP_MUTED}" x-text="pairKind"></span>
  ${helpPopover("About the quiz", QUIZ_HELP)}`;

/** A side's card body: its map over its speed trace, the same on both sides. */
const sideBody = (side: string) => `
  <div class="flex h-full min-h-0 flex-col gap-2">
    <div x-ref="${side}Map" data-testid="map-${side}" class="relative min-h-0 flex-1"></div>
    <div x-ref="${side}Lanes" data-testid="lanes-${side}" class="relative h-20 shrink-0 overflow-hidden"></div>
  </div>`;

const sideActions = (side: string) => `
  <span x-show="chips.${side}" data-testid="chip-${side}" :class="chips.${side} === 'real' ? '${CHIP_ACCENT}' : '${CHIP_MUTED}'" x-text="chips.${side}"></span>`;

const answerBody = `
  <div class="flex flex-wrap items-center gap-4">
    ${SIDES.map((side) => `<button type="button" @click="guess('${side}')" :disabled="guessBlocked !== ''" :title="guessBlocked || 'The ${side} block is the real one'" class="${BUTTON_PRIMARY}">${side[0].toUpperCase()}${side.slice(1)} is real</button>`).join("")}
    <p x-show="verdict" data-testid="verdict" :class="correct ? 'text-ok' : 'text-bad'" class="text-sm" x-text="verdict"></p>
    <p x-show="!verdict && phase === 'open'" class="text-sm text-muted">Watch both sides, then say which one is the real rat.</p>
  </div>`;

/** The quiz page: the set and kind to draw a pair from with the shared playback and the tally, the two sides as maps over their speed traces, and the answer with its reveal. */
export const quizRoot = `
  <div x-data="quizPage" @mousedown="$event.target.closest('button') && $event.preventDefault()" class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,1fr)_auto] gap-4">
    ${card("Pair", pairBody, "col-span-12", pairActions)}
    ${card("Left", sideBody("left"), "col-span-6", sideActions("left"))}
    ${card("Right", sideBody("right"), "col-span-6", sideActions("right"))}
    ${card("Which is real", answerBody, "col-span-12")}
  </div>`;
