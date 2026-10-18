import type { Geometry } from "../api/types";
import { sizeCanvas } from "../draw/canvas";
import { EnvironmentBackdrop } from "../draw/environment";
import { fitScales } from "../draw/map";
import type { Extent } from "../draw/map";
import { palette } from "../ui/palette";

export const WIDTH_PX = 208;
export const HEIGHT_PX = 160;

/** An environment's geometry drawn small on a canvas of its own, in metres with y up, on the extent it is given so that several share one scale. */
export class GeometryView {
  private readonly canvas = document.createElement("canvas");
  private readonly backdrop: EnvironmentBackdrop;

  constructor(host: HTMLElement, geometry: Geometry, extent: Extent) {
    this.backdrop = new EnvironmentBackdrop(geometry, extent);
    host.append(this.canvas);
    this.refresh();
  }

  /** Draw again in the colours of the theme, after a toggle. */
  refresh(): void {
    const ctx = sizeCanvas(this.canvas, WIDTH_PX, HEIGHT_PX);
    this.backdrop.draw(ctx, fitScales(this.backdrop.extent, WIDTH_PX, HEIGHT_PX, true), palette());
  }

  destroy(): void {
    this.canvas.remove();
  }
}
