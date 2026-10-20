import type { Geometry } from "../api/types";
import { sizeCanvas, watchSize } from "../draw/canvas";
import { EnvironmentBackdrop } from "../draw/environment";
import { fitScales } from "../draw/map";
import type { Extent } from "../draw/map";
import { palette } from "../ui/palette";

/** The height of a thumbnail's drawing, about the size every drawing had before one was shown large. */
export const THUMBNAIL_HEIGHT_PX = 160;

/** An environment's geometry drawn on a canvas that fills its host, in metres with y up, on the extent it is given so that several drawings can share one scale. */
export class GeometryView {
  private readonly canvas = document.createElement("canvas");
  private readonly backdrop: EnvironmentBackdrop;
  private readonly stopWatching: () => void;
  private width = 0;
  private height = 0;

  constructor(host: HTMLElement, geometry: Geometry, extent: Extent) {
    this.backdrop = new EnvironmentBackdrop(geometry, extent);
    this.canvas.className = "absolute left-0 top-0";
    host.append(this.canvas);
    this.stopWatching = watchSize(host, (width, height) => {
      [this.width, this.height] = [width, height];
      this.refresh();
    });
  }

  /** Draw again in the colours of the theme, after a toggle or a new size. */
  refresh(): void {
    if (!this.width || !this.height) return;
    const ctx = sizeCanvas(this.canvas, this.width, this.height);
    this.backdrop.draw(ctx, fitScales(this.backdrop.extent, this.width, this.height, true), palette());
  }

  destroy(): void {
    this.stopWatching();
    this.canvas.remove();
  }
}
