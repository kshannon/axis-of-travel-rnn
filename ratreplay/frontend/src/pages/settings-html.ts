import { card } from "../ui/card";
import { BUTTON, BUTTON_PRIMARY, CHIP_MUTED, INPUT, TABLE, TD, TH } from "../ui/style";

const fieldsBody = `
  <div class="flex flex-col gap-3">
    <p x-show="loading" class="text-sm text-muted">Reading the settings</p>
    <div x-show="!loading" class="grid grid-cols-[11rem_7rem_6rem_1fr] items-center gap-x-4 gap-y-1.5">
      <template x-for="field in fields" :key="field.key">
        <div class="contents">
          <label :for="'setting-' + field.key" class="text-sm" x-text="field.label"></label>
          <input type="number" min="0" :id="'setting-' + field.key" :step="field.step" x-model.number="draft[field.key]" @change="change()" class="${INPUT}" />
          <span class="text-xs tabular-nums text-muted" x-text="'default ' + field.default"></span>
          <span class="text-xs text-muted" x-text="field.hint"></span>
        </div>
      </template>
    </div>
    <div class="flex flex-col gap-0.5">
      <p data-testid="tested" class="text-sm" x-text="triedLine"></p>
      <p data-testid="selected" class="text-xs text-muted" x-text="selectedLine"></p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button type="button" @click="select()" :disabled="!canSelect" :title="canSelect ? '' : selectBlocked" class="${BUTTON_PRIMARY}">Select these settings</button>
      <button type="button" @click="reset()" :disabled="busy || loading || isDefault" class="${BUTTON}">Reset to the defaults</button>
    </div>
  </div>`;

const rulesBody = `
  <div class="flex flex-col gap-2">
    <p class="text-xs text-muted">
      The rules are fixed in the engine. Changing one is a code change, and a Rebuild all on the <a href="#/outgoing" class="text-accent underline">Outgoing</a> page for it to reach what is built.
    </p>
    <p x-show="!rules.length" class="text-sm text-muted">Reading the rules</p>
    <table x-show="rules.length" data-testid="rules" class="${TABLE} text-xs">
      <thead class="sticky top-0 z-10 bg-card"><tr><th class="${TH}">Rule</th><th class="${TH}">Value</th><th class="${TH}">Meaning</th></tr></thead>
      <tbody>
        <template x-for="rule in rules" :key="rule.name">
          <tr class="border-t border-line">
            <td class="${TD} whitespace-nowrap font-mono" x-text="rule.name"></td>
            <td class="${TD} whitespace-nowrap tabular-nums" x-text="rule.value"></td>
            <td class="${TD} text-muted" x-text="rule.meaning"></td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>`;

const rulesActions = `<span x-show="rules.length" class="${CHIP_MUTED}" x-text="rules.length + ' rules, read only'"></span>`;

/** The Settings page: the window settings as fields with their hints and defaults, the sentence and the selection, and the engine's rules read only. */
export const settingsRoot = `
  <div x-data="settingsPage" class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,1fr)] gap-4">
    ${card("Window settings", fieldsBody, "col-span-12")}
    ${card("Rules", rulesBody, "col-span-12", rulesActions)}
  </div>`;
