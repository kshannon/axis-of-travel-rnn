import Alpine from "alpinejs";
import { errorText, listSources } from "../api/client";
import type { Source } from "../api/types";
import { toast } from "../ui/toast";
import { loadSelection, NONE, problemWith, reconcile, saveSelection, selectionOf } from "./selection";
import type { Selection } from "./selection";

export interface SourceStore extends Selection {
  select(source: Source): void;
  clear(): void;
  openSession(sessionId: string): void;
  sync(sources: Source[]): void;
  problem(kind?: string): string;
}

/** Register the source store, the selection that survives a reload. */
export function registerSource(): void {
  const store: SourceStore = {
    ...loadSelection(localStorage),
    select(source: Source) {
      Object.assign(this, selectionOf(source));
      saveSelection(localStorage, this);
    },
    clear() {
      Object.assign(this, NONE);
      saveSelection(localStorage, this);
    },
    openSession(sessionId: string) {
      this.sessionId = sessionId;
      saveSelection(localStorage, this);
    },
    sync(sources: Source[]) {
      Object.assign(this, reconcile(this, sources));
      saveSelection(localStorage, this);
    },
    problem(kind = "") {
      return problemWith(this, kind);
    },
  };
  Alpine.store("source", store);
}

export function sourceStore(): SourceStore {
  return Alpine.store("source") as SourceStore;
}

/** Refresh the selection from the list of sources the API gave, saying so when its source is gone. */
export function syncSelection(sources: Source[]): void {
  const store = sourceStore();
  const had = store.id;
  store.sync(sources);
  if (had && !store.id) toast.warning("The selected source is no longer attached or valid, choose another on the Data page.");
}

/** On boot, check the stored selection against the sources the API has now. */
export async function restoreSelection(): Promise<void> {
  if (!sourceStore().id) return;
  try {
    syncSelection(await listSources());
  } catch (error) {
    toast.error(errorText(error));
  }
}
