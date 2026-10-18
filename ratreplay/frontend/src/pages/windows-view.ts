import type { BlockHeader, BlockWindow, WindowSettings } from "../api/types";
import { THIN_PATH } from "../draw/map";
import type { Stretch } from "../draw/map";
import { percent } from "../ui/format";

const WINDOW_STROKE_PX = 3;

/** The window one step on in a direction, kept inside the block's windows. */
export function stepWindow(index: number, direction: 1 | -1, count: number): number {
  return Math.min(Math.max(index + direction, 0), count - 1);
}

/** The index of the window a number typed in the jump box names, the windows being numbered from 1, none when it is not a whole number among them. */
export function jumpTarget(typed: unknown, count: number): number | null {
  const number = Number(typed);
  return Number.isInteger(number) && number >= 1 && number <= count ? number - 1 : null;
}

export interface Check {
  label: string;
  value: string;
  note: string;
}

/**
 * What the row of a window measured: the share of its frames with a finite position, the measured heading against the
 * minimum the settings ask for, the trips inside the window and its horizon, and the burn-in and horizon the settings
 * give. Whether the window passes is the row's own `ok` and `reason`, not decided here.
 */
export function windowChecks(window: BlockWindow, settings: WindowSettings): Check[] {
  return [
    { label: "position finite", value: percent(window.position_finite, 1), note: "of the frames of the window and its horizon" },
    { label: "heading measured", value: percent(window.heading_measured, 1), note: `of the frames, the settings ask for at least ${percent(settings.min_heading_measured, 1)}` },
    { label: "trips", value: `${window.trips_complete} complete, ${window.trips_partial} partial`, note: "complete: outbound start and return end inside the window and its horizon" },
    { label: "burn-in and horizon", value: `${settings.burn_in_s} s and ${settings.horizon_s} s`, note: "marked on the lanes, the burn-in lighter and the horizon hatched" },
  ];
}

/** What the server says of a window: ok, or in trouble with the first check it fails. */
export function windowVerdict(window: BlockWindow): string {
  return window.ok ? "window ok" : `window trouble, ${window.reason}`;
}

/** Where a window lies in the block, from its row: its start and the end of its horizon in seconds. */
export function windowSpan(window: BlockWindow): string {
  return `${window.start_s.toFixed(1)} s to ${window.stop_s.toFixed(1)} s in the block, the window and its horizon`;
}

/** How many of the block's windows are ok. */
export function windowsOk(windows: BlockWindow[]): number {
  return windows.filter((window) => window.ok).length;
}

/** The map's lines for a window: the whole path thin, then the burn-in lighter, the rest of the window and the horizon after it. */
export function windowStretches(header: BlockHeader, window: BlockWindow): Stretch[] {
  const line = { width: WINDOW_STROKE_PX };
  return [
    { first: 1, last: header.row.n_frames, ...THIN_PATH },
    { ...line, first: window.first + 1, last: window.burn_in_stop, colour: "accent", alpha: 1, light: true },
    { ...line, first: Math.max(window.burn_in_stop, 1), last: window.window_stop, colour: "accent", alpha: 1 },
    { ...line, first: window.window_stop, last: window.stop, colour: "warn", alpha: 1 },
  ];
}
