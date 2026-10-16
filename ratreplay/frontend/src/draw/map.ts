import { interpolateViridis, rgb, scaleLinear, scaleSequential } from "d3";
import type { ScaleLinear } from "d3";
import type { SessionArrays, SessionHeader } from "../api/types";
import { epochAt } from "../session/at";
import { palette } from "../ui/palette";
import type { Palette } from "../ui/palette";
import { sizeCanvas, watchSize, withAlpha } from "./canvas";

const FONT = "11px ui-sans-serif, system-ui, sans-serif";
const PAD_PX = 16;
const OCCUPANCY_ALPHA = 0.55;
const TRAIL_S = 2;
const TRAIL_HZ = 20;
const TRAIL_WIDTH_PX = 3;
const PATH_HZ = 4;
const PATH_ALPHA = 0.35;
const POINT_RADIUS_PX = 6;
const ARROW_FRACTION = 0.08;
const ARROW_HEAD_PX = 7;
const ARROW_COLOUR = "#ef4444";
const LEGEND = { width: 90, height: 8, steps: 18 };

// The slowest colours of the trail are lifted off the darkest end of the scale so they stay visible on a dark card.
const COLOUR_FLOOR = 0.15;

export const CURRENT = "current";
export const ALL = "all";

/** The map of a session in camera pixels with y down: the occupancy of the epoch, the selected block's path, the last seconds as a trail coloured by speed, the current point and its heading. */
export class MapView {
  private readonly canvas = document.createElement("canvas");
  private ctx!: CanvasRenderingContext2D;
  private readonly stopWatching: () => void;
  private width = 0;
  private height = 0;
  private colours: Palette = palette();
  private x: ScaleLinear<number, number> = scaleLinear();
  private y: ScaleLinear<number, number> = scaleLinear();
  private speedColour = scaleSequential((t: number) => interpolateViridis(COLOUR_FLOOR + (1 - COLOUR_FLOOR) * t)).clamp(true);

  private header: SessionHeader | null = null;
  private arrays: SessionArrays | null = null;
  private occupancy = new Map<string, HTMLCanvasElement>();
  private choice = CURRENT;
  private path: [number, number] | null = null;
  private index = 0;

  constructor(host: HTMLElement) {
    this.canvas.className = "absolute left-0 top-0";
    host.append(this.canvas);
    this.stopWatching = watchSize(host, (width, height) => this.resize(width, height));
  }

  load(header: SessionHeader, arrays: SessionArrays, speedTop: number): void {
    this.header = header;
    this.arrays = arrays;
    this.speedColour.domain([0, speedTop]);
    this.occupancy.clear();
    this.fitScales();
    this.draw(this.index);
  }

  /** Which occupancy to draw behind the path: the epoch under the cursor, every epoch, or one epoch by name. */
  setOccupancy(choice: string): void {
    this.choice = choice;
    this.draw(this.index);
  }

  /** The lab frames of the block whose whole path is drawn thin, none for no block. */
  setPath(frames: [number, number] | null): void {
    this.path = frames;
    this.draw(this.index);
  }

  refresh(): void {
    this.colours = palette();
    this.occupancy.clear();
    this.draw(this.index);
  }

  destroy(): void {
    this.stopWatching();
    this.canvas.remove();
  }

  private resize(width: number, height: number): void {
    this.width = width;
    this.height = height;
    this.ctx = sizeCanvas(this.canvas, width, height);
    this.fitScales();
    this.draw(this.index);
  }

  /** Equal scales in x and y, centred, over the extent of the positions with a margin. */
  private fitScales(): void {
    if (!this.header) return;
    const { x, y } = this.header.occupancy;
    const room = { width: this.width - 2 * PAD_PX, height: this.height - 2 * PAD_PX };
    const pixels = Math.max(Math.min(room.width / (x[1] - x[0] || 1), room.height / (y[1] - y[0] || 1)), 0);
    const [spanX, spanY] = [(x[1] - x[0]) * pixels, (y[1] - y[0]) * pixels];
    const left = (this.width - spanX) / 2;
    const top = (this.height - spanY) / 2;
    this.x = scaleLinear().domain(x).range([left, left + spanX]);
    this.y = scaleLinear().domain(y).range([top, top + spanY]);
  }

  /** The counts of an epoch as a small image, one pixel per bin and the row of the lowest y first, drawn in the ink of the theme. */
  private occupancyImage(epoch: string): HTMLCanvasElement | null {
    const grid = this.header!.occupancy;
    const counts = grid.counts[epoch];
    if (!counts) return null;
    if (!this.occupancy.has(epoch)) {
      const image = document.createElement("canvas");
      image.width = image.height = grid.bins;
      const ctx = image.getContext("2d")!;
      const pixels = ctx.createImageData(grid.bins, grid.bins);
      const top = Math.log1p(Math.max(...counts));
      const ink = rgb(this.colours.ink);
      counts.forEach((count, i) => {
        pixels.data.set([ink.r, ink.g, ink.b, Math.round(255 * OCCUPANCY_ALPHA * (Math.log1p(count) / top))], 4 * i);
      });
      ctx.putImageData(pixels, 0, 0);
      this.occupancy.set(epoch, image);
    }
    return this.occupancy.get(epoch)!;
  }

  /** Draw the session at a frame index. */
  draw(index: number): void {
    this.index = index;
    if (!this.header || !this.arrays || this.width === 0) return;
    const { ctx, colours: c } = this;
    ctx.clearRect(0, 0, this.width, this.height);
    this.drawOccupancy(ctx);
    this.drawPath(ctx);
    this.drawTrail(ctx);
    this.drawPoint(ctx);
    this.drawLegend(ctx, c);
  }

  private drawOccupancy(ctx: CanvasRenderingContext2D): void {
    const header = this.header!;
    const names = this.choice === ALL ? Object.keys(header.occupancy.counts)
      : [this.choice === CURRENT ? epochAt(header.epochs, this.index + 1) : this.choice];
    ctx.imageSmoothingEnabled = false;
    for (const name of names) {
      const image = this.occupancyImage(name);
      if (image) ctx.drawImage(image, this.x.range()[0], this.y.range()[0], this.x.range()[1] - this.x.range()[0], this.y.range()[1] - this.y.range()[0]);
    }
  }

  private drawPath(ctx: CanvasRenderingContext2D): void {
    if (!this.path) return;
    const { x, y } = this.arrays!;
    const step = Math.max(1, Math.round(this.header!.rate_hz / PATH_HZ));
    ctx.strokeStyle = withAlpha(this.colours.ink, PATH_ALPHA);
    ctx.lineWidth = 1;
    ctx.beginPath();
    let drawing = false;
    for (let i = this.path[0] - 1; i < this.path[1]; i += step) {
      if (Number.isNaN(x[i]) || Number.isNaN(y[i])) {
        drawing = false;
        continue;
      }
      if (drawing) ctx.lineTo(this.x(x[i]), this.y(y[i]));
      else ctx.moveTo(this.x(x[i]), this.y(y[i]));
      drawing = true;
    }
    ctx.stroke();
  }

  /** The last TRAIL_S seconds at TRAIL_HZ, each segment in the colour of the speed where it ends. */
  private drawTrail(ctx: CanvasRenderingContext2D): void {
    const { x, y, speed } = this.arrays!;
    const rate = this.header!.rate_hz;
    const step = Math.max(1, Math.round(rate / TRAIL_HZ));
    const first = Math.max(0, this.index - TRAIL_S * rate);
    ctx.lineWidth = TRAIL_WIDTH_PX;
    ctx.lineCap = "round";
    for (let i = this.index; i - step >= first; i -= step) {
      const from = i - step;
      if (Number.isNaN(x[i]) || Number.isNaN(x[from])) continue;
      ctx.strokeStyle = this.speedColour(Number.isNaN(speed[i]) ? 0 : speed[i]);
      ctx.beginPath();
      ctx.moveTo(this.x(x[from]), this.y(y[from]));
      ctx.lineTo(this.x(x[i]), this.y(y[i]));
      ctx.stroke();
    }
  }

  /** The current point with an arrow along the corrected heading, as long as ARROW_FRACTION of the map's width. */
  private drawPoint(ctx: CanvasRenderingContext2D): void {
    const { x, y, heading } = this.arrays!;
    const i = this.index;
    if (Number.isNaN(x[i])) return;
    const [px, py] = [this.x(x[i]), this.y(y[i])];
    if (!Number.isNaN(heading[i])) {
      const length = ARROW_FRACTION * (this.x.range()[1] - this.x.range()[0]);
      const [tx, ty] = [px + length * Math.cos(heading[i]), py + length * Math.sin(heading[i])];
      ctx.strokeStyle = ctx.fillStyle = ARROW_COLOUR;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(tx, ty);
      ctx.stroke();
      const back = heading[i] + Math.PI;
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      for (const side of [-0.45, 0.45]) ctx.lineTo(tx + ARROW_HEAD_PX * Math.cos(back + side), ty + ARROW_HEAD_PX * Math.sin(back + side));
      ctx.fill();
    }
    ctx.fillStyle = ARROW_COLOUR;
    ctx.strokeStyle = this.colours.ink;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(px, py, POINT_RADIUS_PX, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
  }

  /** The speed colours as a small bar in the corner with the fastest speed written beside it. */
  private drawLegend(ctx: CanvasRenderingContext2D, c: Palette): void {
    const [low, high] = this.speedColour.domain();
    const top = this.height - PAD_PX / 2 - LEGEND.height;
    const cell = LEGEND.width / LEGEND.steps;
    for (let i = 0; i < LEGEND.steps; i++) {
      ctx.fillStyle = this.speedColour(low + ((high - low) * i) / (LEGEND.steps - 1));
      ctx.fillRect(PAD_PX / 2 + i * cell, top, cell + 0.5, LEGEND.height);
    }
    ctx.font = FONT;
    ctx.fillStyle = c.muted;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(`0 to ${Math.round(high)} px/s`, PAD_PX / 2 + LEGEND.width + 6, top + LEGEND.height / 2);
  }
}
