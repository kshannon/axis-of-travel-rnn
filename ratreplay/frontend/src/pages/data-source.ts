import type { AttachBody, Counts, Source, SourceKind } from "../api/types";

export interface AttachForm {
  path: string;
  kind: SourceKind;
  processedPath: string;
}

const COUNT_LABELS: readonly [keyof Counts, string][] = [
  ["sessions", "sessions"], ["epochs", "epochs"], ["runs", "runs"], ["frames", "frames files"], ["blocks", "blocks"], ["reviews", "reviews"],
];

export function folderName(path: string): string {
  return path.split("/").filter(Boolean).pop() ?? path;
}

/** What is missing from the attach form, empty when it can be sent. */
export function attachProblem(form: AttachForm): string {
  if (!form.path.trim()) return "Enter the path of the folder to attach.";
  if (form.kind === "transformed" && !form.processedPath.trim()) {
    return "A transformed source needs the processed folder its reviews and blocks live in.";
  }
  return "";
}

export function attachBody(form: AttachForm): AttachBody {
  const path = form.path.trim();
  return form.kind === "transformed" ? { path, kind: form.kind, processed_path: form.processedPath.trim() } : { path, kind: form.kind };
}

/** The counts the source has, in reading order. */
export function countEntries(source: Source): { label: string; value: number }[] {
  return COUNT_LABELS.filter(([key]) => source.counts[key] !== undefined).map(([key, label]) => ({ label, value: source.counts[key]! }));
}

/** The manifest run times, the times each folder last changed and when the source was attached. */
export function timeRows(source: Source): { label: string; stamp: string }[] {
  const { transformed, processed } = source.manifests;
  return [
    ...(transformed ? [{ label: "converter run", stamp: transformed.timestamp }, { label: "converter folder changed", stamp: transformed.modified }] : []),
    ...(processed ? [{ label: "processor run", stamp: processed.timestamp }, { label: "processor folder changed", stamp: processed.modified }] : []),
    { label: "attached", stamp: source.attached_at },
  ];
}
