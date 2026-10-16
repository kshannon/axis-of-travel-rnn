import Alpine from "alpinejs";
import { errorText, listSessions } from "../api/client";
import type { ReviewBlock } from "../api/types";
import { ALL, CURRENT, MapView } from "../draw/map";
import { allLayers, LAYERS } from "../draw/layers";
import type { LayerKey } from "../draw/layers";
import { timeLabel } from "../draw/lanes";
import { Timeline } from "../draw/timeline";
import { epochAt, runAt } from "../session/at";
import { REAL_TIME, SPEEDS } from "../session/clock";
import { editFor, label, reselected } from "../session/editor";
import type { Action } from "../session/editor";
import { Workspace } from "../session/workspace";
import { sourceStore } from "../state/source";
import { card } from "../ui/card";
import { belongsToTarget, commandOf } from "../ui/keys";
import type { Command } from "../ui/keys";
import { BUTTON_PRIMARY } from "../ui/style";
import { counted } from "../ui/text";
import { toast } from "../ui/toast";
import type { Page } from "./page";
import { replayGrid } from "./replay-html";
import { blockCards, factsLine, liveTiles, marksLine, stateLine, summaryTiles } from "./replay-view";
import type { BlockCard, Tile } from "./replay-view";

// Holding these keys moves the cursor on, holding any other would flip an edit again and again.
const REPEATABLE: readonly Command[] = ["back", "forward", "back-second", "forward-second"];
const NO_SESSION = "No session is open, choose one on the Sessions page.";

// The chips of the timeline keep their state when the person visits another page and comes back.
const layers = allLayers();

function registerReplay(): void {
  Alpine.data("replayPage", () => {
    // The session, its views and the playback loop live in plain objects, only scalars and small lists go to Alpine.
    let ws!: Workspace;
    let timeline!: Timeline;
    let map!: MapView;
    let selected: ReviewBlock | null = null;
    let frameId = 0;
    let alive = true;
    let stopKeys = () => {};
    const targetOf = (first?: number) => {
      const frame = ws.clock.index + 1;
      const block = first === undefined ? selected : (ws.preview.blocks.find((b) => b.frame_start === first) ?? null);
      return { cursor: frame, block, range: ws.editor.range, run: runAt(ws.header.runs, frame) };
    };

    return {
      loading: true,
      busy: false,
      error: "",
      sessionId: "",
      facts: "",
      stateLine: "",
      blocks: [] as BlockCard[],
      summary: [] as Tile[],
      playing: false,
      speeds: SPEEDS,
      speedIndex: REAL_TIME,
      time: "",
      frame: "",
      speed: "",
      lights: "",
      epochNow: "",
      shown: "",
      occupancy: CURRENT,
      occupancyChoices: [CURRENT, ALL] as string[],
      layers,
      layerList: LAYERS,
      marksLine: "",
      runLine: "",
      runNow: null as number | null,
      runFlagged: false,
      notes: "",
      editCount: 0,
      hasSelection: false,
      hasRange: false,
      selectedName: "",

      get speedLabel() {
        return `${SPEEDS[this.speedIndex]}x`;
      },
      get mapTitle() {
        return [this.sessionId, this.epochNow, this.selectedName].filter(Boolean).join(", ");
      },

      async init() {
        await this.$nextTick();
        if (!alive) return;
        const handlers = {
          seek: (index: number) => this.seek(index),
          select: (block: ReviewBlock) => this.selectBlock(block),
          view: (from: number, to: number) => (this.shown = `${timeLabel(from)} to ${timeLabel(to)}`),
        };
        timeline = new Timeline(this.$refs.timeline, handlers, { ...this.layers });
        map = new MapView(this.$refs.map);
        const onKey = (event: KeyboardEvent) => {
          const command = commandOf(event);
          if (!command || this.loading || belongsToTarget({ key: event.key, target: event.target as Element | null })) return;
          event.preventDefault();
          if (!event.repeat || REPEATABLE.includes(command)) this.command(command);
        };
        const onHidden = () => {
          if (document.hidden && !this.loading) this.pause();
        };
        addEventListener("keydown", onKey);
        document.addEventListener("visibilitychange", onHidden);
        stopKeys = () => {
          removeEventListener("keydown", onKey);
          document.removeEventListener("visibilitychange", onHidden);
        };
        this.$watch("$store.shell.dark", () => {
          timeline.refresh();
          map.refresh();
        });
        const tick = (now: number) => {
          frameId = requestAnimationFrame(tick);
          if (this.loading) return;
          if (ws.clock.advance(now)) this.show();
          this.playing = ws.clock.playing;
        };
        frameId = requestAnimationFrame(tick);
        await this.load(sourceStore().sessionId);
      },

      destroy() {
        alive = false;
        cancelAnimationFrame(frameId);
        stopKeys();
        if (!this.loading) ws.clock.pause();
        timeline?.destroy();
        map?.destroy();
      },

      /** Open a session in the views, its unsaved edits still there when it is the one already open. */
      async load(sessionId: string) {
        this.loading = true;
        this.sessionId = sessionId;
        this.error = "";
        const previous = Workspace.current;
        try {
          ws = await Workspace.open(sourceStore().id, sessionId);
        } catch (error) {
          this.error = errorText(error);
          return;
        }
        if (!alive) return;
        if (previous && previous !== ws && previous.editor.dirty) toast.warning(`The edits of ${previous.header.session_id} were not saved and are gone.`);
        const { header, arrays } = ws;
        timeline.load(header, arrays.speed, ws.speedTop);
        map.load(header, arrays, ws.speedTop);
        selected = null;
        this.sessionId = header.session_id;
        this.facts = factsLine(header);
        this.notes = ws.saved?.notes ?? "";
        this.occupancyChoices = [CURRENT, ALL, ...new Set(header.epochs.map((e) => e.epoch))];
        this.occupancy = CURRENT;
        map.setOccupancy(CURRENT);
        this.speedIndex = (SPEEDS as readonly number[]).indexOf(ws.clock.speed);
        this.loading = false;
        this.sync();
        this.show();
      },

      /** Redraw everything that follows the cursor: the lanes' cursor, the map and the live tiles. */
      show() {
        const index = ws.clock.index;
        timeline.setCursor(index);
        map.draw(index);
        Object.assign(this, liveTiles(ws.header, ws.arrays, index));
        this.epochNow = epochAt(ws.header.epochs, index + 1);
        this.showRun();
      },

      /** The run under the cursor, which the flag button acts on, and whether it is flagged. */
      showRun() {
        const run = runAt(ws.header.runs, ws.clock.index + 1);
        this.runNow = run?.run ?? null;
        this.runFlagged = run !== null && ws.preview.flagged_runs.includes(run.run);
        this.runLine = run ? `run ${run.run}, path ${run.path_id} ${run.clean ? "clean" : "dirty"}${this.runFlagged ? ", flagged" : ""}` : "no run under the cursor";
      },

      /** Redraw everything that follows the edits: the cards, the summary, the lanes' blocks, the selection and the marks. */
      sync() {
        const { preview, editor, header } = ws;
        this.blocks = blockCards(preview.blocks, header, selected);
        this.summary = summaryTiles(preview, header, ws.settings);
        this.stateLine = stateLine(ws.saved, editor.edits.length, editor.dirty, preview.skipped.length);
        this.editCount = editor.edits.length;
        this.marksLine = marksLine(editor.markIn, editor.markOut, header.rate_hz);
        this.hasRange = editor.range !== null;
        this.hasSelection = selected !== null;
        this.selectedName = this.blocks.find((b) => b.selected)?.name ?? "";
        timeline.setBlocks(preview.blocks, preview.flagged_runs);
        timeline.setSelection(selected);
        timeline.setMarks(editor.markIn, editor.markOut);
        map.setPath(selected && [selected.frame_start, selected.frame_end]);
        this.showRun();
      },

      command(command: Command) {
        const rate = ws.header.rate_hz;
        const moves: Partial<Record<Command, () => void>> = {
          play: () => this.toggle(),
          back: () => this.step(-1),
          forward: () => this.step(1),
          "back-second": () => this.step(-rate),
          "forward-second": () => this.step(rate),
          "previous-run": () => this.jumpRun(-1),
          "next-run": () => this.jumpRun(1),
          clear: () => this.clear(),
        };
        if (command === "confirm") void this.act("accept");
        else if (command === "undo") void this.undo();
        else moves[command]?.();
      },

      toggle() {
        ws.clock.toggle(performance.now());
        this.playing = ws.clock.playing;
      },
      pause() {
        ws.clock.pause();
        this.playing = false;
      },
      setSpeed() {
        ws.clock.setSpeed(SPEEDS[this.speedIndex], performance.now());
      },
      seek(index: number) {
        ws.clock.seek(index, performance.now());
        this.show();
      },
      step(frames: number) {
        ws.clock.step(frames, performance.now());
        this.show();
      },
      /** Move to the start of the previous or next run. */
      jumpRun(direction: 1 | -1) {
        const here = ws.clock.index + 1;
        const starts = ws.header.runs.map((r) => r.frame_start).sort((a, b) => a - b);
        const target = direction > 0 ? starts.find((s) => s > here) : starts.reverse().find((s) => s < here);
        if (target !== undefined) this.step(target - here);
      },
      setOccupancy(choice: string) {
        this.occupancy = choice;
        map.setOccupancy(choice);
      },
      toggleLayer(key: LayerKey) {
        this.layers[key] = !this.layers[key];
        timeline.setLayers({ ...this.layers });
      },
      zoomAll() {
        timeline.zoomAll();
      },
      zoomIn() {
        timeline.zoomIn();
      },
      zoomOut() {
        timeline.zoomOut();
      },
      fitBlock() {
        timeline.fitSelected();
      },

      selectBlock(block: ReviewBlock | null) {
        selected = block;
        this.sync();
      },
      select(first: number) {
        this.selectBlock(ws.preview.blocks.find((b) => b.frame_start === first) ?? null);
      },
      /** Escape: no selection and no marks, the zoom stays. */
      clear() {
        ws.editor.clearMarks();
        this.selectBlock(null);
      },
      /** The lanes zoomed out and no block selected, the marks stay. */
      wholeSession() {
        timeline.zoomAll();
        this.selectBlock(null);
      },
      mark(which: "in" | "out") {
        ws.editor[which === "in" ? "markIn" : "markOut"] = ws.clock.index + 1;
        this.sync();
      },

      /** Make an action's edit, which the server applies or refuses with its reason. */
      async act(action: Action, first?: number) {
        try {
          const result = await ws.edit(() => editFor(action, targetOf(first)));
          if (typeof result === "string") {
            toast.warning(result);
            return;
          }
          selected = reselected(selected, ws.preview.blocks, result);
          if (result.op === "new") ws.editor.clearMarks();
          toast.success(`Added ${label(result)}, ${counted(ws.editor.edits.length, "edit")} not saved yet`);
          this.sync();
        } catch (error) {
          toast.error(errorText(error));
        }
      },
      async undo() {
        try {
          const undone = await ws.undo();
          if (!undone) {
            toast.warning("There is nothing to undo.");
            return;
          }
          selected = reselected(selected, ws.preview.blocks, { op: "accept" });
          toast.success(`Undid the ${label(undone)}, ${counted(ws.editor.edits.length, "edit")} left`);
          this.sync();
        } catch (error) {
          toast.error(errorText(error));
        }
      },
      async reset() {
        try {
          await ws.reset();
          selected = null;
          toast.success("The edits are cleared and the blocks are automatic again. A saved review stays on disk until you save.");
          this.sync();
        } catch (error) {
          toast.error(errorText(error));
        }
      },

      /** Write the review, then open the next session still to review. */
      async save() {
        this.busy = true;
        try {
          const saved = await ws.save(this.notes);
          toast.success(`Saved ${saved.path}, ${saved.overwrote ? "replacing the earlier review" : "a new file"}`);
          this.sync();
          await this.openNext();
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },
      async openNext() {
        const rows = await listSessions(ws.sid);
        const next = rows.find((row) => !row.reviewed && row.n_automatic !== null && row.session_id !== ws.header.session_id);
        if (!next) {
          toast.success("Every session with frames has a review now.");
          return;
        }
        sourceStore().openSession(next.session_id);
        await this.load(next.session_id);
        toast.success(`Opened the next session to review, ${next.session_id}`);
      },
    };
  });
}

const noSession = `
  <div class="flex flex-col items-start gap-2 text-sm">
    <p x-text="$store.source.problem('transformed') || '${NO_SESSION}'"></p>
    <a href="#/sessions" class="${BUTTON_PRIMARY}">Choose a session</a>
  </div>`;

export const replayPage: Page = {
  id: "replay",
  title: "Replay",
  html: `
    <div class="h-full">
      <template x-if="$store.source.problem('transformed') || !$store.source.sessionId">
        <div class="grid h-full grid-cols-12 grid-rows-6 gap-4">${card("Replay", noSession)}</div>
      </template>
      <template x-if="!$store.source.problem('transformed') && $store.source.sessionId">${replayGrid}</template>
    </div>`,
  register: registerReplay,
};
