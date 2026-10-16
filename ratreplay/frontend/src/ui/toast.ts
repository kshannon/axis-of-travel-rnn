import Alpine from "alpinejs";
import { ToastQueue } from "./toast-queue";

export function registerToasts(): void {
  Alpine.store("toasts", new ToastQueue());
}

function queue(): ToastQueue {
  return Alpine.store("toasts") as ToastQueue;
}

/** Tell the person what an action did, every action ends in one. */
export const toast = {
  success: (text: string) => queue().push("success", text),
  warning: (text: string) => queue().push("warning", text),
  error: (text: string) => queue().push("error", text),
};

/** The stack of toasts in the corner, one click dismisses a toast. */
export function toastHostHtml(): string {
  return `
    <div class="pointer-events-none fixed bottom-4 right-4 z-50 flex w-96 flex-col gap-2">
      <template x-for="toast in $store.toasts.items" :key="toast.id">
        <div role="status" @click="$store.toasts.dismiss(toast.id)"
          class="pointer-events-auto cursor-pointer rounded-lg border bg-card px-4 py-2 text-sm shadow-lg transition-opacity duration-500"
          :class="{ 'border-ok/60 text-ok': toast.kind === 'success', 'border-warn/60 text-warn': toast.kind === 'warning',
            'border-bad/60 text-bad': toast.kind === 'error', 'opacity-0': toast.leaving }" x-text="toast.text"></div>
      </template>
    </div>`;
}
