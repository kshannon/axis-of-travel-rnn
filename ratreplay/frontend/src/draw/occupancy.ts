import { rgb } from "d3";
import type { Epoch, SessionHeader } from "../api/types";
import { epochAt } from "../session/at";
import type { Palette } from "../ui/palette";
import { EnvironmentBackdrop } from "./environment";
import type { Backdrop, Extent, Projection } from "./map";

const OCCUPANCY_ALPHA = 0.55;

/** The scope that draws the epoch under the cursor, and the one that draws every selected epoch. Any other scope is the name of one epoch kind, such as "arena". */
export const FOLLOW_CURSOR = "follow";
export const ALL_EPOCHS = "all";

/** What the map draws of the room: the occupancy and the geometry of the environments, each on or off on its own, and the epochs they are drawn for. The trail is the map view's. */
export interface MapChoice {
  occupancy: boolean;
  geometry: boolean;
  /** The epochs drawn: FOLLOW_CURSOR, ALL_EPOCHS or one epoch kind by name. Exactly one holds. */
  scope: string;
}

/** Occupancy and geometry on, following the epoch under the cursor. */
export function defaultMapChoice(): MapChoice {
  return { occupancy: true, geometry: true, scope: FOLLOW_CURSOR };
}

export interface ScopeOption {
  value: string;
  label: string;
  title: string;
}

/** The choices of the epoch scope for a session: follow the cursor, each selected kind, then every kind together when there is more than one, called both for two kinds and all for more. */
export function scopeOptions(kinds: string[]): ScopeOption[] {
  const together = kinds.length > 2 ? "all" : "both";
  return [
    { value: FOLLOW_CURSOR, label: "follow cursor", title: "Draw only the epoch under the cursor, the map changes where the cursor crosses into the next epoch" },
    ...kinds.map((kind) => ({ value: kind, label: kind, title: `Draw the ${kind} epoch only` })),
    ...(kinds.length > 1 ? [{ value: ALL_EPOCHS, label: together, title: `Draw ${kinds.join(" and ")} together` }] : []),
  ];
}

type Drawn = Pick<SessionHeader, "occupancy" | "epochs" | "selected_epochs" | "environments">;

/** The epoch kinds a scope shows at a frame index: the kind under the cursor, one kind, or every selected kind. A kind the rules do not select is never shown. */
export function epochsShown(header: Pick<SessionHeader, "epochs" | "selected_epochs">, scope: string, index: number): string[] {
  if (scope === ALL_EPOCHS) return header.selected_epochs;
  const wanted = scope === FOLLOW_CURSOR ? epochAt(header.epochs, index + 1) : scope;
  return header.selected_epochs.filter((kind) => kind === wanted);
}

/** The environments of the epochs a scope shows at a frame index, each once. With the cursor followed only the epoch holding the frame counts, and an epoch the rules do not cut has no environment. */
export function environmentsShown(header: Pick<SessionHeader, "epochs" | "selected_epochs" | "environments">, scope: string, index: number): string[] {
  const frame = index + 1;
  const kinds = epochsShown(header, scope, index);
  const shown = (e: Epoch) => kinds.includes(e.epoch) && (scope !== FOLLOW_CURSOR || (e.frame_start <= frame && frame <= e.frame_end));
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
      for (const kind of epochsShown(this.header, this.choice.scope, index)) {
        const image = this.image(kind, colours.ink);
        if (image) ctx.drawImage(image, left, top, width, height);
      }
    }
    if (this.choice.geometry) for (const name of environmentsShown(this.header, this.choice.scope, index)) this.environments.get(name)!.draw(ctx, project, colours);
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
