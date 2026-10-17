import type { Kind } from "../api/types";
import { card, pageGrid } from "./card";

const problemOf = (kinds: readonly Kind[]) => `$store.sources.problem(${kinds.map((kind) => `'${kind}'`).join(", ")})`;

/** Why the page cannot show yet, with the way to the Data page. */
function notice(kinds: readonly Kind[]): string {
  return `
    <div class="flex flex-col items-start gap-2 text-sm">
      <p x-text="${problemOf(kinds)}"></p>
      <a href="#/data" class="text-accent underline">Open the Data page</a>
    </div>`;
}

/** The body of a page that needs these folders: a notice linking to the Data page until each is ok. */
export function folderGate(body: string, ...kinds: Kind[]): string {
  return `
    <div class="h-full">
      <template x-if="${problemOf(kinds)}">${notice(kinds)}</template>
      <template x-if="!${problemOf(kinds)}">${body}</template>
    </div>`;
}

/** A page that needs these folders and lays out a grid of its own: a card with the notice until each is ok, then the body. */
export function folderPage(title: string, body: string, ...kinds: Kind[]): string {
  return `
    <div class="h-full">
      <template x-if="${problemOf(kinds)}">${pageGrid(card(title, notice(kinds)))}</template>
      <template x-if="!${problemOf(kinds)}">${body}</template>
    </div>`;
}
