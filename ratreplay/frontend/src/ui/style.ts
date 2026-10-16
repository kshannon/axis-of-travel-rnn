// The class strings the pages share, so a button or a table looks the same everywhere.

const BUTTON_BASE = "rounded-md px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40";
export const BUTTON = `${BUTTON_BASE} border border-line text-ink hover:bg-ink/5`;
export const BUTTON_PRIMARY = `${BUTTON_BASE} bg-accent font-medium text-page hover:opacity-90`;
export const BUTTON_DANGER = `${BUTTON_BASE} border border-bad/60 text-bad hover:bg-bad/10`;

const CHIP = "rounded-full border px-2 py-0.5 text-xs";
export const CHIP_MUTED = `${CHIP} border-line text-muted`;
export const CHIP_ACCENT = `${CHIP} border-accent/60 text-accent`;
export const CHIP_OK = `${CHIP} border-ok/60 text-ok`;
export const CHIP_BAD = `${CHIP} border-bad/60 text-bad`;

export const INPUT = "w-full rounded-md border border-line bg-page px-2 py-1.5 text-sm text-ink outline-none focus:border-accent";
export const FIELD = "flex flex-col gap-1 text-xs text-muted";

export const TABLE = "w-full border-collapse text-left text-sm";
export const TH = "px-2 py-1.5 text-xs font-medium uppercase tracking-wide text-muted";
export const TD = "px-2 py-1.5";
export const KBD = "rounded border border-line bg-page px-1.5 py-0.5 font-mono text-xs";
export const CHIP_WARN = `${CHIP} border-warn/60 text-warn`;
export const CHIP_ON = `${CHIP} border-accent bg-accent/15 text-accent`;
export const CHIP_OFF = `${CHIP} border-line text-muted hover:text-ink`;

export const TILE = "rounded-md bg-page px-2 py-1";
export const TILE_LABEL = "text-xs text-muted";
export const TILE_VALUE = "font-medium tabular-nums";
