import { CHIP_MUTED } from "./style";

/** A ? button that opens a short explanation under it, and closes on a click anywhere else. */
export function helpPopover(label: string, text: string): string {
  return `
    <span class="relative" x-data="{ open: false }" @click.outside="open = false">
      <button type="button" @click="open = !open" aria-label="${label}" :aria-expanded="open" class="${CHIP_MUTED}">?</button>
      <div x-show="open" x-cloak class="absolute right-0 z-20 mt-2 w-96 rounded-lg border border-line bg-card p-3 text-xs normal-case leading-5 tracking-normal text-ink shadow-lg">${text}</div>
    </span>`;
}
