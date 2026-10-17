import Alpine from "alpinejs";
import { errorText, getSession, listSessions } from "../api/client";
import type { SessionHeader, SessionRow } from "../api/types";
import { Workspace } from "../session/workspace";
import { sourceStore } from "../state/source";
import { card, pageGrid } from "../ui/card";
import { factsList } from "../ui/facts";
import { sourceGate } from "../ui/gate";
import { BUTTON, BUTTON_DANGER, BUTTON_PRIMARY, INPUT, TABLE, TD, TH } from "../ui/style";
import { clickHeader, sortableTable, sortArrow, sortRows } from "../ui/table";
import type { Sort } from "../ui/table";
import { toast } from "../ui/toast";
import type { Page } from "./page";
import { COLUMNS, filterRows, reviewText, sessionFacts, totalsLine } from "./sessions-rows";

const REPLAY_HASH = "#/replay";
const SECONDS_PER_MINUTE = 60;

const openButtons = `
  <template x-if="!confirming">
    <button type="button" @click="openInReplay(row)" class="${BUTTON_PRIMARY} self-start">Open in replay</button>
  </template>
  <template x-if="confirming">
    <div class="flex flex-col items-start gap-2">
      <p class="text-warn">The edits to <span x-text="confirming"></span> in the replay are not saved and would be lost.</p>
      <div class="flex gap-2">
        <button type="button" @click="openInReplay(row, true)" class="${BUTTON_DANGER}">Open and drop them</button>
        <button type="button" @click="confirming = ''" class="${BUTTON}">Cancel</button>
      </div>
    </div>
  </template>`;

const details = `
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
        ${factsList("facts(row)")}
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
        ${openButtons}
      </div>
    </div>`;

const sessionsTable = `
  <div class="flex h-full flex-col gap-3">
    <div class="flex items-center gap-3">
      <input type="search" x-model="filter" aria-label="Filter sessions" placeholder="Filter by session id or rat" class="${INPUT} max-w-xs" />
      <span class="text-sm text-muted" x-text="summary"></span>
      <button type="button" x-show="sort" @click="sort = null" class="${BUTTON}">Dataset order</button>
    </div>
    <p data-testid="totals" x-show="rows.length" x-text="totals" class="text-sm"></p>
    <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
    <p x-show="loading" class="text-sm text-muted">Loading the sessions</p>
    <p x-show="!loading && !error && !rows.length" class="text-sm text-muted">This source has no session with an arena or track epoch.</p>
    <template x-if="rows.length">
      ${sortableTable({ rowKey: "row.session_id", rowTitle: "row.session_id", rowClass: "row.in_dataset ? '' : 'text-muted'", details })}
    </template>
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
    confirming: "",
    columns: COLUMNS,

    get shown() {
      return sortRows(filterRows(this.rows, this.filter), COLUMNS, this.sort);
    },
    get summary() {
      const inDataset = this.rows.filter((row) => row.in_dataset).length;
      return `${this.shown.length} of ${this.rows.length} sessions, ${inDataset} in the dataset`;
    },
    get totals() {
      return totalsLine(this.rows);
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
      return sortArrow(this.sort, key);
    },
    async toggle(row: SessionRow) {
      this.header = null;
      this.detailsError = "";
      this.confirming = "";
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
    /** Open the session in the replay, asking first when the session open there has edits that are not saved. */
    openInReplay(row: SessionRow, drop = false) {
      const unsaved = Workspace.unsavedWhenOpening(sourceStore().id, row.session_id);
      if (unsaved && !drop) {
        this.confirming = unsaved.header.session_id;
        return;
      }
      this.confirming = "";
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
