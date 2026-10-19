import { card } from "../ui/card";
import { BUTTON, BUTTON_DANGER, BUTTON_PRIMARY, CHIP_MUTED, FIELD, INPUT, TABLE, TD, TH } from "../ui/style";

const GENERATE_HINT = "Generate a synthetic set from the chosen sessions' built blocks";
const SOURCES_NOTE = "The recipe is fitted to the built blocks of the chosen sessions, the camera and environments are the first one's.";
const COMPARE_NOTE = "Compare a set, with its button or a click on its row, to see its recipe beside the real one it was made from.";

const SET_COLUMNS: readonly (readonly [key: string, label: string])[] = [
  ["set_id", "Set"], ["created", "Created"], ["by", "By"], ["sources", "Sources"], ["seed", "Seed"], ["minutes", "Minutes per kind"], ["blocks", "Blocks"], ["guesses", "Guesses"],
];

const setsTable = `
  <table class="${TABLE}">
    <thead class="sticky top-0 z-10 bg-card">
      <tr>${SET_COLUMNS.map(([, label]) => `<th class="${TH}">${label}</th>`).join("")}<th class="${TH}"></th></tr>
    </thead>
    <tbody>
      <template x-for="line in lines" :key="line.set_id">
        <tr @click="choose(line.set_id)" :class="line.set_id === chosen ? 'bg-accent/10' : 'hover:bg-ink/5'" :title="line.set_id" :aria-selected="line.set_id === chosen" class="cursor-pointer border-t border-line">
          ${SET_COLUMNS.map(([key]) => `<td class="${TD} whitespace-nowrap${key === "set_id" ? " font-mono text-xs" : ""}" x-text="line.${key}"></td>`).join("")}
          <td class="${TD} text-right">
            <div class="flex justify-end gap-2">
              <button type="button" @click.stop="choose(line.set_id)" :aria-label="'Compare ' + line.set_id" class="${BUTTON}">Compare</button>
              <button type="button" @click.stop="remove(line.set_id)" :disabled="busy" :aria-label="'Delete ' + line.set_id" class="${BUTTON_DANGER}">Delete</button>
            </div>
          </td>
        </tr>
      </template>
    </tbody>
  </table>`;

const setsBody = `
  <div class="flex h-full flex-col gap-3">
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Reading the sets</p>
    <p x-show="!loading && !error && !lines.length" class="text-sm text-muted">No synthetic set yet. Generate one from the built sessions.</p>
    <template x-if="lines.length">
      <div class="flex min-h-0 flex-col gap-2">
        <p class="text-xs text-muted">${COMPARE_NOTE}</p>
        <div class="max-h-60 overflow-auto">${setsTable}</div>
      </div>
    </template>
  </div>`;

const setsActions = `<span data-testid="set-count" class="text-sm text-muted" x-text="lines.length + (lines.length === 1 ? ' set' : ' sets')"></span>`;

const minutesField = (kind: string) => `
  <label class="${FIELD}">
    <span>${kind} minutes</span>
    <input type="number" min="0" step="1" x-model.number="minutes.${kind}" aria-label="${kind} minutes" class="${INPUT} w-24" />
  </label>`;

const generateBody = `
  <div class="flex flex-col gap-3 text-sm">
    <div class="flex flex-col gap-1">
      <p class="text-xs text-muted">Sources, the built sessions. ${SOURCES_NOTE}</p>
      <p x-show="!sessions.length" class="text-sm text-muted">No session has built blocks yet. Save blocks in the Replay first.</p>
      <div data-testid="sources" class="flex flex-wrap gap-x-4 gap-y-1">
        <template x-for="session in sessions" :key="session.session_id">
          <label class="inline-flex cursor-pointer items-center gap-1.5">
            <input type="checkbox" :value="session.session_id" x-model="sources" class="accent-accent" />
            <span class="font-mono text-xs" x-text="session.session_id"></span>
            <span class="${CHIP_MUTED}" x-text="session.built + (session.built === 1 ? ' block' : ' blocks')"></span>
          </label>
        </template>
      </div>
    </div>
    <div class="flex flex-wrap items-end gap-3">
      <label class="${FIELD}">
        <span>seed</span>
        <input type="number" min="0" step="1" x-model.number="seed" aria-label="Seed" class="${INPUT} w-28" />
      </label>
      ${minutesField("arena")}
      ${minutesField("track")}
    </div>
    <div class="flex flex-wrap items-center gap-3">
      <button type="button" @click="generate()" :disabled="busy || blocked !== ''" :title="blocked || '${GENERATE_HINT}'" class="${BUTTON_PRIMARY}"
        x-text="generating ? 'Generating' : 'Generate'"></button>
      <span x-show="blocked" class="text-xs text-muted" x-text="blocked"></span>
    </div>
    <p class="text-xs text-muted">Window settings recorded with the set: <span x-text="settingsLine"></span>. <a href="#/settings" class="text-accent underline">Change on the Settings page</a>.</p>
  </div>`;

const compareTable = `
  <section class="flex min-w-0 flex-col gap-2">
    <h3 class="text-sm font-medium"><span x-text="table.kind"></span><span x-show="table.note" class="ml-2 text-xs font-normal text-muted" x-text="table.note"></span></h3>
    <table class="${TABLE} text-xs">
      <thead class="sticky top-0 z-10 bg-card"><tr><th class="${TH}">Statistic</th><th class="${TH} text-right">Real</th><th class="${TH} text-right">Synthetic</th></tr></thead>
      <tbody>
        <template x-for="row in table.rows" :key="row.label">
          <tr class="border-t border-line">
            <td class="${TD} whitespace-nowrap" x-text="row.label"></td>
            <td class="${TD} text-right tabular-nums" x-text="row.real"></td>
            <td class="${TD} text-right tabular-nums" x-text="row.synthetic"></td>
          </tr>
        </template>
      </tbody>
    </table>
  </section>`;

const compareBody = `
  <div class="flex h-full flex-col gap-3">
    <p x-show="!chosen" class="text-sm text-muted">Choose a set in the table to see its recipe beside the real one.</p>
    <p x-show="chosen && !header && !compareError" class="text-sm text-muted">Reading the set</p>
    <p x-show="compareError" x-text="compareError" role="alert" class="text-sm text-bad"></p>
    <template x-if="header">
      <div class="flex min-h-0 flex-col gap-3">
        <p data-testid="compare-caption" class="text-xs text-muted" x-text="caption"></p>
        <ul x-show="header.warnings.length" class="list-disc space-y-0.5 pl-5 text-xs text-warn">
          <template x-for="warning in header.warnings"><li x-text="warning"></li></template>
        </ul>
        <div data-testid="comparison" class="grid min-h-0 flex-1 grid-cols-2 items-start gap-6 overflow-auto">
          <template x-for="table in tables" :key="table.kind">${compareTable}</template>
        </div>
      </div>
    </template>
  </div>`;

const compareActions = `<span x-show="header" class="${CHIP_MUTED} font-mono" x-text="chosen"></span>`;

/** The Synthetic page: the sets with Compare and Delete, as tall as their rows up to a few, the Generate form over the built sessions, and the chosen set's recipe beside the real one in the room left. */
export const syntheticRoot = `
  <div x-data="syntheticPage" class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,1fr)] gap-4">
    ${card("Sets", setsBody, "col-span-12", setsActions)}
    ${card("Generate", generateBody, "col-span-4")}
    ${card("Comparison", compareBody, "col-span-8", compareActions)}
  </div>`;
