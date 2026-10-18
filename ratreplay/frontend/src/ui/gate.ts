import type { Kind } from "../api/types";
import { card, pageGrid } from "./card";

// The lab data and the environments are read on the Incoming page, the blocks are written on the Outgoing page.
const INCOMING: readonly Kind[] = ["transformed", "environments"];

const problemOf = (kinds: readonly Kind[]) => `$store.health.problem(${kinds.map((kind) => `'${kind}'`).join(", ")})`;

/** Why the page cannot show yet, with the way to the page that shows the broken folder. */
function notice(kinds: readonly Kind[]): string {
  const incoming = kinds.filter((kind) => INCOMING.includes(kind));
  const toIncoming = incoming.length ? problemOf(incoming) : "false";
  return `
    <div class="flex flex-col items-start gap-2 text-sm">
      <p x-text="${problemOf(kinds)}"></p>
      <a x-show="${toIncoming}" href="#/incoming" class="text-accent underline">Open the Incoming page</a>
      <a x-show="!(${toIncoming})" href="#/outgoing" class="text-accent underline">Open the Outgoing page</a>
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
