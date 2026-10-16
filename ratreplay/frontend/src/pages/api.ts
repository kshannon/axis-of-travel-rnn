import Alpine from "alpinejs";
import { errorText, getFormat, getOpenApi } from "../api/client";
import { endpoints, formatGroups, schemaTables } from "../api/describe";
import type { Endpoint, FormatGroup, Table } from "../api/describe";
import { card, pageGrid } from "../ui/card";
import { TABLE, TD, TH } from "../ui/style";
import { toast } from "../ui/toast";
import type { Page } from "./page";

const METHOD_COLOURS: Record<string, string> = {
  GET: "text-ok",
  POST: "text-accent",
  PUT: "text-warn",
  DELETE: "text-bad",
};

// The table of `table`, in an x-for over tables.
const tableMarkup = `
  <div class="overflow-x-auto">
    <table class="${TABLE} text-xs">
      <thead><tr><template x-for="name in table.head" :key="name"><th class="${TH}" x-text="name"></th></template></tr></thead>
      <tbody>
        <template x-for="(cells, index) in table.rows" :key="index">
          <tr class="border-t border-line">
            <template x-for="(cell, column) in cells" :key="column"><td class="${TD}" x-text="cell"></td></template>
          </tr>
        </template>
      </tbody>
    </table>
  </div>`;

const tableHtml = `
  <details class="rounded-md border border-line">
    <summary class="cursor-pointer select-none px-3 py-1.5 text-sm" x-text="table.title"></summary>
    <div class="px-3 pb-2">${tableMarkup}</div>
  </details>`;

const formatCard = `
  <div class="flex flex-col gap-4">
    <template x-for="group in groups" :key="group.title">
      <section class="flex flex-col gap-2">
        <h3 class="text-sm font-medium" x-text="group.title"></h3>
        <template x-for="table in group.tables" :key="table.title">${tableHtml}</template>
      </section>
    </template>
  </div>`;

const endpointHtml = `
  <details class="rounded-md border border-line">
    <summary class="cursor-pointer select-none px-3 py-1.5 text-sm">
      <span class="inline-block w-16 font-mono text-xs font-medium" :class="methodColour[endpoint.method]" x-text="endpoint.method"></span>
      <span class="font-mono text-xs" x-text="endpoint.path"></span>
      <span class="ml-2 text-muted" x-text="endpoint.summary"></span>
    </summary>
    <div class="flex flex-col gap-2 px-3 pb-3">
      <p class="text-sm text-muted" x-text="endpoint.description"></p>
      <template x-for="table in endpoint.tables" :key="table.title">
        <div>
          <h4 class="mb-1 text-xs font-medium uppercase tracking-wide text-muted" x-text="table.title"></h4>
          ${tableMarkup}
        </div>
      </template>
    </div>
  </details>`;

const apiCard = `
  <div class="flex flex-col gap-2">
    <p x-show="title" class="text-sm text-muted" x-text="title"></p>
    <template x-for="endpoint in endpoints" :key="endpoint.method + endpoint.path">${endpointHtml}</template>
    <h3 class="mt-2 text-sm font-medium">Schemas</h3>
    <template x-for="table in schemas" :key="table.title">${tableHtml}</template>
  </div>`;

function registerApi(): void {
  Alpine.data("apiPage", () => ({
    groups: [] as FormatGroup[],
    endpoints: [] as Endpoint[],
    schemas: [] as Table[],
    title: "",
    methodColour: METHOD_COLOURS,

    async init() {
      try {
        const [contract, document] = await Promise.all([getFormat(), getOpenApi()]);
        this.groups = formatGroups(contract);
        this.endpoints = endpoints(document);
        this.schemas = schemaTables(document);
        this.title = `${document.info.title} ${document.info.version}, ${this.endpoints.length} routes, data format version ${contract.version}`;
      } catch (error) {
        toast.error(errorText(error));
      }
    },
  }));
}

export const apiPage: Page = {
  id: "api",
  title: "API",
  html: pageGrid(
    card("Data format", formatCard, "col-span-5 row-span-6") + card("API", apiCard, "col-span-7 row-span-6"),
    `x-data="apiPage"`,
  ),
  register: registerApi,
};
