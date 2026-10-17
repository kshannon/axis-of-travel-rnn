import Alpine from "alpinejs";
import type { Kind } from "../api/types";
import { sourcesStore } from "../state/sources";
import { card, pageGrid } from "../ui/card";
import { BUTTON_PRIMARY, CHIP_ACCENT, CHIP_BAD, CHIP_MUTED, CHIP_OK, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { stampWithSince } from "../ui/time";
import { toast } from "../ui/toast";
import { foldersView, FLOW, HERE } from "./data-view";
import type { Page } from "./page";

const flowLine = `
  <ol class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
    <template x-for="(step, index) in flow" :key="step">
      <li class="flex items-center gap-2">
        <span x-show="index" class="text-muted">&rarr;</span>
        <span :class="step === here ? '${CHIP_ACCENT}' : '${CHIP_MUTED}'" x-text="step"></span>
      </li>
    </template>
  </ol>`;

/** The body of the card of one folder, from the page's view of the folders. */
function folderBody(kind: Kind): string {
  const view = `view.${kind}`;
  return `
    <template x-if="view">
      <div data-testid="${kind}" class="flex flex-col gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <span class="${CHIP_MUTED}" x-text="${view}.direction"></span>
          <span :class="${view}.status === 'ok' ? '${CHIP_OK}' : '${CHIP_BAD}'" x-text="${view}.status"></span>
          <code class="font-mono text-xs text-muted" x-text="${view}.key"></code>
        </div>
        <p class="break-all font-mono text-xs" x-text="${view}.path"></p>
        <p x-show="${view}.note" class="text-xs text-muted" x-text="${view}.note"></p>
        <ul x-show="${view}.problems.length" class="list-disc space-y-0.5 pl-5 text-xs text-bad">
          <template x-for="problem in ${view}.problems"><li x-text="problem"></li></template>
        </ul>
        <dl class="grid grid-cols-3 gap-2">
          <template x-for="entry in ${view}.counts" :key="entry.label">
            <div class="${TILE}">
              <dt class="${TILE_LABEL}" x-text="entry.label"></dt>
              <dd class="${TILE_VALUE}" x-text="entry.value"></dd>
            </div>
          </template>
        </dl>
        <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
          <template x-for="row in ${view}.times" :key="row.label">
            <div class="contents"><dt class="text-muted" x-text="row.label"></dt><dd x-text="stamp(row.stamp)"></dd></div>
          </template>
        </dl>
      </div>
    </template>`;
}

const configBody = `
  <template x-if="view">
    <div class="flex flex-col gap-1">
      <p data-testid="config-path" class="break-all font-mono text-xs" x-text="configPath"></p>
      <p class="text-xs text-muted">
        Changing a folder means editing this file, then pressing Reload. The processor reads the same two keys, so both always agree.
      </p>
    </div>
  </template>
  <p x-show="!view" class="text-sm text-muted">Reading the data folders</p>`;

const reloadButton = `<button type="button" :disabled="busy" @click="reload()" class="${BUTTON_PRIMARY}">Reload</button>`;

function registerData(): void {
  Alpine.data("dataPage", () => ({
    flow: FLOW,
    here: HERE,
    busy: false,
    stamp: stampWithSince,

    get view() {
      const { found } = sourcesStore();
      return found && foldersView(found);
    },
    get configPath() {
      return sourcesStore().found?.config_path;
    },

    async init() {
      await sourcesStore().load();
    },
    async reload() {
      this.busy = true;
      if (await sourcesStore().load(true)) toast.success("Read the config file again and checked both folders");
      this.busy = false;
    },
  }));
}

export const dataPage: Page = {
  id: "data",
  title: "Data",
  html: pageGrid(
    card("Data flow", flowLine, "col-span-12 row-span-1") +
      card("Incoming, transformed lab data", folderBody("transformed"), "col-span-6 row-span-4") +
      card("Outbound, processed lab data", folderBody("processed"), "col-span-6 row-span-4") +
      card("Config file", configBody, "col-span-12 row-span-1", reloadButton),
    `x-data="dataPage"`,
  ),
  register: registerData,
};
