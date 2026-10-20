import { belongsToTarget, commandOf } from "../ui/keys";
import type { Command } from "../ui/keys";
import type { Clock } from "./clock";

// Holding these keys moves the cursor on, holding any other would flip an edit again and again.
const REPEATABLE: readonly Command[] = ["back", "forward", "back-second", "forward-second"];

/** What a page hands the playback loop: the clock it plays, how to redraw the cursor and where the runs start. */
export interface PlaybackPage {
  playing: boolean;
  /** The clock being played, none while nothing is loaded. */
  clock(): Clock | null;
  /** Redraw everything that follows the cursor. */
  show(): void;
  /** The lab frames the runs start at. */
  runStarts(): number[];
  /** A key that is not a playback key. */
  command?(command: Command): void;
}

/** Move the clock by a playback command: play or pause, a frame or a second either way, the previous or next run. Gives back whether the command was one of them. */
export function movePlayback(command: Command, clock: Clock, runStarts: readonly number[], nowMs: number): boolean {
  const here = clock.index + 1;
  const starts = [...runStarts].sort((a, b) => a - b);
  const jump = (target: number | undefined) => target !== undefined && clock.step(target - here, nowMs);
  const moves: Partial<Record<Command, () => void>> = {
    play: () => clock.toggle(nowMs),
    back: () => clock.step(-1, nowMs),
    forward: () => clock.step(1, nowMs),
    "back-second": () => clock.step(-clock.rateHz, nowMs),
    "forward-second": () => clock.step(clock.rateHz, nowMs),
    "previous-run": () => jump(starts.filter((start) => start < here).at(-1)),
    "next-run": () => jump(starts.find((start) => start > here)),
  };
  moves[command]?.();
  return command in moves;
}

/** Run the page's playback: advance the clock with the wall clock, follow the playback keys and pause when the tab is hidden. Gives back the function that stops it. */
export function startPlayback(page: PlaybackPage): () => void {
  let frameId = 0;
  const tick = (now: number) => {
    frameId = requestAnimationFrame(tick);
    const clock = page.clock();
    if (!clock) return;
    if (clock.advance(now)) page.show();
    page.playing = clock.playing;
  };
  const onKey = (event: KeyboardEvent) => {
    const clock = page.clock();
    const command = commandOf(event);
    if (!clock || !command || belongsToTarget({ key: event.key, target: event.target as Element | null })) return;
    event.preventDefault();
    if (event.repeat && !REPEATABLE.includes(command)) return;
    if (movePlayback(command, clock, page.runStarts(), performance.now())) {
      page.show();
      page.playing = clock.playing;
    } else page.command?.(command);
  };
  const onHidden = () => {
    if (!document.hidden) return;
    page.clock()?.pause();
    page.playing = false;
  };
  frameId = requestAnimationFrame(tick);
  addEventListener("keydown", onKey);
  document.addEventListener("visibilitychange", onHidden);
  return () => {
    cancelAnimationFrame(frameId);
    removeEventListener("keydown", onKey);
    document.removeEventListener("visibilitychange", onHidden);
    page.clock()?.pause();
  };
}
