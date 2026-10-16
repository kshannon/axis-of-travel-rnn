import type { Epoch, Run } from "../api/types";

const NO_EPOCH = "no epoch";

/** The name of the epoch holding the lab frame. */
export function epochAt(epochs: Epoch[], frame: number): string {
  return epochs.find((e) => e.frame_start <= frame && frame <= e.frame_end)?.epoch ?? NO_EPOCH;
}

/** The run holding the lab frame. */
export function runAt(runs: Run[], frame: number): Run | null {
  return runs.find((r) => r.frame_start <= frame && frame <= r.frame_end) ?? null;
}
