import Alpine from "alpinejs";
import { ToastQueue } from "./toast-queue";

export function registerToasts(): void {
  Alpine.store("toasts", new ToastQueue());
}

function queue(): ToastQueue {
  return Alpine.store("toasts") as ToastQueue;
}

/** Tell the person what an action did, every action ends in one. A success is brief, a warning or an error stays until it is closed. */
export const toast = {
  success: (text: string, path = "") => queue().push("success", text, path),
  warning: (text: string, path = "") => queue().push("warning", text, path),
  error: (text: string) => queue().push("error", text),
};

const KIND_NAMES = "toast.kind === 'error' ? 'Error' : 'Warning'";

/** The two stacks of toasts: the problems at the top right, large, with their time and a close button each, and the successes at the bottom right, a click dismisses one. */
export function toastHostHtml(): string {
  return `
    <div data-testid="problems" class="pointer-events-none fixed right-4 top-14 z-50 flex max-h-[calc(100vh-4.5rem)] w-[28rem] flex-col gap-3 overflow-y-auto">
      <template x-for="toast in $store.toasts.problems" :key="toast.id">
        <div role="alert" class="pointer-events-auto rounded-lg border-2 bg-card p-4 text-base shadow-xl"
          :class="toast.kind === 'error' ? 'border-bad text-bad' : 'border-warn text-warn'">
          <div class="flex items-center justify-between gap-3 text-sm">
            <span class="font-semibold uppercase tracking-wide"><span x-text="${KIND_NAMES}"></span>
              <span class="ml-2 font-normal normal-case tabular-nums text-muted" x-text="toast.time"></span></span>
            <button type="button" @click="$store.toasts.dismiss(toast.id)" aria-label="Close" title="Close"
              class="rounded px-2 text-xl leading-none hover:bg-ink/10">&times;</button>
          </div>
          <p class="mt-1 break-words" x-text="toast.text"></p>
          <p x-show="toast.path" class="mt-1 break-all font-mono text-sm" x-text="toast.path"></p>
        </div>
      </template>
    </div>
    <div class="pointer-events-none fixed bottom-4 right-4 z-50 flex w-96 flex-col gap-2">
      <template x-for="toast in $store.toasts.items" :key="toast.id">
        <div role="status" @click="$store.toasts.dismiss(toast.id)"
          class="pointer-events-auto cursor-pointer rounded-lg border border-ok/60 bg-card px-4 py-2 text-sm text-ok shadow-lg transition-opacity duration-500"
          :class="{ 'opacity-0': toast.leaving }">
          <span x-text="toast.text"></span>
          <span x-show="toast.path" class="mt-0.5 block break-all font-mono text-xs" x-text="toast.path"></span>
        </div>
      </template>
    </div>`;
}
