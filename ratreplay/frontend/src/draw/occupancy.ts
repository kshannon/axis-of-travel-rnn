import { rgb } from "d3";
import type { Epoch, SessionHeader } from "../api/types";
import { epochAt } from "../session/at";
import type { Palette } from "../ui/palette";
import { EnvironmentBackdrop } from "./environment";
import type { Backdrop, Extent, Projection } from "./map";

const OCCUPANCY_ALPHA = 0.55;

/**
 * What the map draws of the room, each on or off on its own: the occupancy, the geometry of the environments, the epoch kinds
 * (arena and track) and whether only the epoch under the cursor is drawn. The trail is the map view's.
 */
export interface MapChoice {
  occupancy: boolean;
  geometry: boolean;
  /** Only the epoch under the cursor, out of the kinds that are on. */
  follow: boolean;
  /** Which epoch kinds are on, by name. A page adds each kind of a session as on when it opens it. */
  kinds: Record<string, boolean>;
}

/** Occupancy and geometry on, following the epoch under the cursor. */
export function defaultMapChoice(): MapChoice {
  return { occupancy: true, geometry: true, follow: true, kinds: {} };
}

type Drawn = Pick<SessionHeader, "occupancy" | "epochs" | "selected_epochs" | "environments">;

/** The epoch kinds a choice shows at a frame index: those that are on, and with follow only the one under the cursor. */
export function epochsShown(header: Pick<SessionHeader, "epochs" | "selected_epochs">, choice: MapChoice, index: number): string[] {
  const on = header.selected_epochs.filter((kind) => choice.kinds[kind]);
  return choice.follow ? on.filter((kind) => kind === epochAt(header.epochs, index + 1)) : on;
}

/** The environments of the epochs a choice shows at a frame index, each once, an epoch the rules do not cut having none. */
export function environmentsShown(header: Pick<SessionHeader, "epochs" | "selected_epochs" | "environments">, choice: MapChoice, index: number): string[] {
  const frame = index + 1;
  const kinds = epochsShown(header, { ...choice, follow: false }, index);
  const shown = (e: Epoch) => kinds.includes(e.epoch) && (!choice.follow || (e.frame_start <= frame && frame <= e.frame_end));
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

/** The room in metres, y up, behind the map: the occupancy of the epochs shown and the geometry of their environments, each when it is on. */
export class OccupancyBackdrop implements Backdrop {
  readonly yUp = true;
  readonly extent: Extent;
  choice: MapChoice = defaultMapChoice();
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
    const { left, top, width, height } = roomRect(project, this.extent);
    ctx.imageSmoothingEnabled = false;
    if (this.choice.occupancy) {
      for (const kind of epochsShown(this.header, this.choice, index)) {
        const image = this.image(kind, colours.ink);
        if (image) ctx.drawImage(image, left, top, width, height);
      }
    }
    if (this.choice.geometry) for (const name of environmentsShown(this.header, this.choice, index)) this.environments.get(name)!.draw(ctx, project, colours);
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
