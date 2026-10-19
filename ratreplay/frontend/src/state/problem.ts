import type { Health, Kind } from "../api/types";

const READING = "Reading the data folders.";
const NAMES: Record<Kind, string> = { transformed: "The transformed lab data", processed: "The processed lab data", synthetic: "The synthetic data", environments: "The environments" };

/**
 * Why a page that needs these folders cannot show, none when each is usable. A folder is unusable when it has problems,
 * which a missing folder gives too. A processed folder that does not exist yet has none, the first save creates it.
 */
export function problemWith(health: Health | null, kinds: readonly Kind[]): string {
  if (!health) return READING;
  const broken = kinds.find((kind) => health[kind].problems.length);
  return broken ? `${NAMES[broken]} cannot be used: ${health[broken].problems.join(", ")}` : "";
}
