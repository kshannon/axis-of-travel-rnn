import { select, zoom, zoomIdentity } from "d3";
import type { ZoomBehavior, ZoomTransform } from "d3";
import { colourOf, palette } from "../ui/palette";
import type { Palette } from "../ui/palette";
import { lighter, sizeCanvas, watchSize, withAlpha } from "./canvas";
import {
  BAR_INSET_PX, barBox, barSpan, baseScale, FRAMES_LANE, hitBar, indexAt, inPlot, keepVisible, laneBands, PLOT, timeLabel, timeTicks, windowTransform, zoomLimits,
} from "./lanes";
import type { Bands, Bar, FrameLayer, Scale, Scene } from "./lanes";

const FONT = "12px ui-sans-serif, system-ui, sans-serif";
const LANE_TINT = 0.05;
const GRID_ALPHA = 0.08;
const LABEL_GAP_PX = 8;
const TICK_SPACING_PX = 90;
const LABEL_PAD_PX = 6;
const HATCH_PX = 5;
const MIN_HATCH_PX = 4;
const HATCH_COLOUR = "rgba(255, 255, 255, 0.6)";
const LINE_PX = 2;
const SPEED_ALPHA = 0.7;

const CURSOR_COLOUR = "#8b5cf6";
const CURSOR_HEAD_PX = 5;
const MARK_COLOUR = "#ef4444";
const MARK_DASH = [4, 3];
const MARK_FILL_ALPHA = 0.12;
const TOOLTIP_PAD_PX = 6;
const TOOLTIP_OFFSET_PX = 12;

const ZOOM_STEP = 2;
const FIT_MARGIN = 0.05;
const CLICK_PX = 4;

export interface TimelineHandlers {
  /** A click on the lanes, with the frame index under it. */
  seek?(index: number): void;
  /** The seconds the lanes show, from and to, after each zoom or pan. */
  view(from: number, to: number): void;
  /** A click on a bar that can be picked, with the number the bar carries. */
  select?(pick: number): void;
}

/** A stretch of lab frames outlined in its lane, the block or window the page has selected. */
export interface LaneSelection {
  lane: string;
  first: number;
  last: number;
}

interface Point {
  x: number;
  y: number;
}

/**
 * The lanes of a scene on canvas over one time axis. Two canvases are stacked, the still one holds the lanes and is
 * redrawn when the view or the data changes, the live one holds the cursor, the marks, the selection and the hover and
 * is redrawn on every frame of playback. The zoom is D3's, on the live canvas.
 */
export class Timeline {
  private readonly still = document.createElement("canvas");
  private readonly live = document.createElement("canvas");
  private stillCtx!: CanvasRenderingContext2D;
  private liveCtx!: CanvasRenderingContext2D;
  private readonly behaviour: ZoomBehavior<HTMLCanvasElement, unknown> = zoom<HTMLCanvasElement, unknown>().on("zoom", (event) => {
    this.transform = event.transform;
    this.paint();
    if (this.scene) this.handlers.view(...(this.scale.domain() as [number, number]));
  });
  private readonly stopWatching: () => void;

  private width = 0;
  private height = 0;
  private bands: Bands = {};
  private base: Scale = baseScale(1, 0);
  private transform: ZoomTransform = zoomIdentity;
  private colours: Palette = palette();

  private scene: Scene | null = null;
  private cursor = 0;
  private selected: LaneSelection | null = null;
  private markIn: number | null = null;
  private markOut: number | null = null;
  private hover: { bar: Bar | null; at: Point } | null = null;

  constructor(host: HTMLElement, private readonly handlers: TimelineHandlers) {
    for (const canvas of [this.still, this.live]) {
      canvas.className = "absolute left-0 top-0";
      host.append(canvas);
    }
    this.live.style.cursor = "pointer";
    this.behaviour.clickDistance(CLICK_PX);
    select(this.live).call(this.behaviour).on("dblclick.zoom", null);
    this.live.addEventListener("click", this.onClick);
    this.live.addEventListener("pointermove", this.onMove);
    this.live.addEventListener("pointerleave", this.onLeave);
    this.stopWatching = watchSize(host, (width, height) => this.resize(width, height));
    this.resize(host.clientWidth, host.clientHeight); // so a page can zoom the lanes before the first resize event
  }

  private get nFrames(): number {
    return this.scene?.nFrames ?? 0;
  }

  private get rate(): number {
    return this.scene?.rateHz ?? 1;
  }

  private get duration(): number {
    return this.nFrames ? this.nFrames / this.rate : 1;
  }

  private get scale(): Scale {
    return this.transform.rescaleX(this.base);
  }

  private get ready(): boolean {
    return this.scene !== null && this.width > 0;
  }

  /** A new recording to draw, whole in view. */
  load(scene: Scene): void {
    this.scene = scene;
    this.bands = laneBands(this.height, scene.lanes);
    this.configure();
    this.apply(zoomIdentity);
  }

  /** The same recording with other bars or layers, the view stays. */
  setScene(scene: Scene): void {
    this.scene = scene;
    this.paint();
  }

  /** Move the cursor to a frame index, paging the window to it when it fell outside. */
  setCursor(index: number): void {
    this.cursor = index;
    const kept = keepVisible(this.transform, this.base, index / this.rate);
    if (kept === this.transform) this.paintLive();
    else this.apply(kept);
  }

  setSelection(selected: LaneSelection | null): void {
    this.selected = selected;
    this.paintLive();
  }

  setMarks(markIn: number | null, markOut: number | null): void {
    this.markIn = markIn;
    this.markOut = markOut;
    this.paintLive();
  }

  zoomAll(): void {
    this.apply(zoomIdentity);
  }

  zoomIn(): void {
    this.zoomBy(ZOOM_STEP);
  }

  zoomOut(): void {
    this.zoomBy(1 / ZOOM_STEP);
  }

  /** Zoom to the selection with a margin. */
  fitSelected(): void {
    if (!this.selected) return;
    const start = (this.selected.first - 1) / this.rate;
    const end = this.selected.last / this.rate;
    this.apply(windowTransform(this.base, start - FIT_MARGIN * (end - start), end + FIT_MARGIN * (end - start)));
  }

  /** Read the theme again and redraw, after a theme toggle. */
  refresh(): void {
    this.colours = palette();
    this.paint();
  }

  destroy(): void {
    this.stopWatching();
    select(this.live).on(".zoom", null);
    this.still.remove();
    this.live.remove();
  }

  /** Zoom in or out about the cursor when it is in view, else about the middle. */
  private zoomBy(factor: number): void {
    const x = this.scale(this.cursor / this.rate);
    const about: [number, number] | undefined = x >= PLOT.left && x <= this.width - PLOT.right ? [x, 0] : undefined;
    this.behaviour.scaleBy(select(this.live), factor, about);
  }

  private resize(width: number, height: number): void {
    const visible = this.scene && this.scale.domain();
    this.width = width;
    this.height = height;
    this.stillCtx = sizeCanvas(this.still, width, height);
    this.liveCtx = sizeCanvas(this.live, width, height);
    this.bands = laneBands(height, this.scene?.lanes ?? []);
    this.configure();
    this.apply(visible ? windowTransform(this.base, visible[0], visible[1]) : zoomIdentity);
  }

  private configure(): void {
    this.base = baseScale(this.duration, this.width);
    const extent: [[number, number], [number, number]] = [[PLOT.left, 0], [this.width - PLOT.right, this.height]];
    this.behaviour.extent(extent).translateExtent(extent).scaleExtent(zoomLimits(this.duration));
  }

  private apply(transform: ZoomTransform): void {
    select(this.live).call(this.behaviour.transform, transform);
  }

  private paint(): void {
    this.paintStill();
    this.paintLive();
  }

  private pointer(event: MouseEvent): Point {
    const box = this.live.getBoundingClientRect();
    return { x: event.clientX - box.left, y: event.clientY - box.top };
  }

  private barAt(point: Point): Bar | null {
    return hitBar(this.scene!.bars, this.bands, this.scale, this.rate, point);
  }

  private onClick = (event: MouseEvent): void => {
    const point = this.pointer(event);
    if (!this.ready || !inPlot(point, this.width, this.height)) return;
    const bar = this.barAt(point);
    if (bar?.pick !== undefined && this.handlers.select) this.handlers.select(bar.pick);
    else this.handlers.seek?.(indexAt(this.scale, point.x, this.rate, this.nFrames));
  };

  private onMove = (event: MouseEvent): void => {
    const at = this.pointer(event);
    this.hover = { bar: this.ready && inPlot(at, this.width, this.height) ? this.barAt(at) : null, at };
    this.paintLive();
  };

  private onLeave = (): void => {
    this.hover = null;
    this.paintLive();
  };

  private paintStill(): void {
    if (!this.ready) return;
    const ctx = this.stillCtx;
    const scale = this.scale;
    ctx.clearRect(0, 0, this.width, this.height);
    ctx.font = FONT;
    this.drawLanes(ctx, scale);
    ctx.save();
    ctx.beginPath();
    ctx.rect(PLOT.left, 0, this.width - PLOT.left - PLOT.right, this.height);
    ctx.clip();
    for (const bar of this.scene!.bars) this.drawBar(ctx, scale, bar);
    this.drawFrames(ctx, scale);
    ctx.restore();
  }

  /** The lane backgrounds with their names, the time grid and the axis labels. */
  private drawLanes(ctx: CanvasRenderingContext2D, scale: Scale): void {
    const c = this.colours;
    ctx.textBaseline = "middle";
    ctx.textAlign = "right";
    for (const { name } of this.scene!.lanes) {
      const { top, bottom } = this.bands[name];
      ctx.fillStyle = withAlpha(c.ink, LANE_TINT);
      ctx.fillRect(PLOT.left, top, this.width - PLOT.left - PLOT.right, bottom - top);
      ctx.fillStyle = c.muted;
      ctx.fillText(name, PLOT.left - LABEL_GAP_PX, (top + bottom) / 2);
    }
    const ticks = timeTicks(scale.domain() as [number, number], (this.width - PLOT.left - PLOT.right) / TICK_SPACING_PX);
    ctx.textAlign = "center";
    for (const t of ticks) {
      const x = scale(t);
      this.line(ctx, x, PLOT.top, x, this.height - PLOT.bottom, withAlpha(c.ink, GRID_ALPHA));
      ctx.fillStyle = c.muted;
      ctx.fillText(timeLabel(t), x, this.height - PLOT.bottom / 2);
    }
  }

  private line(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, colour: string, width = 1): void {
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
  }

  /** A bar in its box with its name written inside when it fits, hatched and outlined when it asks. */
  private drawBar(ctx: CanvasRenderingContext2D, scale: Scale, bar: Bar): void {
    const [x, y, w, h] = barBox(scale, this.bands, bar, this.rate);
    const fill = colourOf(this.colours, bar.fill);
    ctx.fillStyle = withAlpha(bar.light ? lighter(fill) : fill, bar.alpha ?? 1);
    ctx.fillRect(x, y, w, h);
    if (bar.text && ctx.measureText(bar.text).width + LABEL_PAD_PX <= w) {
      ctx.fillStyle = this.colours.ink;
      ctx.textAlign = "center";
      ctx.fillText(bar.text, x + w / 2, y + h / 2);
    }
    if (bar.hatched && w >= MIN_HATCH_PX) this.hatch(ctx, x, y, w, h);
    if (bar.outline) {
      ctx.strokeStyle = colourOf(this.colours, bar.outline);
      ctx.lineWidth = LINE_PX;
      ctx.strokeRect(x, y, w, h);
    }
  }

  private hatch(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number): void {
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    ctx.strokeStyle = HATCH_COLOUR;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let d = -h; d < w; d += HATCH_PX) {
      ctx.moveTo(x + d, y + h);
      ctx.lineTo(x + d + h, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  /** The frames lane, each layer of the scene in its order. */
  private drawFrames(ctx: CanvasRenderingContext2D, scale: Scale): void {
    const { top, bottom } = this.bands[FRAMES_LANE];
    const height = bottom - top;
    const draw = (layer: FrameLayer) => {
      if (layer.kind === "trace") return this.drawSpeed(ctx, scale, layer);
      if (layer.kind === "span") {
        ctx.fillStyle = withAlpha(layer.colour, layer.alpha);
        for (const [first, last] of layer.spans) {
          const [x0, x1] = barSpan(scale, { first, last }, this.rate);
          ctx.fillRect(x0, top + layer.from * height, x1 - x0, (layer.to - layer.from) * height);
        }
        return;
      }
      for (const frame of layer.frames) {
        const x = scale((frame - 1) / this.rate);
        this.line(ctx, x, top, x, top + layer.to * height, layer.colour, LINE_PX);
      }
    };
    this.scene!.frames.forEach(draw);
  }

  /** The speed as a thin trace, the mean of the frames under each pixel so a long recording still draws in a few thousand points. */
  private drawSpeed(ctx: CanvasRenderingContext2D, scale: Scale, { values, top: speedTop }: Extract<FrameLayer, { kind: "trace" }>): void {
    const { top, bottom } = this.bands[FRAMES_LANE];
    const [from, to] = scale.domain();
    const first = Math.max(0, Math.floor(from * this.rate));
    const last = Math.min(this.nFrames - 1, Math.ceil(to * this.rate));
    const step = Math.max(1, Math.ceil((last - first + 1) / (this.width - PLOT.left - PLOT.right)));
    ctx.strokeStyle = withAlpha(this.colours.ink, SPEED_ALPHA);
    ctx.lineWidth = 1;
    ctx.beginPath();
    let drawing = false;
    for (let i = first; i <= last; i += step) {
      let sum = 0;
      let n = 0;
      for (let k = i; k < Math.min(i + step, last + 1); k++) {
        if (!Number.isNaN(values[k])) {
          sum += values[k];
          n++;
        }
      }
      if (!n) {
        drawing = false;
        continue;
      }
      const x = scale((i + step / 2) / this.rate);
      const y = bottom - Math.min(sum / n / speedTop, 1) * (bottom - top);
      if (drawing) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
      drawing = true;
    }
    ctx.stroke();
  }

  private paintLive(): void {
    if (!this.ready) return;
    const ctx = this.liveCtx;
    const scale = this.scale;
    const c = this.colours;
    const bottom = this.height - PLOT.bottom;
    ctx.clearRect(0, 0, this.width, this.height);
    ctx.save();
    ctx.beginPath();
    ctx.rect(PLOT.left, 0, this.width - PLOT.left - PLOT.right, this.height);
    ctx.clip();

    const x = (frame: number) => scale((frame - 1) / this.rate);
    if (this.markIn !== null && this.markOut !== null) {
      const [first, last] = [this.markIn, this.markOut].sort((a, b) => a - b);
      ctx.fillStyle = withAlpha(MARK_COLOUR, MARK_FILL_ALPHA);
      ctx.fillRect(x(first), PLOT.top, scale(last / this.rate) - x(first), bottom - PLOT.top);
    }
    ctx.setLineDash(MARK_DASH);
    for (const mark of [this.markIn, this.markOut]) if (mark !== null) this.line(ctx, x(mark), PLOT.top, x(mark), bottom, MARK_COLOUR, LINE_PX);
    ctx.setLineDash([]);

    if (this.selected) {
      const [x0, x1] = barSpan(scale, this.selected, this.rate);
      const { top, bottom: laneBottom } = this.bands[this.selected.lane];
      ctx.strokeStyle = c.ink;
      ctx.lineWidth = LINE_PX;
      ctx.strokeRect(x0, top + BAR_INSET_PX, x1 - x0, laneBottom - top - 2 * BAR_INSET_PX);
      for (const edge of [x0, x1]) this.line(ctx, edge, top, edge, this.bands[FRAMES_LANE].top, c.ink);
    }

    const cursor = scale(this.cursor / this.rate);
    this.line(ctx, cursor, PLOT.top, cursor, bottom, CURSOR_COLOUR, LINE_PX);
    ctx.fillStyle = CURSOR_COLOUR;
    ctx.beginPath();
    ctx.moveTo(cursor - CURSOR_HEAD_PX, 0);
    ctx.lineTo(cursor + CURSOR_HEAD_PX, 0);
    ctx.lineTo(cursor, PLOT.top + CURSOR_HEAD_PX);
    ctx.fill();
    ctx.restore();

    if (this.hover?.bar) this.drawTooltip(ctx, this.hover.bar.tip, this.hover.at);
  }

  private drawTooltip(ctx: CanvasRenderingContext2D, text: string, at: Point): void {
    ctx.font = FONT;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    const width = ctx.measureText(text).width + 2 * TOOLTIP_PAD_PX;
    const height = 18 + TOOLTIP_PAD_PX;
    const left = Math.min(at.x + TOOLTIP_OFFSET_PX, this.width - width - 2);
    const top = Math.max(at.y - height - TOOLTIP_OFFSET_PX, 2);
    ctx.fillStyle = this.colours.card;
    ctx.strokeStyle = this.colours.line;
    ctx.lineWidth = 1;
    ctx.fillRect(left, top, width, height);
    ctx.strokeRect(left, top, width, height);
    ctx.fillStyle = this.colours.ink;
    ctx.fillText(text, left + TOOLTIP_PAD_PX, top + height / 2);
  }
}
