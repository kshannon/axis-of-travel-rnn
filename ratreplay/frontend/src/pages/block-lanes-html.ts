/** The body of the Timeline card on the pages that show a block: the range on show over the canvas of the lanes. The page's Alpine data has `viewing`. */
export const blockLanesBody = `
  <div class="flex h-full min-h-0 flex-col gap-2">
    <p class="text-xs text-muted">showing <span data-testid="shown" class="tabular-nums text-ink" x-text="viewing"></span></p>
    <div x-ref="timeline" data-testid="timeline" class="relative min-h-0 flex-1 overflow-hidden"></div>
  </div>`;
