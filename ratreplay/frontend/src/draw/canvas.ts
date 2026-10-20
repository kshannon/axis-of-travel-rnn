import { color, interpolateRgb } from "d3";

/** Size a canvas to a box in CSS pixels at the screen's pixel ratio, and give back a context that draws in CSS pixels. */
export function sizeCanvas(canvas: HTMLCanvasElement, width: number, height: number): CanvasRenderingContext2D {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return ctx;
}

/** Call back with the element's size now and whenever it changes, give back the function that stops watching. */
export function watchSize(element: HTMLElement, onSize: (width: number, height: number) => void): () => void {
  const observer = new ResizeObserver(([entry]) => onSize(entry.contentRect.width, entry.contentRect.height));
  observer.observe(element);
  return () => observer.disconnect();
}

// How far toward white a lighter shade goes.
const LIGHTER_SHARE = 0.45;

/** The colour in a lighter shade, the same hue partway to white. */
export function lighter(colour: string): string {
  return interpolateRgb(colour, "white")(LIGHTER_SHARE);
}

export function withAlpha(colour: string, opacity: number): string {
  return color(colour)!.copy({ opacity }).formatRgb();
}
