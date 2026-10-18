import { card, foldedCard } from "../ui/card";
import { statusMark } from "../ui/status";
import { BUTTON, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { sortableTable } from "../ui/table";
import { compareTable, formatBody, formatChip } from "./tables-html";

const REBUILD_HINT = "Build the blocks of every reviewed session again";
const REBUILD_BLOCKED = "Needs the three folders usable and at least one review";

const writeBody = `
  <div data-testid="processed" class="flex flex-col gap-3">
    <p x-show="!view" class="text-sm text-muted">Reading the data folders</p>
    <template x-if="view">
      <div class="flex flex-col gap-3">
        <div class="grid grid-cols-[auto_auto_minmax(0,1fr)] items-center gap-x-3 text-sm">
          ${statusMark("view.status")}
          <span class="text-muted">blocks written to</span>
          <code class="min-w-0 break-all font-mono text-xs" :title="view.root" x-text="view.root"></code>
        </div>
        <p x-show="view.note" class="text-xs text-muted" x-text="view.note"></p>
        <ul x-show="view.problems.length" class="list-disc space-y-0.5 pl-5 text-xs text-bad">
          <template x-for="problem in view.problems"><li x-text="problem"></li></template>
        </ul>
        <div class="flex flex-wrap items-end gap-x-6 gap-y-2">
          <dl class="grid grid-cols-3 gap-2">
            <template x-for="entry in view.counts" :key="entry.label">
              <div class="min-w-24 ${TILE}">
                <dt class="${TILE_LABEL}" x-text="entry.label"></dt>
                <dd class="${TILE_VALUE}" x-text="entry.value"></dd>
              </div>
            </template>
          </dl>
          <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
            <template x-for="row in view.times" :key="row.label">
              <div class="contents"><dt class="text-muted" x-text="row.label"></dt><dd x-text="stamp(row.stamp)"></dd></div>
            </template>
          </dl>
        </div>
      </div>
    </template>
  </div>`;

const selectedBody = `
  <div class="flex flex-col items-start gap-2 text-sm">
    <p data-testid="selected" x-text="selectedLine || (blocked ? 'Not read while a folder has a problem' : 'Reading the selection')"></p>
    <p class="text-xs text-muted">
      <code class="font-mono">windows.json</code> is what the RNN project reads. It is chosen on the
      <a href="#/settings" class="text-accent underline">Settings</a> page.
    </p>
  </div>`;

const details = `
  <div class="grid grid-cols-2 gap-6 text-xs">
    <div class="flex flex-col gap-2">
      <p x-text="rowNote(row)"></p>
      <ul x-show="failedLines(row).length" class="list-disc space-y-0.5 pl-5 text-bad">
        <template x-for="line in failedLines(row)"><li x-text="line"></li></template>
      </ul>
    </div>
    <div x-show="row.compare.length">${compareTable("row.compare", "in use now", "built-with")}</div>
  </div>`;

const rebuildButton = `
  <button type="button" :disabled="busy || !canRebuild" :title="canRebuild ? '${REBUILD_HINT}' : '${REBUILD_BLOCKED}'" @click="rebuildAll()" class="${BUTTON}"
    x-text="rebuilding ? 'Rebuilding' : 'Rebuild all'"></button>`;

const builtBody = `
  <div class="flex h-full flex-col gap-3">
    <div class="flex flex-wrap items-center gap-3">
      ${rebuildButton}
      <span x-show="rows.length" class="text-sm text-muted" x-text="summary"></span>
      <button type="button" x-show="sort" @click="sort = null" class="${BUTTON}">Session order</button>
    </div>
    <template x-if="blocked">
      <div class="flex flex-col items-start gap-2 text-sm">
        <p x-text="blocked"></p>
        <a x-show="$store.health.problem('transformed', 'environments')" href="#/incoming" class="text-accent underline">Open the Incoming page</a>
      </div>
    </template>
    <template x-if="!blocked">
      <div class="flex h-full flex-col gap-3">
        <p x-show="error" x-text="error" role="alert" class="text-sm text-bad"></p>
        <p x-show="loading" class="text-sm text-muted">Reading what is built</p>
        <p x-show="!loading && !error && !rows.length" class="text-sm text-muted">Nothing is built and no session is reviewed yet. Saving blocks in the Replay builds a session.</p>
        <template x-if="rows.length">
          ${sortableTable({ rowKey: "row.session_id", rowTitle: "row.session_id", details })}
        </template>
      </div>
    </template>
  </div>`;

/** The Outgoing page: the write path with its state, the selected windows.json, what is built per session with Rebuild all, and the processed files' format folded at the bottom. */
export const outgoingRoot = `
  <div x-data="outgoingPage" class="grid h-full grid-cols-12 grid-rows-[auto_minmax(0,1fr)_auto] gap-4">
    ${card("Write path", writeBody, "col-span-8")}
    ${card("Selected for export", selectedBody, "col-span-4")}
    ${card("Built", builtBody, "col-span-12")}
    ${foldedCard("Outgoing data format", formatBody, "col-span-12", formatChip)}
  </div>`;
