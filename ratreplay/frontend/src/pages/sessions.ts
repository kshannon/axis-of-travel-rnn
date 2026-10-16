import Alpine from "alpinejs";
import { errorText, getSession, listSessions } from "../api/client";
import type { SessionHeader, SessionRow } from "../api/types";
import { sourceStore } from "../state/source";
import { card, pageGrid } from "../ui/card";
import { sourceGate } from "../ui/gate";
import { BUTTON, BUTTON_PRIMARY, INPUT, TABLE, TD, TH } from "../ui/style";
import { toast } from "../ui/toast";
import type { Page } from "./page";
import { clickHeader, COLUMNS, filterRows, reviewText, sessionFacts, sortRows } from "./sessions-rows";
import type { Sort } from "./sessions-rows";

const REPLAY_HASH = "#/replay";
const SECONDS_PER_MINUTE = 60;

const details = `
  <td colspan="${COLUMNS.length}" class="bg-page/60 px-4 py-3">
    <div class="grid grid-cols-2 gap-6 text-xs">
      <div class="flex flex-col gap-3">
        <table class="${TABLE} text-xs">
          <thead><tr>
            <th class="${TH}">Epoch</th><th class="${TH}">Environment</th><th class="${TH}">Condition</th>
            <th class="${TH}">Frames</th><th class="${TH}">Minutes</th>
          </tr></thead>
          <tbody>
            <template x-for="epoch in row.epochs" :key="epoch.epoch">
              <tr>
                <td class="${TD}" x-text="epoch.epoch"></td><td class="${TD}" x-text="epoch.environment"></td>
                <td class="${TD}" x-text="epoch.condition"></td>
                <td class="${TD} tabular-nums" x-text="epoch.frame_start + ' to ' + epoch.frame_end"></td>
                <td class="${TD} tabular-nums" x-text="(epoch.duration_s / ${SECONDS_PER_MINUTE}).toFixed(1)"></td>
              </tr>
            </template>
          </tbody>
        </table>
        <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <template x-for="fact in facts(row)" :key="fact.label">
            <div class="contents"><dt class="text-muted" x-text="fact.label"></dt><dd x-text="fact.value"></dd></div>
          </template>
        </dl>
        <p x-show="detailsError" x-text="detailsError" class="text-bad"></p>
      </div>
      <div class="flex flex-col gap-3">
        <div>
          <h3 class="mb-1 font-medium">Automatic blocks</h3>
          <p x-show="!header" class="text-muted">Loading</p>
          <p x-show="header && !header.blocks.length" class="text-muted">The processor builds none from this session.</p>
          <ul class="space-y-0.5">
            <template x-for="block in (header ? header.blocks : [])" :key="block.block_id">
              <li class="tabular-nums">
                <span x-text="block.block_id.replace(row.session_id + '_', '')"></span>,
                frames <span x-text="block.frame_start + ' to ' + block.frame_end"></span>,
                <span x-text="block.duration_s.toFixed(0)"></span> s
              </li>
            </template>
          </ul>
        </div>
        <div>
          <h3 class="mb-1 font-medium">Review</h3>
          <p x-text="reviewOf(row)"></p>
          <p x-show="row.notes" class="mt-1 whitespace-pre-wrap text-muted" x-text="row.notes"></p>
        </div>
        <button type="button" @click="openInReplay(row)" class="${BUTTON_PRIMARY} self-start">Open in replay</button>
      </div>
    </div>
  </td>`;

const sessionsTable = `
  <div class="flex h-full flex-col gap-3">
    <div class="flex items-center gap-3">
      <input type="search" x-model="filter" aria-label="Filter sessions" placeholder="Filter by session id or rat" class="${INPUT} max-w-xs" />
      <span class="text-sm text-muted" x-text="summary"></span>
      <button type="button" x-show="sort" @click="sort = null" class="${BUTTON}">Dataset order</button>
    </div>
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Loading the sessions</p>
    <p x-show="!loading && !error && !rows.length" class="text-sm text-muted">This source has no session with an arena or track epoch.</p>
    <div x-show="rows.length" class="min-h-0 flex-1 overflow-auto">
      <table class="${TABLE}">
        <thead class="sticky top-0 z-10 bg-card">
          <tr>
            <template x-for="column in columns" :key="column.key">
              <th class="${TH}" :class="column.numeric ? 'text-right' : ''">
                <button type="button" @click="sortBy(column.key)" class="uppercase tracking-wide hover:text-ink">
                  <span x-text="column.label"></span><span x-text="arrow(column.key)"></span>
                </button>
              </th>
            </template>
          </tr>
        </thead>
        <template x-for="row in shown" :key="row.session_id">
          <tbody class="border-t border-line">
            <tr @click="toggle(row)" class="cursor-pointer hover:bg-ink/5" :class="row.in_dataset ? '' : 'text-muted'" :title="row.session_id">
              <template x-for="column in columns" :key="column.key">
                <td class="${TD} whitespace-nowrap" :class="column.numeric ? 'text-right tabular-nums' : ''" x-text="column.text(row)"></td>
              </template>
            </tr>
            <template x-if="openId === row.session_id"><tr>${details}</tr></template>
          </tbody>
        </template>
      </table>
    </div>
  </div>`;

function registerSessions(): void {
  Alpine.data("sessionsPage", () => ({
    rows: [] as SessionRow[],
    loading: true,
    error: "",
    filter: "",
    sort: null as Sort | null,
    openId: "",
    header: null as SessionHeader | null,
    detailsError: "",
    columns: COLUMNS,

    get shown() {
      return sortRows(filterRows(this.rows, this.filter), this.sort);
    },
    get summary() {
      const inDataset = this.rows.filter((row) => row.in_dataset).length;
      return `${this.shown.length} of ${this.rows.length} sessions, ${inDataset} in the dataset`;
    },

    async init() {
      try {
        this.rows = await listSessions(sourceStore().id);
      } catch (error) {
        this.error = errorText(error);
      }
      this.loading = false;
    },
    sortBy(key: string) {
      this.sort = clickHeader(this.sort, key);
    },
    arrow(key: string) {
      return this.sort?.key === key ? (this.sort.descending ? " ↓" : " ↑") : "";
    },
    async toggle(row: SessionRow) {
      this.header = null;
      this.detailsError = "";
      if (this.openId === row.session_id) {
        this.openId = "";
        return;
      }
      this.openId = row.session_id;
      try {
        const header = await getSession(sourceStore().id, row.session_id);
        if (this.openId === row.session_id) this.header = header;
      } catch (error) {
        if (this.openId === row.session_id) this.detailsError = errorText(error);
      }
    },
    facts(row: SessionRow) {
      return sessionFacts(row, this.header);
    },
    reviewOf: reviewText,
    openInReplay(row: SessionRow) {
      sourceStore().openSession(row.session_id);
      toast.success(`Opened ${row.session_id} in the replay`);
      location.hash = REPLAY_HASH;
    },
  }));
}

export const sessionsPage: Page = {
  id: "sessions",
  title: "Sessions",
  html: pageGrid(card("Sessions", sourceGate(`<div x-data="sessionsPage" class="h-full">${sessionsTable}</div>`, "transformed"))),
  register: registerSessions,
};
