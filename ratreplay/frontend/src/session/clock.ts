export const SPEEDS = [0.25, 0.5, 1, 2, 4, 8] as const;
export const REAL_TIME = SPEEDS.indexOf(1);

/** The index of the speed one step slower (-1) or faster (1), held at the slowest and the fastest. */
export function stepSpeed(index: number, direction: -1 | 1): number {
  return Math.min(Math.max(index + direction, 0), SPEEDS.length - 1);
}

const MS_PER_S = 1000;

/** The playback position of a session. The frame index is the single truth, advanced from the wall clock so 1x is real time. */
export class Clock {
  index = 0;
  playing = false;
  speed = 1;
  private anchorMs = 0;
  private anchorIndex = 0;

  constructor(readonly nFrames: number, readonly rateHz: number) {}

  private anchor(nowMs: number): void {
    this.anchorMs = nowMs;
    this.anchorIndex = this.index;
  }

  /** Jump to a frame index, clamped to the session, playing on from there if it was playing. */
  seek(index: number, nowMs: number): void {
    this.index = Math.min(Math.max(Math.round(index), 0), this.nFrames - 1);
    this.anchor(nowMs);
  }

  /** Play or pause, playing from the start when the session had run out. */
  toggle(nowMs: number): void {
    if (!this.playing && this.index >= this.nFrames - 1) this.index = 0;
    this.playing = !this.playing;
    this.anchor(nowMs);
  }

  pause(): void {
    this.playing = false;
  }

  /** Move by whole frames, which pauses. */
  step(frames: number, nowMs: number): void {
    this.playing = false;
    this.seek(this.index + frames, nowMs);
  }

  setSpeed(speed: number, nowMs: number): void {
    this.anchor(nowMs);
    this.speed = speed;
  }

  /** Move the index to where the wall clock says it is, and say whether it moved. */
  advance(nowMs: number): boolean {
    if (!this.playing) return false;
    const before = this.index;
    const elapsed = Math.floor(((nowMs - this.anchorMs) / MS_PER_S) * this.speed * this.rateHz);
    this.index = Math.min(this.anchorIndex + elapsed, this.nFrames - 1);
    if (this.index === this.nFrames - 1) this.playing = false;
    return this.index !== before;
  }
}
