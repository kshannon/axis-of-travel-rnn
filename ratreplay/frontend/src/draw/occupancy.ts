import { rgb } from "d3";
import type { Epoch, SessionHeader } from "../api/types";
import { epochAt } from "../session/at";
import type { Palette } from "../ui/palette";
import { EnvironmentBackdrop } from "./environment";
import type { Backdrop, Extent, Projection } from "./map";

const OCCUPANCY_ALPHA = 0.55;

export const CURRENT = "current";
export const ALL = "all";

type Drawn = Pick<SessionHeader, "occupancy" | "epochs" | "selected_epochs" | "environments">;

/** The epoch kinds a choice shows at a frame index: the epoch under the cursor, every epoch the rules cut, or one by name. */
export function epochsShown(header: Pick<SessionHeader, "epochs" | "selected_epochs">, choice: string, index: number): string[] {
  if (choice === ALL) return header.selected_epochs;
  return [choice === CURRENT ? epochAt(header.epochs, index + 1) : choice];
}

/** The environments of the epochs a choice shows at a frame index, each once, an epoch the rules do not cut having none. */
export function environmentsShown(header: Pick<SessionHeader, "epochs" | "selected_epochs" | "environments">, choice: string, index: number): string[] {
  const frame = index + 1;
  const shown = (e: Epoch) => (choice === CURRENT ? e.frame_start <= frame && frame <= e.frame_end : header.selected_epochs.includes(e.epoch) && (choice === ALL || e.epoch === choice));
  return [...new Set(header.epochs.filter(shown).map((e) => e.environment).filter((name) => header.environments[name]))];
}

/** The room's rectangle on the canvas where the projection puts it, the extent of the occupancy through the same scales as the path, so it does not depend on what else the projection fits. */
export function roomRect({ x, y }: Projection, extent: Extent): { left: number; top: number; width: number; height: number } {
  const top = y(extent.y[1]);
  return { left: x(extent.x[0]), top, width: x(extent.x[1]) - x(extent.x[0]), height: y(extent.y[0]) - top };
}

/** The counts row by row from the highest y, as the pixels of an image run from its top, the engine's rows are from the lowest y. */
export function rowsFromTop(counts: number[], bins: number): number[] {
  return Array.from({ length: bins }, (_, row) => counts.slice((bins - 1 - row) * bins, (bins - row) * bins)).flat();
}

/** The room in metres, y up, behind the map: the occupancy of the epochs shown with the geometry of their environments over it. */
export class OccupancyBackdrop implements Backdrop {
  readonly yUp = true;
  readonly extent: Extent;
  choice = CURRENT;
  private images = new Map<string, HTMLCanvasElement>();
  private environments = new Map<string, EnvironmentBackdrop>();

  constructor(private readonly header: Drawn) {
    this.extent = { x: header.occupancy.x, y: header.occupancy.y };
    for (const [name, geometry] of Object.entries(header.environments)) this.environments.set(name, new EnvironmentBackdrop(geometry, this.extent));
  }

  speedText(top: number): string {
    return `0 to ${top.toFixed(2)} m/s`;
  }

  refresh(): void {
    this.images.clear();
  }

  draw(ctx: CanvasRenderingContext2D, project: Projection, colours: Palette, index: number): void {
    const kinds = epochsShown(this.header, this.choice, index);
    const { left, top, width, height } = roomRect(project, this.extent);
    ctx.imageSmoothingEnabled = false;
    for (const kind of kinds) {
      const image = this.image(kind, colours.ink);
      if (image) ctx.drawImage(image, left, top, width, height);
    }
    for (const name of environmentsShown(this.header, this.choice, index)) this.environments.get(name)!.draw(ctx, project, colours);
  }

  /** The counts of an epoch as a small image, one pixel per bin and the row of the highest y first, drawn in the ink of the theme. */
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
      rowsFromTop(counts[epoch], bins).forEach((count, i) => {
        pixels.data.set([colour.r, colour.g, colour.b, Math.round(255 * OCCUPANCY_ALPHA * (Math.log1p(count) / top))], 4 * i);
      });
      ctx.putImageData(pixels, 0, 0);
      this.images.set(epoch, image);
    }
    return this.images.get(epoch)!;
  }
}
