import Alpine from "alpinejs";
import { errorText, getSelected, rebuildAll } from "../api/client";
import type { Kind } from "../api/types";
import { healthStore } from "../state/health";
import { settingsStore } from "../state/settings";
import { card, pageGrid } from "../ui/card";
import { BUTTON, BUTTON_PRIMARY, CHIP_ACCENT, CHIP_BAD, CHIP_MUTED, CHIP_OK, TILE, TILE_LABEL, TILE_VALUE } from "../ui/style";
import { stampWithSince } from "../ui/time";
import { toast } from "../ui/toast";
import { foldersView, FLOW, HERE, rebuildPrompt, rebuildSummary } from "./data-view";
import type { Page } from "./page";

const REBUILD_HINT = "Build the blocks of every reviewed session again";
const REBUILD_BLOCKED = "Needs the three folders usable and at least one review";

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
          <code x-show="${view}.key" class="font-mono text-xs text-muted" x-text="${view}.key"></code>
        </div>
        <p class="break-all font-mono text-xs" x-text="${view}.root"></p>
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
        Changing a folder means editing this file, then pressing Reload, which reads it again and checks the folders it names.
      </p>
    </div>
  </template>
  <p x-show="!view" class="text-sm text-muted">Reading the data folders</p>`;

const reloadButton = `<button type="button" :disabled="busy" @click="reload()" class="${BUTTON_PRIMARY}">Reload</button>`;
const rebuildButton = `
  <button type="button" :disabled="busy || !canRebuild" :title="canRebuild ? '${REBUILD_HINT}' : '${REBUILD_BLOCKED}'" @click="rebuildAll()" class="${BUTTON}"
    x-text="rebuilding ? 'Rebuilding' : 'Rebuild all'"></button>`;

function registerData(): void {
  Alpine.data("dataPage", () => ({
    flow: FLOW,
    here: HERE,
    busy: false,
    rebuilding: false,
    stamp: stampWithSince,

    get view() {
      const { found } = healthStore();
      return found && foldersView(found);
    },
    get configPath() {
      return healthStore().found?.config_path;
    },
    get reviews() {
      return healthStore().found?.processed.counts.reviews ?? 0;
    },
    get canRebuild() {
      return !healthStore().problem("transformed", "processed", "environments") && this.reviews > 0;
    },

    async init() {
      await healthStore().load();
    },
    async reload() {
      this.busy = true;
      if (await healthStore().load(true)) toast.success("Read the config file again and checked the three folders");
      this.busy = false;
    },
    /** Build every reviewed session's blocks again after a confirmation, at the settings selected for export when there are some, else the settings in use. */
    async rebuildAll() {
      this.busy = true;
      try {
        const { selected } = await getSelected();
        const settings = selected?.settings ?? (await settingsStore().load());
        if (!confirm(rebuildPrompt(this.reviews, settings, healthStore().found!.processed.root!))) return;
        this.rebuilding = true;
        const result = await rebuildAll(settings);
        const { failed, errors } = result.totals;
        if (failed || errors) toast.warning(rebuildSummary(result));
        else toast.success(rebuildSummary(result), healthStore().found!.processed.root!);
        await healthStore().load();
      } catch (error) {
        toast.error(errorText(error));
      } finally {
        this.busy = false;
        this.rebuilding = false;
      }
    },
  }));
}

export const dataPage: Page = {
  id: "data",
  title: "Data",
  html: pageGrid(
    card("Data flow", flowLine, "col-span-12 row-span-1") +
      card("Incoming, transformed lab data", folderBody("transformed"), "col-span-4 row-span-4") +
      card("Outbound, processed lab data", folderBody("processed"), "col-span-4 row-span-4", rebuildButton) +
      card("Environments", folderBody("environments"), "col-span-4 row-span-4") +
      card("Config file", configBody, "col-span-12 row-span-1", reloadButton),
    `x-data="dataPage"`,
  ),
  register: registerData,
};
