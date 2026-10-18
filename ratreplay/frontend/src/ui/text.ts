import type { WindowSettings } from "../api/types";
import { percent } from "./format";

/** A number with its noun, the noun made plural unless the number is one. */
export function counted(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** The window settings as one line. */
export function settingsText(s: WindowSettings): string {
  return `a ${s.window_s} s window every ${s.stride_s} s, burn-in ${s.burn_in_s} s, horizon ${s.horizon_s} s, ${s.rate_hz} Hz, ` +
    `measured heading at least ${percent(s.min_heading_measured)}, at least ${counted(s.min_complete_trips, "complete trip")}`;
}
