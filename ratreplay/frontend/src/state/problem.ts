import type { Kind, Sources } from "../api/types";

const READING = "Reading the data folders.";
const NAMES: Record<Kind, string> = { transformed: "The transformed lab data", processed: "The processed lab data" };

/** Why a page that needs these folders cannot show, none when each is ok. */
export function problemWith(sources: Sources | null, kinds: readonly Kind[]): string {
  if (!sources) return READING;
  const broken = kinds.find((kind) => sources[kind].status !== "ok");
  return broken ? `${NAMES[broken]} cannot be used: ${sources[broken].problems.join(", ")}` : "";
}
