import type { SessionHeader } from "../api/types";

export type LayerKey = "gaps" | "jumps" | "margins" | "lost" | "filled" | "held" | "speed";
export type Layers = Record<LayerKey, boolean>;

/** What happened to the head direction of a frame, the words saying whose work it is. */
export const HEAD_DIR = { lost: "missing", filled: "interpolated by RatReplay", held: "held by RatReplay" } as const;

/**
 * The layers of the frames lane that a checkbox toggles, each with the colour it is drawn in and its toggle dot shows. A
 * colour is a CSS variable of the theme, one per layer and borrowed from no bar, so the dot and the lane follow the theme
 * and a layer is told from the others, the trips and the blocks at a glance. The words say whose work it is. A pause is
 * no layer, it is dead time and is always drawn as a break across every lane.
 */
export const LAYERS: readonly { key: LayerKey; label: string; colour: string }[] = [
  { key: "gaps", label: "tracking lost", colour: "var(--lost)" },
  { key: "jumps", label: "position jumped", colour: "var(--jumped)" },
  { key: "margins", label: "margins trimmed", colour: "var(--trimmed)" },
  { key: "lost", label: `head dir ${HEAD_DIR.lost}`, colour: "var(--hd-missing)" },
  { key: "filled", label: `head dir ${HEAD_DIR.filled}`, colour: "var(--hd-filled)" },
  { key: "held", label: `head dir ${HEAD_DIR.held}`, colour: "var(--hd-held)" },
  { key: "speed", label: "speed", colour: "var(--speed)" },
];

export const colourOf = (key: LayerKey): string => LAYERS.find((layer) => layer.key === key)!.colour;

export function allLayers(): Layers {
  return Object.fromEntries(LAYERS.map((layer) => [layer.key, true])) as Layers;
}

const DECIMALS = 2;

/** One line of what each layer means, with the numbers of the rules the session was cut under and the lab's max gap, so the words follow the engine. */
export function layerMeanings(header: Pick<SessionHeader, "rules" | "max_gap">, speedTop: number): Record<LayerKey, string> {
  const { rules, max_gap: maxGap } = header;
  const lights = rules.gap_lights === "both" ? "both lights" : "a light";
  return {
    gaps: `striped bar, lights filled by the lab up to ${maxGap} frames, ${lights} lost for longer`,
    jumps: `moved over ${rules.jump_px} px in one frame, a tick`,
    margins: `${rules.pause_margin_s} s trimmed beside a pause, jump or epoch bound`,
    lost: "no head direction measured or filled, bottom band",
    filled: `gap up to ${rules.heading_fill_s} s filled along the shortest arc`,
    held: `a longer gap, rat under ${rules.running_floor_m_per_s} m/s, last direction kept`,
    speed: `a trace, the full height is ${speedTop.toFixed(DECIMALS)} m/s`,
  };
}
