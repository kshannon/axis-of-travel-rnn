import type { WindowSettings } from "../api/types";

// A block exactly as long as one window plus the horizon yields one window through float rounding, within this.
const TOLERANCE_S = 1e-9;

/** How many training windows a block yields, the project's window_count (axis_of_travel_rnn.windows) mirrored for display. */
export function windowCount(nFrames: number, rateHz: number, settings: Pick<WindowSettings, "window_s" | "stride_s" | "horizon_s">): number {
  const usable = nFrames / rateHz - settings.window_s - settings.horizon_s;
  return usable < -TOLERANCE_S ? 0 : Math.floor((usable + TOLERANCE_S) / settings.stride_s) + 1;
}
