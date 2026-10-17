import Alpine from "alpinejs";
import { errorText, getWindowSettings, listBlocks, putWindowSettings } from "../api/client";
import type { BlockRow, WindowSettings } from "../api/types";
import { blockScene } from "../draw/block-scene";
import { EnvironmentBackdrop, extentOf } from "../draw/environment";
import { timeLabel } from "../draw/lanes";
import { MapView, THIN_PATH } from "../draw/map";
import { Timeline } from "../draw/timeline";
import { BlockPlayer } from "../session/block";
import { REAL_TIME, SPEEDS } from "../session/clock";
import { startPlayback } from "../session/playback";
import type { Fact } from "../ui/facts";
import { folderPage } from "../ui/gate";
import { clickHeader, sortArrow, sortRows } from "../ui/table";
import type { Sort } from "../ui/table";
import { counted } from "../ui/text";
import { toast } from "../ui/toast";
import { blocksRoot } from "./blocks-html";
import { blockFacts, blockLine, COLUMNS, liveTiles, NO_LINE, SETTING_FIELDS, testedLine, totalGroups } from "./blocks-view";
import type { TotalsGroup } from "./blocks-view";
import type { Page } from "./page";

// The settings the verdicts were last tested at, kept while the person visits other pages.
let testedSettings: WindowSettings | null = null;

function registerBlocks(): void {
  Alpine.data("blocksPage", () => {
    // The block and its views live in plain objects, only scalars and small lists go to Alpine.
    let player: BlockPlayer | null = null;
    let timeline!: Timeline;
    let map!: MapView;
    let drawn = "";
    let alive = true;
    let stopPlayback = () => {};

    return {
      view: "index" as "index" | "block",
      loading: true,
      busy: false,
      opening: false,
      error: "",
      fields: SETTING_FIELDS,
      draft: {} as WindowSettings,
      settingsPath: "",
      verdictsAt: "",
      totals: [] as TotalsGroup[],
      rows: [] as BlockRow[],
      columns: COLUMNS,
      sort: null as Sort | null,
      openId: "",
      line: NO_LINE,
      openFacts: [] as Fact[],
      playing: false,
      speeds: SPEEDS,
      speedIndex: REAL_TIME,
      time: "",
      frame: "",
      speed: "",
      lights: "",
      run: "",
      phase: "",
      viewing: "",

      get shown() {
        return sortRows(this.rows, COLUMNS, this.sort);
      },
      get speedLabel() {
        return `${SPEEDS[this.speedIndex]}x`;
      },

      async init() {
        await this.$nextTick();
        if (!alive) return;
        timeline = new Timeline(this.$refs.timeline, {
          seek: (index) => this.seek(index),
          view: (from, to) => (this.viewing = `${timeLabel(from)} to ${timeLabel(to)}`),
        });
        map = new MapView(this.$refs.map);
        stopPlayback = startPlayback(this);
        this.$watch("$store.shell.dark", () => {
          timeline.refresh();
          map.refresh();
        });
        await this.start();
      },

      destroy() {
        alive = false;
        stopPlayback();
        timeline?.destroy();
        map?.destroy();
      },

      /** The index at the settings tested last, the project's settings the first time, and the block that was open when the person left. */
      async start() {
        try {
          const answer = await getWindowSettings();
          this.settingsPath = answer.path;
          this.draft = { ...(testedSettings ?? answer.settings) };
          await this.fetchIndex();
          const open = BlockPlayer.holding();
          if (open) {
            await this.load(open.header.block_id);
            this.view = "block";
          }
        } catch (error) {
          this.error = errorText(error);
        }
        this.loading = false;
      },

      /** Every block's verdict and the totals at the settings in the inputs. */
      async fetchIndex() {
        const index = await listBlocks({ ...this.draft });
        testedSettings = index.settings;
        this.rows = index.blocks;
        this.totals = totalGroups(index.totals);
        this.verdictsAt = testedLine(index.settings);
        this.error = "";
      },

      /** The verdicts again at the settings in the inputs, and the windows of the block that is open. */
      async retest() {
        await this.fetchIndex();
        const open = BlockPlayer.holding();
        if (open) await this.load(open.header.block_id);
      },

      async test() {
        this.busy = true;
        try {
          await this.retest();
          const ok = this.rows.filter((row) => row.ok).length;
          toast.success(`Tested ${counted(this.rows.length, "block")}, ${ok} ok and ${this.rows.length - ok} in trouble`);
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },

      /** Save the settings in the inputs and test at them, so the page, the file and the tested settings kept for a return agree. */
      async saveSettings() {
        this.busy = true;
        try {
          const saved = await putWindowSettings({ ...this.draft });
          await this.retest();
          toast.success(`Saved, ${saved.overwrote ? "replacing the earlier file" : "a new file"}`, saved.path);
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },

      sortBy(key: string) {
        this.sort = clickHeader(this.sort, key);
      },
      arrow(key: string) {
        return sortArrow(this.sort, key);
      },
      toggle(row: BlockRow) {
        this.openId = this.openId === row.block_id ? "" : row.block_id;
      },
      facts: blockFacts,

      /** Load a block into the views at the settings tested. The zoom is kept when the block is the one already drawn. */
      async load(blockId: string) {
        player = await BlockPlayer.open(blockId, testedSettings!);
        const { header, arrays } = player;
        const scene = blockScene(header, arrays.speed, player.speedTop);
        if (drawn !== blockId) {
          drawn = blockId;
          timeline.load(scene);
          map.load({ ...arrays, rateHz: header.rate_hz }, new EnvironmentBackdrop(header.geometry, extentOf(header.geometry, arrays.x, arrays.y)), player.speedTop);
          map.setStretches([{ first: 1, last: header.n_frames, ...THIN_PATH }]);
        } else timeline.setScene(scene);
        this.line = blockLine(header);
        const row = this.rows.find((r) => r.block_id === blockId);
        this.openFacts = row ? blockFacts(row) : [];
        this.speedIndex = (SPEEDS as readonly number[]).indexOf(player.clock.speed);
        this.show();
      },

      async open(row: BlockRow) {
        this.opening = true;
        try {
          await this.load(row.block_id);
          this.view = "block";
          toast.success(`Opened ${row.block_id}`);
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.opening = false;
        }
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

      back() {
        player?.clock.pause();
        this.playing = false;
        this.view = "index";
      },

      /** Redraw everything that follows the cursor: the lanes' cursor, the map and the live tiles. */
      show() {
        const index = player!.clock.index;
        timeline.setCursor(index);
        map.draw(index);
        Object.assign(this, liveTiles(player!.header, player!.arrays, index));
      },
      clock() {
        return this.view === "block" && player ? player.clock : null;
      },
      runStarts() {
        return player ? player.header.runs.map((r) => r.first + 1) : [];
      },

      togglePlay() {
        player!.clock.toggle(performance.now());
        this.playing = player!.clock.playing;
      },
      setSpeed() {
        player!.clock.setSpeed(SPEEDS[this.speedIndex], performance.now());
      },
      seek(index: number) {
        player!.clock.seek(index, performance.now());
        this.show();
      },
    };
  });
}

export const blocksPage: Page = {
  id: "blocks",
  title: "Blocks",
  html: folderPage("Blocks", blocksRoot, "processed"),
  register: registerBlocks,
};
