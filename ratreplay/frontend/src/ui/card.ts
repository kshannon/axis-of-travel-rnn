/** A card in the page grid: a title over a body, spanning the given grid classes. */
export function card(title: string, body: string, span = "col-span-12 row-span-6"): string {
  return `
    <section class="${span} flex min-h-0 min-w-0 flex-col gap-3 overflow-hidden rounded-xl border border-line bg-card p-4">
      <h2 class="text-sm font-medium uppercase tracking-wide text-muted">${title}</h2>
      <div class="min-h-0 flex-1">${body}</div>
    </section>`;
}

/** The fixed 12 by 6 grid every page fills with cards, no scrolling. */
export function pageGrid(cards: string): string {
  return `<div class="grid h-full grid-cols-12 grid-rows-6 gap-4">${cards}</div>`;
}
