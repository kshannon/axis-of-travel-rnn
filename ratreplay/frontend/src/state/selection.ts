import type { Counts, Source, SourceKind } from "../api/types";

const STORAGE_KEY = "ratreplay-source";

/** The source the pages work on and, once one is opened, the session in the replay. */
export interface Selection {
  id: string;
  kind: SourceKind | "";
  path: string;
  counts: Counts;
  sessionId: string;
}

export const NONE: Selection = { id: "", kind: "", path: "", counts: {}, sessionId: "" };

export function selectionOf(source: Source, sessionId = ""): Selection {
  return { id: source.id, kind: source.kind, path: source.path, counts: source.counts, sessionId };
}

/** The stored selection, none when nothing is stored or it cannot be read. */
export function loadSelection(storage: Pick<Storage, "getItem">): Selection {
  try {
    return { ...NONE, ...JSON.parse(storage.getItem(STORAGE_KEY) ?? "{}") };
  } catch {
    return NONE;
  }
}

export function saveSelection(storage: Pick<Storage, "setItem">, selection: Selection): void {
  const { id, kind, path, counts, sessionId } = selection;
  storage.setItem(STORAGE_KEY, JSON.stringify({ id, kind, path, counts, sessionId }));
}

/** The selection refreshed from the API's list of sources, none when its source is gone or no longer valid. */
export function reconcile(selection: Selection, sources: Source[]): Selection {
  const source = sources.find((s) => s.id === selection.id && s.status === "ok");
  return source ? selectionOf(source, selection.sessionId) : NONE;
}

/** Why the selected source cannot serve a page that needs this kind, none when it can. */
export function problemWith(selection: Selection, kind = ""): string {
  if (!selection.id) return "No source is selected.";
  return kind && selection.kind !== kind ? `The selected source is ${selection.kind}, this page needs a ${kind} one.` : "";
}
