export type LayerKey = "pauses" | "gaps" | "jumps" | "margins" | "lost" | "filled" | "held" | "speed";
export type Layers = Record<LayerKey, boolean>;

/** The layers of the frames lane that a chip toggles, each with the colour it is drawn in. */
export const LAYERS: readonly { key: LayerKey; label: string; colour: string }[] = [
  { key: "pauses", label: "pauses", colour: "#ec4899" },
  { key: "gaps", label: "gaps", colour: "#9ca3af" },
  { key: "jumps", label: "jumps", colour: "#ef4444" },
  { key: "margins", label: "margins", colour: "#000000" },
  { key: "lost", label: "heading lost", colour: "#f97316" },
  { key: "filled", label: "heading filled", colour: "#facc15" },
  { key: "held", label: "heading held", colour: "#2dd4bf" },
  { key: "speed", label: "speed", colour: "#94a3b8" },
];

export const colourOf = (key: LayerKey): string => LAYERS.find((layer) => layer.key === key)!.colour;

export function allLayers(): Layers {
  return Object.fromEntries(LAYERS.map((layer) => [layer.key, true])) as Layers;
}
