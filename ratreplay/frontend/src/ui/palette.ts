const NAMES = ["page", "card", "line", "ink", "muted", "accent", "ok", "warn", "bad"] as const;

export type Palette = Record<(typeof NAMES)[number], string>;

/** The theme's colours as the canvases need them, read from the CSS variables so a theme toggle only has to redraw. */
export function palette(): Palette {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(NAMES.map((name) => [name, style.getPropertyValue(`--${name}`).trim()])) as Palette;
}

/** The colour a name stands for: a colour of the theme, else a CSS colour as it stands. */
export function colourOf(colours: Palette, name: string): string {
  return (colours as Record<string, string>)[name] ?? name;
}
