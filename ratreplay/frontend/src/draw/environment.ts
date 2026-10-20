import type { Geometry } from "../api/types";
import type { Palette } from "../ui/palette";
import { withAlpha } from "./canvas";
import type { Backdrop, Extent, Projection } from "./map";

const FONT = "11px ui-sans-serif, system-ui, sans-serif";
const WALL_PX = 1.5;
const CENTERLINE_PX = 1;
const CENTERLINE_DASH = [2, 4];
const CENTERLINE_ALPHA = 0.6;
const SITE_RADIUS_PX = 5;
const SITE_LABEL_GAP_PX = 9;
const SITE_LABEL_DROP_PX = 15;
const SITE_LABEL_CLEARANCE_PX = 4;
const SAME_ROW_PX = 8;

interface LabelledSite {
  px: number;
  py: number;
  width: number;
}

/** Which sites put their label below the circle: those whose label, to the right of the circle, would reach the next site on their row. */
export function labelsBelow(sites: LabelledSite[]): boolean[] {
  return sites.map((site) =>
    sites.some(({ px, py }) => px > site.px && Math.abs(py - site.py) < SAME_ROW_PX
      && site.px + SITE_LABEL_GAP_PX + site.width + SITE_LABEL_CLEARANCE_PX > px - SITE_RADIUS_PX));
}

/** The extent in metres of the environment and of the path over it, so a path that strays off the drawn geometry shows. */
export function extentOf(geometry: Geometry, x: Float64Array, y: Float64Array): Extent {
  const { walls, boundary, centerline, reward_sites: sites, circle } = geometry;
  const points = [...walls.flat(), ...(boundary ?? []), ...centerline.flatMap((line) => [line.p0, line.p1]), ...Object.values(sites)];
  if (circle) points.push([circle.center[0] - circle.radius, circle.center[1] - circle.radius], [circle.center[0] + circle.radius, circle.center[1] + circle.radius]);
  const extent: Extent = { x: [Infinity, -Infinity], y: [Infinity, -Infinity] };
  const include = (px: number, py: number) => {
    if (!Number.isFinite(px) || !Number.isFinite(py)) return;
    extent.x = [Math.min(extent.x[0], px), Math.max(extent.x[1], px)];
    extent.y = [Math.min(extent.y[0], py), Math.max(extent.y[1], py)];
  };
  points.forEach(([px, py]) => include(px, py));
  for (let i = 0; i < x.length; i++) include(x[i], y[i]);
  return extent;
}

/** The environment config behind a block's map in metres, y up: the walls and the arena boundary as lines, the centerline dotted, the reward sites as named circles. */
export class EnvironmentBackdrop implements Backdrop {
  readonly yUp = true;

  constructor(private readonly geometry: Geometry, readonly extent: Extent) {}

  speedText(top: number): string {
    return `0 to ${top.toFixed(2)} m/s`;
  }

  draw(ctx: CanvasRenderingContext2D, { x, y }: Projection, colours: Palette): void {
    const { walls, boundary, centerline, reward_sites: sites, circle } = this.geometry;
    ctx.strokeStyle = colours.muted;
    ctx.lineWidth = WALL_PX;
    ctx.beginPath();
    const trace = (points: [number, number][]) => points.forEach(([px, py], i) => (i ? ctx.lineTo(x(px), y(py)) : ctx.moveTo(x(px), y(py))));
    walls.forEach((wall) => trace(wall));
    if (boundary) {
      trace(boundary);
      ctx.closePath();
    }
    if (circle) {
      ctx.moveTo(x(circle.center[0] + circle.radius), y(circle.center[1]));
      ctx.arc(x(circle.center[0]), y(circle.center[1]), Math.abs(x(circle.radius) - x(0)), 0, 2 * Math.PI);
    }
    ctx.stroke();

    ctx.strokeStyle = withAlpha(colours.muted, CENTERLINE_ALPHA);
    ctx.lineWidth = CENTERLINE_PX;
    ctx.setLineDash(CENTERLINE_DASH);
    ctx.beginPath();
    for (const { p0, p1 } of centerline) {
      ctx.moveTo(x(p0[0]), y(p0[1]));
      ctx.lineTo(x(p1[0]), y(p1[1]));
    }
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.font = FONT;
    ctx.textBaseline = "middle";
    const placed = Object.entries(sites).map(([name, [sx, sy]]) => ({ name, px: x(sx), py: y(sy), width: ctx.measureText(name).width }));
    const below = labelsBelow(placed);
    placed.forEach(({ name, px, py }, i) => {
      ctx.fillStyle = colours.card;
      ctx.strokeStyle = colours.ink;
      ctx.lineWidth = WALL_PX;
      ctx.beginPath();
      ctx.arc(px, py, SITE_RADIUS_PX, 0, 2 * Math.PI);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = colours.muted;
      ctx.textAlign = below[i] ? "center" : "left";
      ctx.fillText(name, below[i] ? px : px + SITE_LABEL_GAP_PX, below[i] ? py + SITE_LABEL_DROP_PX : py);
    });
  }
}
