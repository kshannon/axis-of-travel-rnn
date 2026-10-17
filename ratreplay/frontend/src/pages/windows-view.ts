import type { BlockHeader, BlockWindow } from "../api/types";
import { THIN_PATH } from "../draw/map";
import type { Stretch } from "../draw/map";
import { CHIP_BAD, CHIP_MUTED, CHIP_OK } from "../ui/style";

const PERCENT = 100;
const WINDOW_STROKE_PX = 3;

/** A share as a percent with at most one decimal. */
const percent = (share: number): string => `${+(PERCENT * share).toFixed(1)}%`;

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
  status: "ok" | "trouble" | "info";
  chip: string;
}

const STATUS_CHIPS: Record<Check["status"], string> = { ok: CHIP_OK, trouble: CHIP_BAD, info: CHIP_MUTED };

const check = (label: string, value: string, note: string, ok: boolean | null): Check => {
  const status = ok === null ? "info" : ok ? "ok" : "trouble";
  return { label, value, note, status, chip: STATUS_CHIPS[status] };
};

/**
 * The checks of a window: the position finite throughout, the measured heading against the minimum, the trips inside
 * (counted only, the minimum applies to the whole block) and the burn-in and the horizon fitting inside the block.
 */
export function windowChecks(window: BlockWindow, header: BlockHeader): Check[] {
  const { settings, rate_hz: rate } = header;
  const horizonFits = window.stop - window.window_stop === Math.round(settings.horizon_s * rate);
  return [
    check("position finite", percent(window.position_finite), "of the frames, all of them are needed", window.position_finite === 1),
    check("heading measured", percent(window.heading_measured), `of the frames, at least ${percent(settings.min_heading_measured)} is needed`,
      window.heading_measured >= settings.min_heading_measured),
    check("trips", `${window.trips_complete} complete, ${window.trips_partial} partial`, "inside the window and its horizon", null),
    check("burn-in and horizon", `${settings.burn_in_s} s and ${settings.horizon_s} s`, "inside the block", window.burn_in_stop <= window.window_stop && horizonFits),
  ];
}

/** Where a window lies in the block: its start, the end of the window proper and the end of its horizon. */
export function windowSpan(window: BlockWindow, rateHz: number): string {
  const seconds = (index: number) => `${(index / rateHz).toFixed(1)} s`;
  return `${seconds(window.first)} to ${seconds(window.window_stop)} in the block, horizon to ${seconds(window.stop)}`;
}

/** How many of the block's windows are ok. */
export function windowsOk(windows: BlockWindow[]): number {
  return windows.filter((window) => window.ok).length;
}

/** The map's lines for a window: the whole path thin, then the burn-in lighter, the rest of the window and the horizon after it. */
export function windowStretches(header: BlockHeader, window: BlockWindow): Stretch[] {
  const line = { width: WINDOW_STROKE_PX };
  return [
    { first: 1, last: header.n_frames, ...THIN_PATH },
    { ...line, first: window.first + 1, last: window.burn_in_stop, colour: "accent", alpha: 1, light: true },
    { ...line, first: Math.max(window.burn_in_stop, 1), last: window.window_stop, colour: "accent", alpha: 1 },
    { ...line, first: window.window_stop, last: window.stop, colour: "warn", alpha: 1 },
  ];
}
