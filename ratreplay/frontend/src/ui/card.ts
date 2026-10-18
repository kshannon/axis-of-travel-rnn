export const CARD = "rounded-xl border border-line bg-card p-4";

/** A card in the page grid: a title over a body, spanning the given grid classes, with buttons or chips beside the title when given and, for a card that owns a status, the Alpine expression of its edge from `statusEdge`. */
export function card(title: string, body: string, span = "col-span-12 row-span-6", actions = "", edge = ""): string {
  return `
    <section ${edge ? `:class="${edge}"` : ""} class="${span} flex min-h-0 min-w-0 flex-col gap-3 overflow-hidden ${CARD}">
      <header class="flex items-center justify-between gap-2">
        <h2 class="text-sm font-medium uppercase tracking-wide text-muted">${title}</h2>
        ${actions ? `<div class="flex flex-wrap items-center justify-end gap-2">${actions}</div>` : ""}
      </header>
      <div class="min-h-0 flex-1 overflow-auto">${body}</div>
    </section>`;
}

/** A card folded to its title, open on a click, for what is read now and then. An open body scrolls when it is taller than its room. */
export function foldedCard(title: string, body: string, span = "col-span-12", actions = ""): string {
  return `
    <details class="group ${span} min-w-0 ${CARD}">
      <summary class="flex cursor-pointer select-none items-center justify-between gap-2">
        <h2 class="text-sm font-medium uppercase tracking-wide text-muted">
          <span class="inline-block text-xs transition-transform group-open:rotate-90">&#9656;</span> ${title}
        </h2>
        ${actions ? `<div class="flex flex-wrap items-center justify-end gap-2">${actions}</div>` : ""}
      </summary>
      <div class="mt-3 max-h-72 overflow-auto">${body}</div>
    </details>`;
}

/** The fixed 12 by 6 grid every page fills with cards, no page scroll. Attributes go on the grid, where a page puts its x-data. */
export function pageGrid(cards: string, attributes = ""): string {
  return `<div ${attributes} class="grid h-full grid-cols-12 grid-rows-6 gap-4">${cards}</div>`;
}
