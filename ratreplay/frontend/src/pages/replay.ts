import Alpine from "alpinejs";
import { errorText, listSessions, StaleApiError } from "../api/client";
import type { MadeBlock, SessionRow } from "../api/types";
import { allLayers, LAYERS, layerMeanings } from "../draw/layers";
import type { LayerKey } from "../draw/layers";
import { FRAMES_LANE, timeLabel } from "../draw/lanes";
import { MapView, THIN_PATH } from "../draw/map";
import { defaultMapChoice, OccupancyBackdrop } from "../draw/occupancy";
import { sessionScene } from "../draw/session-scene";
import { Timeline } from "../draw/timeline";
import type { LaneClick } from "../draw/timeline";
import { epochAt, runAt } from "../session/at";
import { REAL_TIME, SPEEDS } from "../session/clock";
import { editFor, label, reselected } from "../session/editor";
import type { Action } from "../session/editor";
import { startPlayback } from "../session/playback";
import { Workspace } from "../session/workspace";
import { healthStore, warnStale } from "../state/health";
import { settingsStore } from "../state/settings";
import { card } from "../ui/card";
import type { Command } from "../ui/keys";
import { BUTTON_PRIMARY } from "../ui/style";
import { counted } from "../ui/text";
import { toast } from "../ui/toast";
import { askAndChange } from "./exclusion";
import { filterRows } from "./incoming-view";
import type { Page } from "./page";
import { replayGrid } from "./replay-html";
import { chipsOf, leaveQuestion, neighbours, pickerOrder, stepReason } from "./replay-picker";
import type { Step } from "./replay-picker";
import { escapeClears, laneSelection, pickedRun, selectionText, toggled } from "./replay-selection";
import type { Picked } from "./replay-selection";
import { blockCards, factsLine, liveTiles, marksLine, saveToast, sessionNotes, sessionStatus, settingsLine, summaryTiles } from "./replay-view";
import type { BlockCard, Note, Status, Tile } from "./replay-view";

const NO_SESSION = "No session is open, choose one on the Incoming page.";
const PROBLEM = "$store.health.problem('transformed', 'processed', 'environments')";

// The layers of the timeline and of the map keep their state when the person visits another page and comes back.
const layers = allLayers();
const mapLayers = { ...defaultMapChoice(), trail: true };

function registerReplay(): void {
  Alpine.data("replayPage", () => {
    // The session, its views and the playback loop live in plain objects, only scalars and small lists go to Alpine.
    let ws!: Workspace;
    let timeline!: Timeline;
    let map!: MapView;
    let occupancy!: OccupancyBackdrop;
    // What is selected: a block, or an epoch, a run or a frame, never both.
    let selected: MadeBlock | null = null;
    let picked: Picked | null = null;
    let alive = true;
    let stopPlayback = () => {};
    // The run a flag acts on: the run selected, else the run under the cursor.
    const runInReach = () => pickedRun(ws.header, picked) ?? runAt(ws.header.runs, ws.clock.index + 1);
    const targetOf = (position?: number) => {
      const block = position === undefined ? selected : (ws.preview.blocks[position] ?? null);
      return { cursor: ws.clock.index + 1, block, blocks: ws.preview.blocks, range: ws.editor.range, run: runInReach() };
    };

    return {
      loading: true,
      busy: false,
      sessionId: "",
      facts: "",
      status: { state: { text: "", chip: "", title: "" }, flags: [] } as Status,
      selectionLine: "",
      inDataset: true,
      excluded: false,
      reason: "",
      notices: [] as Note[],
      settingsLine: "",
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
      mapLayers,
      epochKinds: [] as string[],
      layers,
      layerList: LAYERS,
      meanings: {} as Record<LayerKey, string>,
      marksLine: "",
      runLine: "",
      runNow: null as number | null,
      runFlagged: false,
      notes: "",
      editCount: 0,
      hasSelection: false,
      hasRange: false,
      hasMarks: false,
      selectedName: "",
      // The picker: the sessions index in the order the arrows walk, read once per visit and after a save or an exclusion, and the list under the session id.
      index: [] as SessionRow[],
      indexError: "",
      pickerOpen: false,
      filter: "",
      pickerTop: 0,
      pickerLeft: 0,

      get speedLabel() {
        return `${SPEEDS[this.speedIndex]}x`;
      },
      get mapTitle() {
        return [this.sessionId, this.epochNow, this.selectedName].filter(Boolean).join(", ");
      },
      /** The sessions the list shows and the arrows walk: those matching the filter, which is empty while the list is closed. */
      get listed() {
        return filterRows(this.index, this.filter);
      },
      get listedText() {
        if (this.indexError) return `The sessions could not be listed: ${this.indexError}`;
        return this.listed.length ? `${this.listed.length} of ${counted(this.index.length, "session")}` : "No session matches";
      },

      async init() {
        await this.$nextTick();
        if (!alive) return;
        const handlers = {
          seek: (index: number) => this.seek(index),
          click: (hit: LaneClick) => this.laneClick(hit),
          view: (from: number, to: number) => (this.shown = `${timeLabel(from)} to ${timeLabel(to)}`),
        };
        timeline = new Timeline(this.$refs.timeline, handlers);
        map = new MapView(this.$refs.map);
        stopPlayback = startPlayback(this);
        this.$watch("$store.shell.dark", () => {
          timeline.refresh();
          map.refresh();
        });
        this.$watch("$store.settings.current", () => void this.settingsChanged());
        void this.refreshIndex();
        await this.load(healthStore().sessionId);
      },

      destroy() {
        alive = false;
        stopPlayback();
        timeline?.destroy();
        map?.destroy();
      },

      /**
       * Open a session in the views, its unsaved edits still there when it is the one already open. Gives back whether it opened. When it
       * does not, the reason goes to the warning stack and the console, and the page falls back to its empty state with the link to choose a session.
       */
      async load(sessionId: string): Promise<boolean> {
        this.loading = true;
        this.sessionId = sessionId;
        try {
          ws = await Workspace.open(sessionId, { ...(await settingsStore().load()) });
          if (!alive) return false;
          if (!ws.header.rules) throw new StaleApiError();
          const { header, arrays } = ws;
          selected = null;
          picked = null;
          timeline.load(this.scene());
          for (const kind of header.selected_epochs) mapLayers.kinds[kind] ??= true;
          occupancy = new OccupancyBackdrop(header);
          occupancy.choice = mapLayers;
          map.trail = mapLayers.trail;
          map.load({ ...arrays, rateHz: header.rate_hz }, occupancy, ws.speedTop);
          this.sessionId = header.session_id;
          this.facts = factsLine(header);
          this.inDataset = header.in_dataset;
          this.excluded = ws.excluded;
          this.reason = header.reason ?? "";
          this.notes = ws.saved?.notes ?? "";
          this.epochKinds = header.selected_epochs;
          this.meanings = layerMeanings(header, ws.speedTop);
          this.speedIndex = (SPEEDS as readonly number[]).indexOf(ws.clock.speed);
          this.loading = false; // before the counts are read again, which wait for it
          this.sync();
          this.show();
          await this.settingsChanged(); // a change made while the session was loading
          return true;
        } catch (error) {
          console.error(`Could not open ${sessionId}`, error);
          if (error instanceof StaleApiError) warnStale();
          else toast.error(`Could not open ${sessionId}: ${errorText(error)}`);
          if (!Workspace.current?.editor.dirty) Workspace.current = null; // read again next time, unless unsaved edits are in it
          healthStore().closeSession(); // the page shows its empty state and the way to choose a session
          return false;
        } finally {
          this.loading = false;
        }
      },

      /** The timeline's bars and layers for the blocks as they stand, the flagged runs and the layers that are on. */
      scene() {
        return sessionScene(ws.header, ws.preview.blocks, ws.preview.flagged_runs, this.layers, ws.arrays.speed, ws.speedTop);
      },
      clock() {
        return this.loading ? null : (ws?.clock ?? null);
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

      /** The run the flag button acts on, the run selected or else the run under the cursor, and whether it is flagged. */
      showRun() {
        const run = runInReach();
        this.runNow = run?.run ?? null;
        this.runFlagged = run !== null && ws.preview.flagged_runs.includes(run.run);
        const chosen = pickedRun(ws.header, picked) !== null;
        this.runLine = run ? `${chosen ? "selected " : ""}run ${run.run}, path ${run.path_id} ${run.clean ? "clean" : "dirty"}${this.runFlagged ? ", flagged" : ""}` : "no run under the cursor";
      },

      /** Redraw everything that follows the edits: the cards, the summary, the lanes' blocks, the selection and the marks. */
      sync() {
        const { preview, editor, header } = ws;
        this.blocks = blockCards(preview.blocks, header, selected);
        this.summary = summaryTiles(preview, header, ws.settings);
        this.settingsLine = settingsLine(ws.settings);
        this.notices = sessionNotes(header, preview.refusals, editor.edits);
        this.status = sessionStatus(header, ws.saved, editor.edits.length, editor.dirty, preview.refusals.length, ws.excluded);
        this.editCount = editor.edits.length;
        this.marksLine = marksLine(editor.markIn, editor.markOut, header.rate_hz);
        this.hasRange = editor.range !== null;
        this.hasMarks = editor.markIn !== null || editor.markOut !== null;
        this.hasSelection = selected !== null;
        this.selectedName = this.blocks.find((b) => b.selected)?.name ?? "";
        this.selectionLine = selectionText(header, picked, selected, selected ? preview.blocks.indexOf(selected) : -1);
        const outline = laneSelection(header, picked, selected);
        timeline.setScene(this.scene());
        timeline.setSelection(outline);
        timeline.setMarks(editor.markIn, editor.markOut);
        map.setStretches(outline && outline.lane !== FRAMES_LANE ? [{ first: outline.first, last: outline.last, ...THIN_PATH }] : []);
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
      /** A map layer was switched: the backdrop reads the choice itself, the trail is the map's. */
      mapLayersChanged() {
        map.trail = mapLayers.trail;
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

      /** Select a block, or let go of the selection, which drops whatever else was picked. */
      selectBlock(block: MadeBlock | null) {
        selected = block;
        if (block) picked = null;
        this.sync();
      },
      select(position: number) {
        this.selectBlock(ws.preview.blocks[position] ?? null);
      },
      /** A click on a lane selects the epoch, run, block or frame under it, and a second click on the same one lets go of it. Empty lane space moves the cursor. */
      laneClick({ lane, pick, index, again }: LaneClick) {
        if (lane === "blocks" && pick !== undefined) {
          const block = ws.preview.blocks[pick];
          this.selectBlock(block === selected ? null : block);
        } else if ((lane === "session" || lane === "runs") && pick !== undefined) {
          this.pick(toggled(picked, { kind: lane === "session" ? "epoch" : "run", index: pick }));
        } else if (lane === FRAMES_LANE) {
          if (!again) this.seek(index);
          this.pick(toggled(picked, { kind: "frame", frame: index + 1 }, again));
        } else this.seek(index);
      },
      pick(next: Picked | null) {
        picked = next;
        if (next) selected = null;
        this.sync();
      },
      /** Escape: the marks go first, then the selection. The zoom stays. */
      clear() {
        const step = escapeClears(ws.editor.markIn !== null || ws.editor.markOut !== null, selected !== null || picked !== null);
        if (!step) return;
        if (step === "marks") ws.editor.clearMarks();
        else selected = picked = null;
        this.sync();
      },
      mark(which: "in" | "out") {
        ws.editor[which === "in" ? "markIn" : "markOut"] = ws.clock.index + 1;
        this.sync();
      },

      /** Count the blocks again at the settings now in use: the whole edit list is previewed and the cards, tiles and bar tips follow. */
      async settingsChanged() {
        const next = settingsStore().current;
        if (this.loading || !next || JSON.stringify(next) === JSON.stringify(ws.settings)) return;
        try {
          await ws.useSettings({ ...next });
          selected = reselected(selected, ws.preview.blocks, { op: "accept" });
          this.sync();
        } catch (error) {
          toast.error(errorText(error));
        }
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

      /** Exclude the session or include it again after asking for a note, the edits not saved stay. The notes box takes the review's notes, or keeps what was typed with the note added to it. */
      async changeExclusion() {
        this.busy = true;
        try {
          const untouched = this.notes === (ws.saved?.notes ?? "");
          let given = "";
          const saved = await askAndChange(this.sessionId, !this.excluded, (note) => {
            given = note;
            return ws.setExclusion(!this.excluded, note);
          });
          if (!saved) return;
          void this.refreshIndex();
          this.excluded = ws.excluded;
          if (untouched) this.notes = saved.review?.notes ?? "";
          else if (saved.review) this.notes = [this.notes, given].filter(Boolean).join("\n");
          this.sync();
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },

      /** Write the review and build the blocks, then open the next session still to review. */
      async save() {
        this.busy = true;
        try {
          const done = saveToast(await ws.save(this.notes));
          if (done.kind === "warning") toast.warning(done.text, done.path);
          else toast.success(done.text, done.path);
          this.sync();
          await this.openNext();
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },
      async openNext() {
        const rows = await this.refreshIndex();
        if (!rows) {
          toast.error(`The sessions could not be listed: ${this.indexError}`);
          return;
        }
        const next = rows.find((row) => !row.reviewed && row.in_dataset && row.session_id !== ws.header.session_id);
        if (!next) {
          toast.success("Every session in the dataset has a review now.");
          Workspace.current = null;
          await this.load(ws.header.session_id); // read again, so the page shows the session as saved
          return;
        }
        healthStore().openSession(next.session_id);
        if (await this.load(next.session_id)) toast.success(`Opened the next session to review, ${next.session_id}`);
      },

      /** Read the sessions index, in the API's order for the caller and in the arrows' order for the picker. None when it cannot be read, the reason kept for the list. */
      async refreshIndex(): Promise<SessionRow[] | null> {
        try {
          const rows = await listSessions();
          this.index = pickerOrder(rows);
          this.indexError = "";
          return rows;
        } catch (error) {
          this.indexError = errorText(error);
          return null;
        }
      },
      /** Open or close the list under the session id, with an empty filter and the cursor in it. */
      async togglePicker() {
        if (this.pickerOpen) {
          this.closePicker();
          return;
        }
        if (this.indexError) await this.refreshIndex();
        const box = (this.$refs.pickerButton as HTMLElement).getBoundingClientRect();
        this.pickerLeft = box.left;
        this.pickerTop = box.bottom + 4;
        this.filter = "";
        this.pickerOpen = true;
        await this.$nextTick();
        (this.$refs.pickerFilter as HTMLElement).focus();
      },
      closePicker() {
        this.pickerOpen = false;
        this.filter = "";
      },
      /** Why an arrow cannot step now, none when it can. */
      stepWhy(step: Step): string {
        if (this.loading || this.busy) return this.loading ? "session still loading" : "wait, still working";
        if (this.indexError) return "the sessions could not be listed";
        return stepReason(this.listed, this.sessionId, step, this.filter.trim() !== "");
      },
      stepTitle(step: Step): string {
        return `Open the ${step} session, ${neighbours(this.listed, this.sessionId)[step]?.session_id}`;
      },
      /** Open the session before or after this one in the list shown. */
      async step(step: Step) {
        const target = neighbours(this.listed, this.sessionId)[step];
        if (target && !this.stepWhy(step)) await this.openFromList(target.session_id);
      },
      /** Enter in the filter opens the first session it leaves. */
      async openFirst() {
        const first = this.listed[0];
        if (first) await this.openFromList(first.session_id);
      },
      /** Open a session of the list, asking first when the one open has edits that are not saved. */
      async openFromList(sessionId: string) {
        this.closePicker();
        if (this.loading || this.busy || sessionId === this.sessionId) return;
        const unsaved = Workspace.unsavedWhenOpening(sessionId);
        if (unsaved && !confirm(leaveQuestion(unsaved.header.session_id, unsaved.editor.edits.length))) return;
        healthStore().openSession(sessionId);
        if (await this.load(sessionId)) toast.success(`Opened ${sessionId}`);
      },
      chipsOf(row: SessionRow) {
        return chipsOf(row, this.sessionId);
      },
    };
  });
}

const noSession = `
  <div class="flex flex-col items-start gap-2 text-sm">
    <p x-text="${PROBLEM} || '${NO_SESSION}'"></p>
    <a href="#/incoming" class="${BUTTON_PRIMARY}">Choose a session</a>
  </div>`;

export const replayPage: Page = {
  id: "replay",
  title: "Replay",
  html: `
    <div class="h-full">
      <template x-if="${PROBLEM} || !$store.health.sessionId">
        <div class="grid h-full grid-cols-12 grid-rows-6 gap-4">${card("Replay", noSession)}</div>
      </template>
      <template x-if="!${PROBLEM} && $store.health.sessionId">${replayGrid}</template>
    </div>`,
  register: registerReplay,
};
