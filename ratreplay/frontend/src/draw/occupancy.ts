import { rgb } from "d3";
import type { SessionHeader } from "../api/types";
import { epochAt } from "../session/at";
import type { Palette } from "../ui/palette";
import type { Backdrop, Extent, Projection } from "./map";

const OCCUPANCY_ALPHA = 0.55;

export const CURRENT = "current";
export const ALL = "all";

/** Where the animal spent time in the session's epochs, behind its map in camera pixels, y down: the epoch under the cursor, every epoch, or one by name. */
export class OccupancyBackdrop implements Backdrop {
  readonly yUp = false;
  readonly extent: Extent;
  choice = CURRENT;
  private images = new Map<string, HTMLCanvasElement>();

  constructor(private readonly header: Pick<SessionHeader, "occupancy" | "epochs">) {
    this.extent = { x: header.occupancy.x, y: header.occupancy.y };
  }

  speedText(top: number): string {
    return `0 to ${Math.round(top)} px/s`;
  }

  refresh(): void {
    this.images.clear();
  }

  draw(ctx: CanvasRenderingContext2D, project: Projection, colours: Palette, index: number): void {
    const { counts } = this.header.occupancy;
    const names = this.choice === ALL ? Object.keys(counts) : [this.choice === CURRENT ? epochAt(this.header.epochs, index + 1) : this.choice];
    const [left, right] = project.x.range();
    const [top, bottom] = project.y.range();
    ctx.imageSmoothingEnabled = false;
    for (const name of names) {
      const image = this.image(name, colours.ink);
      if (image) ctx.drawImage(image, left, top, right - left, bottom - top);
    }
  }

  /** The counts of an epoch as a small image, one pixel per bin and the row of the lowest y first, drawn in the ink of the theme. */
  private image(epoch: string, ink: string): HTMLCanvasElement | null {
    const { bins, counts } = this.header.occupancy;
    if (!counts[epoch]) return null;
    if (!this.images.has(epoch)) {
      const image = document.createElement("canvas");
      image.width = image.height = bins;
      const ctx = image.getContext("2d")!;
      const pixels = ctx.createImageData(bins, bins);
      const top = Math.log1p(Math.max(...counts[epoch]));
      const colour = rgb(ink);
      counts[epoch].forEach((count, i) => {
        pixels.data.set([colour.r, colour.g, colour.b, Math.round(255 * OCCUPANCY_ALPHA * (Math.log1p(count) / top))], 4 * i);
      });
      ctx.putImageData(pixels, 0, 0);
      this.images.set(epoch, image);
    }
    return this.images.get(epoch)!;
  }
}
