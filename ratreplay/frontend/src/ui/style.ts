// The class strings the pages share, so a button or a table looks the same everywhere.

// A button has a border and a fill that show on the dark and the light theme alike, the primary one the accent. A
// disabled primary button gives up the accent, since dark text on a faded blue cannot be read on either theme.
const PRIMARY_DISABLED = "disabled:bg-ink/10 disabled:font-normal disabled:text-ink";
const BUTTON_BASE = "rounded-md px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40";
export const BUTTON = `${BUTTON_BASE} border border-ink/30 bg-ink/5 text-ink enabled:hover:bg-ink/15`;
export const BUTTON_PRIMARY = `${BUTTON_BASE} bg-accent font-medium text-page enabled:hover:opacity-90 ${PRIMARY_DISABLED}`;
// A button that is only a glyph, square, the glyph an inline svg and the words in its aria-label and title.
export const BUTTON_ICON = "rounded-md border border-ink/30 bg-ink/5 p-1.5 text-ink enabled:hover:bg-ink/15 disabled:cursor-not-allowed disabled:opacity-40";
export const BUTTON_DANGER = `${BUTTON_BASE} border border-bad/60 text-bad enabled:hover:bg-bad/10`;

// Buttons of one group as one block, such as the zoom controls: SEGMENTS holds the SEGMENT buttons divided by the line colour,
// every segment a neutral fill with the ink as its text and a shade lighter or darker under the pointer. The primary action
// of a group is a SEGMENT_PRIMARY, which takes the accent only while it is enabled. A disabled segment is muted and says
// why in its title. GROUP_LABEL names a group beside its block, small muted capitals with room between the letters so it
// reads as a label and not as a button.
export const SEGMENTS = "inline-flex shrink-0 divide-x divide-ink/30 overflow-hidden rounded-md border border-ink/30";
const SEGMENT_BASE = "bg-ink/5 px-2.5 py-1.5 text-sm text-ink disabled:cursor-not-allowed disabled:text-ink/40";
// Every segment looks and hovers like a plain BUTTON, Kyle's call after using it: no accent in a group.
export const SEGMENT = `${SEGMENT_BASE} enabled:hover:bg-ink/15`;
export const SEGMENT_PRIMARY = SEGMENT;
export const GROUP_LABEL = "text-[11px] font-semibold uppercase tracking-[0.14em] text-muted";

// A layer toggle of the timeline as one plain box holding its checkbox, its word and the colour dot after the word, with
// the line colour as its border. Put the same gap between boxes.
export const LAYER_TOGGLE = "inline-flex shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-line px-2.5 py-1 text-xs hover:bg-ink/10";

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
// A key cap, not a button: a small raised key with a line under it, monospace, with a title saying what pressing the key does.
export const KBD = "cursor-default select-none rounded border border-ink/30 bg-page px-1.5 py-0.5 font-mono text-xs text-ink shadow-[0_1px_0_color-mix(in_oklab,var(--ink)_40%,transparent)]";
export const CHIP_WARN = `${CHIP} border-warn/60 text-warn`;
export const CHIP_ON = `${CHIP} border-accent bg-accent/15 text-accent`;
export const CHIP_OFF = `${CHIP} border-line text-muted hover:text-ink`;

export const TILE = "rounded-md bg-page px-2 py-1";
export const TILE_LABEL = "text-xs text-muted";
export const TILE_VALUE = "font-medium tabular-nums";

/**
 * The `:disabled` and `:title` attributes of a button that is disabled while the Alpine expression `off` is true. A
 * disabled button says why on hover (`reason`, plain words such as "select a block first"), an enabled one carries its
 * usual `title`. Put it where the `:disabled` and `title` attributes were.
 */
export function disabledWhy(off: string, reason: string, title = ""): string {
  const text = (words: string) => words.replace(/'/g, "\\'").replace(/"/g, "&quot;");
  return `:disabled="${off}" :title="${off} ? '${text(reason)}' : '${text(title)}'"`;
}
