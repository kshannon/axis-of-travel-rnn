import { select, zoom, zoomIdentity } from "d3";
import type { ZoomBehavior, ZoomTransform } from "d3";
import type { ReviewBlock, SessionHeader, Span } from "../api/types";
import { palette } from "../ui/palette";
import type { Palette } from "../ui/palette";
import { sizeCanvas, watchSize, withAlpha } from "./canvas";
import { colourOf } from "./layers";
import type { LayerKey, Layers } from "./layers";
import {
  barSpan, barsOf, baseScale, describeBar, hitBar, indexAt, inPlot, keepVisible, laneBands, LANES, PLOT, runKind, timeLabel, timeTicks,
  windowTransform, zoomLimits,
} from "./lanes";
import type { Bands, Bar, Scale } from "./lanes";

const FONT = "12px ui-sans-serif, system-ui, sans-serif";
const LANE_TINT = 0.05;
const GRID_ALPHA = 0.08;
const BAR_ALPHA = 0.8;
const LABEL_GAP_PX = 8;
const TICK_SPACING_PX = 90;
const LABEL_PAD_PX = 6;
const BAR_INSET_PX = 1;
const HATCH_PX = 5;
const MIN_HATCH_PX = 4;

const EPOCH_COLOURS: Record<string, string> = { arena: "#38bdf8", track: "#4ade80" };
const OTHER_EPOCH_COLOUR = "#a1a1aa";
const RUN_COLOURS = { outbound: "#3b82f6", return: "#93c5fd", other: "#9ca3af" };
const HATCH_COLOUR = "rgba(255, 255, 255, 0.6)";

// Fractions of the frames lane: the band of the heading layers at the bottom, the pause ticks at the top. The speed
// trace is drawn up to the speed scale, and a margin is a dark band over the cut it trims.
const HEADING_BAND = 0.14;
const PAUSE_TICK = 0.3;
const GAP_ALPHA = 0.35;
const MARGIN_ALPHA = 0.85;
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
  seek(index: number): void;
  select(block: ReviewBlock): void;
  /** The seconds the lanes show, from and to, after each zoom or pan. */
  view(from: number, to: number): void;
}

interface Point {
  x: number;
  y: number;
}

/**
 * The four lanes of a session on canvas: session, runs, frames and blocks over one time axis. Two canvases are stacked,
 * the still one holds the lanes and is redrawn when the view or the data changes, the live one holds the cursor, the
 * marks, the selection and the hover and is redrawn on every frame of playback. The zoom is D3's, on the live canvas.
 */
export class Timeline {
  private readonly still = document.createElement("canvas");
  private readonly live = document.createElement("canvas");
  private stillCtx!: CanvasRenderingContext2D;
  private liveCtx!: CanvasRenderingContext2D;
  private readonly behaviour: ZoomBehavior<HTMLCanvasElement, unknown> = zoom<HTMLCanvasElement, unknown>().on("zoom", (event) => {
    this.transform = event.transform;
    this.paint();
    if (this.header) this.handlers.view(...(this.scale.domain() as [number, number]));
  });
  private readonly stopWatching: () => void;

  private width = 0;
  private height = 0;
  private bands: Bands = laneBands(0);
  private base: Scale = baseScale(1, 0);
  private transform: ZoomTransform = zoomIdentity;
  private colours: Palette = palette();

  private header: SessionHeader | null = null;
  private speed: Float64Array = new Float64Array(0);
  private speedTop = 1;
  private bars: Bar[] = [];
  private flagged = new Set<number>();
  private layers: Layers;
  private cursor = 0;
  private selected: ReviewBlock | null = null;
  private markIn: number | null = null;
  private markOut: number | null = null;
  private hover: { bar: Bar | null; at: Point } | null = null;

  constructor(host: HTMLElement, private readonly handlers: TimelineHandlers, layers: Layers) {
    this.layers = layers;
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
  }

  private get nFrames(): number {
    return this.header?.n_frames ?? 0;
  }

  private get rate(): number {
    return this.header?.rate_hz ?? 1;
  }

  private get duration(): number {
    return this.nFrames ? this.nFrames / this.rate : 1;
  }

  private get scale(): Scale {
    return this.transform.rescaleX(this.base);
  }

  private get ready(): boolean {
    return this.header !== null && this.width > 0;
  }

  /** The session to draw, whole in view. */
  load(header: SessionHeader, speed: Float64Array, speedTop: number): void {
    this.header = header;
    this.speed = speed;
    this.speedTop = speedTop;
    this.configure();
    this.apply(zoomIdentity);
  }

  setBlocks(blocks: ReviewBlock[], flaggedRuns: number[]): void {
    this.bars = barsOf(this.header!.epochs, this.header!.runs, blocks);
    this.flagged = new Set(flaggedRuns);
    this.paint();
  }

  setLayers(layers: Layers): void {
    this.layers = layers;
    this.paintStill();
  }

  /** Move the cursor to a frame index, paging the window to it when it fell outside. */
  setCursor(index: number): void {
    this.cursor = index;
    const kept = keepVisible(this.transform, this.base, index / this.rate);
    if (kept === this.transform) this.paintLive();
    else this.apply(kept);
  }

  setSelection(block: ReviewBlock | null): void {
    this.selected = block;
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

  /** Zoom to the selected block with a margin. */
  fitSelected(): void {
    if (!this.selected) return;
    const start = (this.selected.frame_start - 1) / this.rate;
    const end = this.selected.frame_end / this.rate;
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
    const visible = this.header && this.scale.domain();
    this.width = width;
    this.height = height;
    this.stillCtx = sizeCanvas(this.still, width, height);
    this.liveCtx = sizeCanvas(this.live, width, height);
    this.bands = laneBands(height);
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
    return hitBar(this.bars, this.bands, this.scale, this.rate, point);
  }

  private onClick = (event: MouseEvent): void => {
    const point = this.pointer(event);
    if (!this.ready || !inPlot(point, this.width, this.height)) return;
    const bar = this.barAt(point);
    if (bar?.lane === "blocks") this.handlers.select(bar.block);
    else this.handlers.seek(indexAt(this.scale, point.x, this.rate, this.nFrames));
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
    for (const bar of this.bars) {
      if (bar.lane === "session") this.drawEpoch(ctx, scale, bar);
      else if (bar.lane === "runs") this.drawRun(ctx, scale, bar);
      else this.drawBlock(ctx, scale, bar);
    }
    this.drawFrames(ctx, scale);
    ctx.restore();
  }

  /** The lane backgrounds with their names, the time grid and the axis labels. */
  private drawLanes(ctx: CanvasRenderingContext2D, scale: Scale): void {
    const c = this.colours;
    ctx.textBaseline = "middle";
    ctx.textAlign = "right";
    for (const lane of LANES) {
      const { top, bottom } = this.bands[lane];
      ctx.fillStyle = withAlpha(c.ink, LANE_TINT);
      ctx.fillRect(PLOT.left, top, this.width - PLOT.left - PLOT.right, bottom - top);
      ctx.fillStyle = c.muted;
      ctx.fillText(lane, PLOT.left - LABEL_GAP_PX, (top + bottom) / 2);
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

  /** A bar's pixel box in its lane, and its name written inside when it fits. */
  private drawBar(ctx: CanvasRenderingContext2D, scale: Scale, bar: Bar, fill: string, text = ""): [number, number, number, number] {
    const [x0, x1] = barSpan(scale, bar, this.rate);
    const { top, bottom } = this.bands[bar.lane];
    const box: [number, number, number, number] = [x0, top + BAR_INSET_PX, x1 - x0, bottom - top - 2 * BAR_INSET_PX];
    ctx.fillStyle = fill;
    ctx.fillRect(...box);
    if (text && ctx.measureText(text).width + LABEL_PAD_PX <= x1 - x0) {
      ctx.fillStyle = this.colours.ink;
      ctx.textAlign = "center";
      ctx.fillText(text, (x0 + x1) / 2, (top + bottom) / 2);
    }
    return box;
  }

  private drawEpoch(ctx: CanvasRenderingContext2D, scale: Scale, bar: Extract<Bar, { lane: "session" }>): void {
    this.drawBar(ctx, scale, bar, withAlpha(EPOCH_COLOURS[bar.epoch.epoch] ?? OTHER_EPOCH_COLOUR, BAR_ALPHA), bar.epoch.epoch);
  }

  private drawRun(ctx: CanvasRenderingContext2D, scale: Scale, bar: Extract<Bar, { lane: "runs" }>): void {
    const [x, y, w, h] = this.drawBar(ctx, scale, bar, RUN_COLOURS[runKind(bar.run.path_id)]);
    if (!bar.run.clean && w >= MIN_HATCH_PX) this.hatch(ctx, x, y, w, h);
    if (this.flagged.has(bar.run.run)) {
      ctx.strokeStyle = this.colours.bad;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);
    }
  }

  private drawBlock(ctx: CanvasRenderingContext2D, scale: Scale, bar: Extract<Bar, { lane: "blocks" }>): void {
    const c = this.colours;
    const colour = { auto: c.accent, confirmed: c.ok, edited: c.warn, dropped: c.muted }[bar.block.status];
    this.drawBar(ctx, scale, bar, withAlpha(colour, bar.block.status === "dropped" ? GAP_ALPHA : BAR_ALPHA), bar.name);
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

  /** The frames lane: the gaps and margins behind, the heading bands, the speed trace, then the jumps and pauses in front. */
  private drawFrames(ctx: CanvasRenderingContext2D, scale: Scale): void {
    const h = this.header!;
    const { top, bottom } = this.bands.frames;
    const heading = (bottom - top) * HEADING_BAND;
    const band = (spans: Span[], key: LayerKey, from: number, to: number, alpha = 1) => {
      if (!this.layers[key]) return;
      ctx.fillStyle = withAlpha(colourOf(key), alpha);
      for (const [first, last] of spans) {
        const [x0, x1] = barSpan(scale, { first, last }, this.rate);
        ctx.fillRect(x0, from, x1 - x0, to - from);
      }
    };
    band(h.cuts.gaps, "gaps", top, bottom, GAP_ALPHA);
    band(h.cuts.margins, "margins", top, bottom, MARGIN_ALPHA);
    band(h.heading_filled, "filled", bottom - heading, bottom);
    band(h.heading_held, "held", bottom - heading, bottom);
    band(h.heading_lost, "lost", bottom - heading, bottom);
    if (this.layers.speed) this.drawSpeed(ctx, scale);
    const mark = (frames: number[], key: LayerKey, from: number, to: number) => {
      if (!this.layers[key]) return;
      for (const frame of frames) {
        const x = scale((frame - 1) / this.rate);
        this.line(ctx, x, from, x, to, colourOf(key), 2);
      }
    };
    mark(h.cuts.jumps, "jumps", top, bottom);
    mark(h.cuts.pauses, "pauses", top, top + (bottom - top) * PAUSE_TICK);
  }

  /** The speed as a thin trace, the mean of the frames under each pixel so a long session still draws in a few thousand points. */
  private drawSpeed(ctx: CanvasRenderingContext2D, scale: Scale): void {
    const { top, bottom } = this.bands.frames;
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
        if (!Number.isNaN(this.speed[k])) {
          sum += this.speed[k];
          n++;
        }
      }
      if (!n) {
        drawing = false;
        continue;
      }
      const x = scale((i + step / 2) / this.rate);
      const y = bottom - Math.min(sum / n / this.speedTop, 1) * (bottom - top);
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
    for (const mark of [this.markIn, this.markOut]) if (mark !== null) this.line(ctx, x(mark), PLOT.top, x(mark), bottom, MARK_COLOUR, 2);
    ctx.setLineDash([]);

    if (this.selected) {
      const [x0, x1] = barSpan(scale, { first: this.selected.frame_start, last: this.selected.frame_end }, this.rate);
      const { top } = this.bands.blocks;
      ctx.strokeStyle = c.ink;
      ctx.lineWidth = 2;
      ctx.strokeRect(x0, top + BAR_INSET_PX, x1 - x0, this.bands.blocks.bottom - top - 2 * BAR_INSET_PX);
      for (const edge of [x0, x1]) this.line(ctx, edge, top, edge, this.bands.frames.top, c.ink);
    }

    const cursor = scale(this.cursor / this.rate);
    this.line(ctx, cursor, PLOT.top, cursor, bottom, CURSOR_COLOUR, 2);
    ctx.fillStyle = CURSOR_COLOUR;
    ctx.beginPath();
    ctx.moveTo(cursor - CURSOR_HEAD_PX, 0);
    ctx.lineTo(cursor + CURSOR_HEAD_PX, 0);
    ctx.lineTo(cursor, PLOT.top + CURSOR_HEAD_PX);
    ctx.fill();
    ctx.restore();

    if (this.hover?.bar) this.drawTooltip(ctx, this.hover.bar, this.hover.at);
  }

  private drawTooltip(ctx: CanvasRenderingContext2D, bar: Bar, at: Point): void {
    const flagged = bar.lane === "runs" && this.flagged.has(bar.run.run);
    const text = describeBar(bar, this.rate, flagged);
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
