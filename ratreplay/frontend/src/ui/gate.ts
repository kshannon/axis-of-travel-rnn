import { card, pageGrid } from "./card";

const problemOf = (kind: string) => `$store.source.problem('${kind}')`;

/** Why the page cannot show yet, with the way to the Data page to choose a source. */
function sourceNotice(kind: string): string {
  return `
    <div class="flex flex-col items-start gap-2 text-sm">
      <p x-text="${problemOf(kind)}"></p>
      <a href="#/data" class="text-accent underline">Choose a source on the Data page</a>
    </div>`;
}

/** The body of a page that needs a source: a notice linking to the Data page until one of the right kind is selected. */
export function sourceGate(body: string, kind = ""): string {
  return `
    <div class="h-full">
      <template x-if="${problemOf(kind)}">${sourceNotice(kind)}</template>
      <template x-if="!${problemOf(kind)}">${body}</template>
    </div>`;
}

/** A page that needs a source and lays out a grid of its own: a card with the notice until one is selected, then the body. */
export function sourcePage(title: string, body: string, kind = ""): string {
  return `
    <div class="h-full">
      <template x-if="${problemOf(kind)}">${pageGrid(card(title, sourceNotice(kind)))}</template>
      <template x-if="!${problemOf(kind)}">${body}</template>
    </div>`;
}
