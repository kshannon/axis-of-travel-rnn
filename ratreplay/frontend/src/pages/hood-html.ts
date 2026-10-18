import { tableHtml, tableMarkup } from "./tables-html";

export const METHOD_COLOURS: Record<string, string> = {
  GET: "text-accent",
  POST: "text-accent",
  PUT: "text-warn",
  DELETE: "text-bad",
};

const INTRO = "These are the internal routes the browser uses to talk to the backend, a cheat sheet of how the tool works, not a public API.";

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

/** The body of the Under the hood card: the routes of the OpenAPI document, then its schemas. The page's Alpine data has `endpoints`, `schemas`, `title` and `methodColour`. */
export const hoodBody = `
  <div class="flex flex-col gap-2">
    <p class="text-sm">${INTRO}</p>
    <p x-show="title" class="text-sm text-muted" x-text="title"></p>
    <template x-for="endpoint in endpoints" :key="endpoint.method + endpoint.path">${endpointHtml}</template>
    <h3 class="mt-2 text-sm font-medium">Schemas</h3>
    <template x-for="table in schemas" :key="table.title">${tableHtml}</template>
  </div>`;
