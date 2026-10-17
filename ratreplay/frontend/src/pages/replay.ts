import Alpine from "alpinejs";
import { errorText, listSessions } from "../api/client";
import type { ReviewBlock } from "../api/types";
import { allLayers, LAYERS } from "../draw/layers";
import type { LayerKey } from "../draw/layers";
import { timeLabel } from "../draw/lanes";
import { MapView, THIN_PATH } from "../draw/map";
import { ALL, CURRENT, OccupancyBackdrop } from "../draw/occupancy";
import { sessionScene } from "../draw/session-scene";
import { Timeline } from "../draw/timeline";
import { epochAt, runAt } from "../session/at";
import { REAL_TIME, SPEEDS } from "../session/clock";
import { editFor, label, reselected } from "../session/editor";
import type { Action } from "../session/editor";
import { startPlayback } from "../session/playback";
import { Workspace } from "../session/workspace";
import { sourceStore } from "../state/source";
import { card } from "../ui/card";
import type { Command } from "../ui/keys";
import { BUTTON_PRIMARY } from "../ui/style";
import { counted } from "../ui/text";
import { toast } from "../ui/toast";
import type { Page } from "./page";
import { replayGrid } from "./replay-html";
import { blockCards, factsLine, liveTiles, marksLine, stateLine, summaryTiles } from "./replay-view";
import type { BlockCard, Tile } from "./replay-view";

const NO_SESSION = "No session is open, choose one on the Sessions page.";

// The chips of the timeline keep their state when the person visits another page and comes back.
const layers = allLayers();

function registerReplay(): void {
  Alpine.data("replayPage", () => {
    // The session, its views and the playback loop live in plain objects, only scalars and small lists go to Alpine.
    let ws!: Workspace;
    let timeline!: Timeline;
    let map!: MapView;
    let occupancy!: OccupancyBackdrop;
    let selected: ReviewBlock | null = null;
    let alive = true;
    let stopPlayback = () => {};
    const targetOf = (position?: number) => {
      const frame = ws.clock.index + 1;
      const block = position === undefined ? selected : (ws.preview.blocks[position] ?? null);
      return { cursor: frame, block, blocks: ws.preview.blocks, range: ws.editor.range, run: runAt(ws.header.runs, frame) };
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
          select: (position: number) => this.select(position),
          view: (from: number, to: number) => (this.shown = `${timeLabel(from)} to ${timeLabel(to)}`),
        };
        timeline = new Timeline(this.$refs.timeline, handlers);
        map = new MapView(this.$refs.map);
        stopPlayback = startPlayback(this);
        this.$watch("$store.shell.dark", () => {
          timeline.refresh();
          map.refresh();
        });
        await this.load(sourceStore().sessionId);
      },

      destroy() {
        alive = false;
        stopPlayback();
        timeline?.destroy();
        map?.destroy();
      },

      /** Open a session in the views, its unsaved edits still there when it is the one already open. */
      async load(sessionId: string) {
        this.loading = true;
        this.sessionId = sessionId;
        this.error = "";
        try {
          ws = await Workspace.open(sourceStore().id, sessionId);
        } catch (error) {
          this.error = errorText(error);
          return;
        }
        if (!alive) return;
        const { header, arrays } = ws;
        selected = null;
        timeline.load(this.scene());
        occupancy = new OccupancyBackdrop(header);
        map.load({ ...arrays, rateHz: header.rate_hz }, occupancy, ws.speedTop);
        this.sessionId = header.session_id;
        this.facts = factsLine(header);
        this.notes = ws.saved?.notes ?? "";
        this.occupancyChoices = [CURRENT, ALL, ...new Set(header.epochs.map((e) => e.epoch))];
        this.occupancy = CURRENT;
        this.speedIndex = (SPEEDS as readonly number[]).indexOf(ws.clock.speed);
        this.loading = false;
        this.sync();
        this.show();
      },

      /** The timeline's bars and layers for the blocks as they stand, the flagged runs and the layers that are on. */
      scene() {
        return sessionScene(ws.header, ws.preview.blocks, ws.preview.flagged_runs, this.layers, ws.arrays.speed, ws.speedTop);
      },
      clock() {
        return this.loading ? null : ws.clock;
      },
      runStarts() {
        return ws.header.runs.map((r) => r.frame_start);
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
        this.blocks = blockCards(preview.blocks, header, selected, ws.settings);
        this.summary = summaryTiles(preview, header, ws.settings);
        this.stateLine = stateLine(ws.saved, editor.edits.length, editor.dirty, preview.skipped.length);
        this.editCount = editor.edits.length;
        this.marksLine = marksLine(editor.markIn, editor.markOut, header.rate_hz);
        this.hasRange = editor.range !== null;
        this.hasSelection = selected !== null;
        this.selectedName = this.blocks.find((b) => b.selected)?.name ?? "";
        timeline.setScene(this.scene());
        timeline.setSelection(selected && { lane: "blocks", first: selected.frame_start, last: selected.frame_end });
        timeline.setMarks(editor.markIn, editor.markOut);
        map.setStretches(selected ? [{ first: selected.frame_start, last: selected.frame_end, ...THIN_PATH }] : []);
        this.showRun();
      },

      /** The keys that are not playback keys. */
      command(command: Command) {
        if (command === "confirm") void this.act("accept");
        else if (command === "undo") void this.undo();
        else if (command === "clear") this.clear();
      },

      togglePlay() {
        ws.clock.toggle(performance.now());
        this.playing = ws.clock.playing;
      },
      setSpeed() {
        ws.clock.setSpeed(SPEEDS[this.speedIndex], performance.now());
      },
      seek(index: number) {
        ws.clock.seek(index, performance.now());
        this.show();
      },
      setOccupancy(choice: string) {
        this.occupancy = choice;
        occupancy.choice = choice;
        map.redraw();
      },
      toggleLayer(key: LayerKey) {
        this.layers[key] = !this.layers[key];
        timeline.setScene(this.scene());
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
      select(position: number) {
        this.selectBlock(ws.preview.blocks[position] ?? null);
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
      async act(action: Action, position?: number) {
        try {
          const result = await ws.edit(() => editFor(action, targetOf(position)));
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
