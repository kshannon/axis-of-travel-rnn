export const CARD = "rounded-xl border border-line bg-card p-4";

/** A card in the page grid: a title over a body, spanning the given grid classes, with buttons or chips beside the title when given. */
export function card(title: string, body: string, span = "col-span-12 row-span-6", actions = ""): string {
  return `
    <section class="${span} flex min-h-0 min-w-0 flex-col gap-3 overflow-hidden ${CARD}">
      <header class="flex items-center justify-between gap-2">
        <h2 class="text-sm font-medium uppercase tracking-wide text-muted">${title}</h2>
        ${actions ? `<div class="flex flex-wrap items-center justify-end gap-2">${actions}</div>` : ""}
      </header>
      <div class="min-h-0 flex-1 overflow-auto">${body}</div>
    </section>`;
}

/** The fixed 12 by 6 grid every page fills with cards, no page scroll. Attributes go on the grid, where a page puts its x-data. */
export function pageGrid(cards: string, attributes = ""): string {
  return `<div ${attributes} class="grid h-full grid-cols-12 grid-rows-6 gap-4">${cards}</div>`;
}
