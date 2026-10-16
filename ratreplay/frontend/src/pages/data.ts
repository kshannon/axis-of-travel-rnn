import Alpine from "alpinejs";
import { attachSource, detachSource, errorText, listSources } from "../api/client";
import type { Source } from "../api/types";
import { sourceStore, syncSelection } from "../state/source";
import { CARD, card, pageGrid } from "../ui/card";
import { BUTTON, BUTTON_DANGER, BUTTON_PRIMARY, CHIP_ACCENT, CHIP_BAD, CHIP_MUTED, CHIP_OK, FIELD, INPUT } from "../ui/style";
import { stampWithSince } from "../ui/time";
import { toast } from "../ui/toast";
import { attachBody, attachProblem, countEntries, folderName, timeRows } from "./data-source";
import type { AttachForm } from "./data-source";
import type { Page } from "./page";

const attachForm = `
  <form class="flex flex-col gap-3" @submit.prevent="attach()">
    <label class="${FIELD}">Kind
      <select x-model="form.kind" class="${INPUT}">
        <option value="transformed">transformed</option>
        <option value="processed">processed</option>
      </select>
    </label>
    <label class="${FIELD}">Folder path
      <input type="text" x-model="form.path" spellcheck="false" placeholder="/path/to/the/folder" class="${INPUT}" />
    </label>
    <div x-show="form.kind === 'transformed'" class="flex flex-col gap-1">
      <label class="${FIELD}">Processed folder path
        <input type="text" x-model="form.processedPath" spellcheck="false" placeholder="/path/to/the/processed/folder" class="${INPUT}" />
      </label>
      <p class="text-xs text-muted">Where its reviews and blocks live. The folder need not exist yet, the first save creates it.</p>
    </div>
    <p x-show="formError" x-text="formError" role="alert" class="whitespace-pre-wrap break-words text-sm text-bad"></p>
    <button type="submit" :disabled="busy" class="${BUTTON_PRIMARY} self-start">Attach</button>
  </form>`;

const sourceCard = `
  <article class="${CARD} flex flex-col gap-3" :class="current(source) ? 'ring-2 ring-accent' : ''">
    <header class="flex flex-wrap items-center gap-2">
      <h3 class="mr-auto truncate font-medium" :title="source.path" x-text="folderName(source.path)"></h3>
      <span x-show="current(source)" class="${CHIP_ACCENT}">selected</span>
      <span class="${CHIP_MUTED}" x-text="source.kind"></span>
      <span :class="source.status === 'ok' ? '${CHIP_OK}' : '${CHIP_BAD}'" x-text="source.status"></span>
    </header>
    <p class="break-all font-mono text-xs text-muted" x-text="source.path"></p>
    <p x-show="source.kind === 'transformed'" class="break-all font-mono text-xs text-muted">
      reviews and blocks in <span x-text="source.processed_path"></span>
    </p>
    <ul x-show="source.problems.length" class="list-disc space-y-0.5 pl-5 text-xs text-bad">
      <template x-for="problem in source.problems"><li x-text="problem"></li></template>
    </ul>
    <dl class="grid grid-cols-3 gap-2">
      <template x-for="entry in counts(source)" :key="entry.label">
        <div class="rounded-md bg-page px-2 py-1">
          <dt class="text-xs text-muted" x-text="entry.label"></dt>
          <dd class="font-medium tabular-nums" x-text="entry.value"></dd>
        </div>
      </template>
    </dl>
    <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
      <template x-for="row in times(source)" :key="row.label">
        <div class="contents">
          <dt class="text-muted" x-text="row.label"></dt>
          <dd x-text="stamp(row.stamp)"></dd>
        </div>
      </template>
    </dl>
    <template x-if="confirming !== source.id">
      <div class="mt-auto flex gap-2 pt-1">
        <button type="button" :disabled="current(source) || source.status !== 'ok'" @click="select(source)"
          class="${BUTTON_PRIMARY}" x-text="current(source) ? 'Selected' : 'Select'"></button>
        <button type="button" @click="confirming = source.id" class="${BUTTON}">Detach</button>
      </div>
    </template>
    <template x-if="confirming === source.id">
      <div class="mt-auto flex items-center gap-2 pt-1">
        <span class="mr-auto text-xs text-muted">Its data stays where it is.</span>
        <button type="button" @click="detach(source)" class="${BUTTON_DANGER}">Confirm detach</button>
        <button type="button" @click="confirming = ''" class="${BUTTON}">Cancel</button>
      </div>
    </template>
  </article>`;

const sourceList = `
  <div class="h-full overflow-y-auto">
    <p x-show="loading" class="text-sm text-muted">Loading the sources</p>
    <p x-show="!loading && !sources.length" class="text-sm text-muted">
      Nothing is attached yet. Attach a transformed folder with the processed folder its reviews go in, or a processed folder, with the form.
    </p>
    <div class="grid grid-cols-[repeat(auto-fill,minmax(24rem,1fr))] gap-4">
      <template x-for="source in sources" :key="source.id">${sourceCard}</template>
    </div>
  </div>`;

function registerData(): void {
  Alpine.data("dataPage", () => ({
    sources: [] as Source[],
    loading: true,
    busy: false,
    confirming: "",
    formError: "",
    form: { path: "", kind: "transformed", processedPath: "" } as AttachForm,
    folderName,
    counts: countEntries,
    times: timeRows,
    stamp: stampWithSince,

    async init() {
      await this.load();
    },
    async load() {
      try {
        this.sources = await listSources();
        syncSelection(this.sources);
      } catch (error) {
        toast.error(errorText(error));
      }
      this.loading = false;
    },
    current(source: Source) {
      return sourceStore().id === source.id;
    },
    select(source: Source) {
      sourceStore().select(source);
      toast.success(`Selected ${folderName(source.path)}, the other pages work on it now`);
    },
    async attach() {
      this.formError = attachProblem(this.form);
      if (this.formError) return;
      this.busy = true;
      try {
        const source = await attachSource(attachBody(this.form));
        const known = this.sources.some((s) => s.id === source.id);
        if (known) toast.warning(`${folderName(source.path)} was already attached`);
        else toast.success(`Attached ${folderName(source.path)}`);
        Object.assign(this.form, { path: "", processedPath: "" });
        await this.load();
      } catch (error) {
        this.formError = errorText(error);
        toast.error("Not attached, the form says why");
      } finally {
        this.busy = false;
      }
    },
    async detach(source: Source) {
      try {
        await detachSource(source.id);
        if (sourceStore().id === source.id) sourceStore().clear();
        toast.success(`Detached ${folderName(source.path)}, its data is untouched`);
        this.confirming = "";
        await this.load();
      } catch (error) {
        toast.error(errorText(error));
      }
    },
  }));
}

export const dataPage: Page = {
  id: "data",
  title: "Data",
  html: pageGrid(
    card("Attach a source", attachForm, "col-span-4 row-span-6") + card("Attached sources", sourceList, "col-span-8 row-span-6"),
    `x-data="dataPage"`,
  ),
  register: registerData,
};
