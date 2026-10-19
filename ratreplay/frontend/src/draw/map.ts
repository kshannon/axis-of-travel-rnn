import { interpolateMagma, scaleLinear, scaleSequential } from "d3";
import type { ScaleLinear } from "d3";
import { colourOf, palette } from "../ui/palette";
import type { Palette } from "../ui/palette";
import { currentTheme } from "../ui/theme";
import { lighter, sizeCanvas, watchSize, withAlpha } from "./canvas";

const FONT = "11px ui-sans-serif, system-ui, sans-serif";
const PAD_PX = 16;
const TRAIL_S = 2;
const TRAIL_HZ = 20;
const TRAIL_WIDTH_PX = 4.5;
const PATH_HZ = 10;
const POINT_RADIUS_PX = 6;
const ARROW_FRACTION = 0.08;
const ARROW_HEAD_PX = 7;
const LEGEND = { width: 90, height: 8, steps: 18 };

// The trail's speed colours are the magma scale. Magma runs from black to pale yellow, so each theme uses the part of it that
// shows on its card: the dark theme lifts the slowest colour off the black, the light theme stops short of the pale yellow.
const MAGMA_RANGE = { dark: [0.35, 1], light: [0, 0.8] } as const;

export interface Extent {
  x: [number, number];
  y: [number, number];
}

export interface Projection {
  x: ScaleLinear<number, number>;
  y: ScaleLinear<number, number>;
}

/** What a map draws under the path, in the units of the positions. */
export interface Backdrop {
  /** The extent of the positions the map has to fit. */
  extent: Extent;
  /** Whether y grows up the screen, as in a room, and not down it, as in a camera image. */
  yUp: boolean;
  /** The words beside the speed colours for the fastest speed. */
  speedText(top: number): string;
  draw(ctx: CanvasRenderingContext2D, project: Projection, colours: Palette, index: number): void;
  /** Drop what was drawn in the colours of the theme, after a toggle. */
  refresh?(): void;
}

/** The positions of a recording, one per frame, and the heading and speed that go with them. */
export interface Track {
  /** The measured position: the current point and the heading arrow are drawn here. */
  x: Float64Array;
  y: Float64Array;
  /** The smoothed position the trail and the paths are drawn along, where the recording has one (a built block holds the raw position only). */
  x_smooth?: Float64Array;
  y_smooth?: Float64Array;
  heading: Float64Array;
  speed: Float64Array;
  rateHz: number;
}

/** A stretch of lab frames from 1, both ends included, drawn as a line of its own. */
export interface Stretch {
  first: number;
  last: number;
  /** A palette colour name or a CSS colour. */
  colour: string;
  alpha: number;
  width: number;
  /** Drawn in a lighter shade of its colour. */
  light?: boolean;
}

/** The thin line the path of a block or a selection is drawn in behind the trail. */
export const THIN_PATH = { colour: "ink", alpha: 0.35, width: 1 };

/** The position the trail and the paths pass through at a frame: the smoothed one, the measured one where the smoothed one is NaN or the track holds none. */
export function drawnAt(track: Track, i: number): [number, number] {
  const [x, y] = [track.x_smooth?.[i] ?? NaN, track.y_smooth?.[i] ?? NaN];
  return Number.isNaN(x) || Number.isNaN(y) ? [track.x[i], track.y[i]] : [x, y];
}

/** Equal scales in x and y, the extent centred in the box with a margin, y running up the screen when yUp. */
export function fitScales(extent: Extent, width: number, height: number, yUp: boolean): Projection {
  const { x, y } = extent;
  const room = { width: width - 2 * PAD_PX, height: height - 2 * PAD_PX };
  const pixels = Math.max(Math.min(room.width / (x[1] - x[0] || 1), room.height / (y[1] - y[0] || 1)), 0);
  const [spanX, spanY] = [(x[1] - x[0]) * pixels, (y[1] - y[0]) * pixels];
  const left = (width - spanX) / 2;
  const top = (height - spanY) / 2;
  return {
    x: scaleLinear().domain(x).range([left, left + spanX]),
    y: scaleLinear().domain(y).range(yUp ? [top + spanY, top] : [top, top + spanY]),
  };
}

/** The magma colours of the theme from 0 to the fastest speed, a speed over it taking the last colour. */
function speedScale(speedTop: number) {
  const [from, to] = MAGMA_RANGE[currentTheme()];
  return scaleSequential((t: number) => interpolateMagma(from + (to - from) * t)).domain([0, speedTop]).clamp(true);
}

/** A map of a recording: what lies behind it, stretches of its path, the last seconds as a trail coloured by speed, the current point and its heading. */
export class MapView {
  private readonly canvas = document.createElement("canvas");
  private ctx!: CanvasRenderingContext2D;
  private readonly stopWatching: () => void;
  private width = 0;
  private height = 0;
  private colours: Palette = palette();
  private project: Projection = { x: scaleLinear(), y: scaleLinear() };
  private speedTop = 1;
  private speedColour = speedScale(this.speedTop);

  private track: Track | null = null;
  private backdrop: Backdrop | null = null;
  private stretches: Stretch[] = [];
  private withCursor = true;
  private index = 0;
  /** Whether the last seconds are drawn as a trail coloured by speed, with the legend. The current point is the cursor and is always drawn. */
  trail = true;

  constructor(host: HTMLElement) {
    this.canvas.className = "absolute left-0 top-0";
    host.append(this.canvas);
    this.stopWatching = watchSize(host, (width, height) => this.resize(width, height));
  }

  /** The recording behind its backdrop, with the trail, the point and the speed colours unless the page shows no cursor. */
  load(track: Track, backdrop: Backdrop, speedTop: number, withCursor = true): void {
    this.track = track;
    this.backdrop = backdrop;
    this.withCursor = withCursor;
    this.speedTop = speedTop;
    this.speedColour = speedScale(speedTop);
    this.index = 0;
    this.fitScales();
    this.draw(0);
  }

  /** No recording: the canvas is left blank until the next load. */
  clear(): void {
    this.track = null;
    this.backdrop = null;
    this.stretches = [];
    if (this.width) this.ctx.clearRect(0, 0, this.width, this.height);
  }

  /** The stretches of the path drawn as lines. */
  setStretches(stretches: Stretch[]): void {
    this.stretches = stretches;
    this.redraw();
  }

  redraw(): void {
    this.draw(this.index);
  }

  refresh(): void {
    this.colours = palette();
    this.speedColour = speedScale(this.speedTop);
    this.backdrop?.refresh?.();
    this.redraw();
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
    this.redraw();
  }

  private fitScales(): void {
    if (this.backdrop) this.project = fitScales(this.backdrop.extent, this.width, this.height, this.backdrop.yUp);
  }

  /** Draw the recording at a frame index. */
  draw(index: number): void {
    this.index = index;
    if (!this.track || !this.backdrop || this.width === 0) return;
    const { ctx } = this;
    ctx.clearRect(0, 0, this.width, this.height);
    this.backdrop.draw(ctx, this.project, this.colours, index);
    this.drawStretches(ctx);
    if (!this.withCursor) return;
    if (this.trail) this.drawTrail(ctx);
    this.drawPoint(ctx);
    if (this.trail) this.drawLegend(ctx);
  }

  /** Each stretch at PATH_HZ, its last frame always included so stretches that meet leave no gap. */
  private drawStretches(ctx: CanvasRenderingContext2D): void {
    const track = this.track!;
    const step = Math.max(1, Math.round(track.rateHz / PATH_HZ));
    for (const stretch of this.stretches) {
      const colour = colourOf(this.colours, stretch.colour);
      ctx.strokeStyle = withAlpha(stretch.light ? lighter(colour) : colour, stretch.alpha);
      ctx.lineWidth = stretch.width;
      ctx.beginPath();
      let drawing = false;
      for (let i = stretch.first - 1; ; i = Math.min(i + step, stretch.last - 1)) {
        const [x, y] = drawnAt(track, i);
        if (Number.isNaN(x) || Number.isNaN(y)) drawing = false;
        else if (drawing) ctx.lineTo(this.project.x(x), this.project.y(y));
        else {
          ctx.moveTo(this.project.x(x), this.project.y(y));
          drawing = true;
        }
        if (i >= stretch.last - 1) break;
      }
      ctx.stroke();
    }
  }

  /** The last TRAIL_S seconds at TRAIL_HZ along the drawn position, each segment in the colour of the speed where it ends. */
  private drawTrail(ctx: CanvasRenderingContext2D): void {
    const track = this.track!;
    const { speed, rateHz } = track;
    const step = Math.max(1, Math.round(rateHz / TRAIL_HZ));
    const first = Math.max(0, this.index - TRAIL_S * rateHz);
    ctx.lineWidth = TRAIL_WIDTH_PX;
    ctx.lineCap = "round";
    for (let i = this.index; i - step >= first; i -= step) {
      const from = i - step;
      const [[x0, y0], [x1, y1]] = [drawnAt(track, from), drawnAt(track, i)];
      if (Number.isNaN(x0) || Number.isNaN(y0) || Number.isNaN(x1) || Number.isNaN(y1)) continue;
      ctx.strokeStyle = this.speedColour(Number.isNaN(speed[i]) ? 0 : speed[i]);
      ctx.beginPath();
      ctx.moveTo(this.project.x(x0), this.project.y(y0));
      ctx.lineTo(this.project.x(x1), this.project.y(y1));
      ctx.stroke();
    }
  }

  /** The current point, at the measured position, with an arrow along the heading, as long as ARROW_FRACTION of the map's width. */
  private drawPoint(ctx: CanvasRenderingContext2D): void {
    const { x, y, heading } = this.track!;
    const i = this.index;
    if (Number.isNaN(x[i])) return;
    const [px, py] = [this.project.x(x[i]), this.project.y(y[i])];
    if (!Number.isNaN(heading[i])) {
      const angle = this.backdrop!.yUp ? -heading[i] : heading[i];
      const length = ARROW_FRACTION * (this.project.x.range()[1] - this.project.x.range()[0]);
      const [tx, ty] = [px + length * Math.cos(angle), py + length * Math.sin(angle)];
      ctx.strokeStyle = ctx.fillStyle = this.colours.bad;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(tx, ty);
      ctx.stroke();
      const back = angle + Math.PI;
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      for (const side of [-0.45, 0.45]) ctx.lineTo(tx + ARROW_HEAD_PX * Math.cos(back + side), ty + ARROW_HEAD_PX * Math.sin(back + side));
      ctx.fill();
    }
    ctx.fillStyle = this.colours.bad;
    ctx.strokeStyle = this.colours.ink;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(px, py, POINT_RADIUS_PX, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
  }

  /** The speed colours as a small bar in the corner with the fastest speed written beside it. */
  private drawLegend(ctx: CanvasRenderingContext2D): void {
    const [low, high] = this.speedColour.domain();
    const top = this.height - PAD_PX / 2 - LEGEND.height;
    const cell = LEGEND.width / LEGEND.steps;
    for (let i = 0; i < LEGEND.steps; i++) {
      ctx.fillStyle = this.speedColour(low + ((high - low) * i) / (LEGEND.steps - 1));
      ctx.fillRect(PAD_PX / 2 + i * cell, top, cell + 0.5, LEGEND.height);
    }
    ctx.font = FONT;
    ctx.fillStyle = this.colours.muted;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(this.backdrop!.speedText(high), PAD_PX / 2 + LEGEND.width + 6, top + LEGEND.height / 2);
  }
}
