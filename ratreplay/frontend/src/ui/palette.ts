export const PALETTE_NAMES = [
  "page", "card", "line", "ink", "muted", "accent", "ok", "warn", "bad", "neutral", "arena", "track", "soft", "cursor", "trip",
  "lost", "jumped", "trimmed", "hd-missing", "hd-filled", "hd-held", "speed",
] as const;

export type Palette = Record<(typeof PALETTE_NAMES)[number], string>;

const CSS_VARIABLE = /^var\(--([\w-]+)\)$/;

/** The theme's colours as the canvases need them, read from the CSS variables so a theme toggle only has to redraw. */
export function palette(): Palette {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(PALETTE_NAMES.map((name) => [name, style.getPropertyValue(`--${name}`).trim()])) as Palette;
}

/** The colour a name stands for: a colour of the theme by its name or as `var(--name)`, else a CSS colour as it stands. */
export function colourOf(colours: Palette, name: string): string {
  const token = CSS_VARIABLE.exec(name)?.[1] ?? name;
  return (colours as Record<string, string>)[token] ?? name;
}
