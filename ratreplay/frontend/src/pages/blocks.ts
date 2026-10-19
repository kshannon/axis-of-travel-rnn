import Alpine from "alpinejs";
import { errorText, listBlocks } from "../api/client";
import type { WindowSettings } from "../api/types";
import { blockScene } from "../draw/block-scene";
import { EnvironmentBackdrop, extentOf } from "../draw/environment";
import { timeLabel } from "../draw/lanes";
import { MapView, THIN_PATH } from "../draw/map";
import { Timeline } from "../draw/timeline";
import { BlockPlayer } from "../session/block";
import { REAL_TIME, SPEEDS, stepSpeed } from "../session/clock";
import { startPlayback } from "../session/playback";
import { settingsStore } from "../state/settings";
import type { Fact } from "../ui/facts";
import { folderPage } from "../ui/gate";
import { clickHeader, sortArrow, sortRows } from "../ui/table";
import type { Sort } from "../ui/table";
import { toast } from "../ui/toast";
import { blocksRoot } from "./blocks-html";
import { blockLine, COLUMNS, datasetName, indexFacts, indexRows, liveTiles, NO_LINE, openBlockFacts, REAL, totalTiles, WHICH_CHOICES } from "./blocks-view";
import type { IndexRow, TotalTile } from "./blocks-view";
import type { Page } from "./page";
import { judgedLine } from "./settings-view";

// The dataset the index judges, kept while the person visits other pages.
let chosen = REAL;

function registerBlocks(): void {
  Alpine.data("blocksPage", () => {
    // The block and its views live in plain objects, only scalars and small lists go to Alpine.
    let player: BlockPlayer | null = null;
    let timeline!: Timeline;
    let map!: MapView;
    let drawn = "";
    let alive = true;
    let latest = 0;
    let stopPlayback = () => {};

    return {
      view: "index" as "index" | "block",
      loading: true,
      busy: false,
      opening: false,
      error: "",
      choices: WHICH_CHOICES,
      which: chosen,
      tried: null as WindowSettings | null,
      judgedLine: "",
      totals: [] as TotalTile[],
      rows: [] as IndexRow[],
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
        this.$watch("$store.settings.current", () => void this.settingsChanged());
        await this.start();
      },

      destroy() {
        alive = false;
        stopPlayback();
        timeline?.destroy();
        map?.destroy();
      },

      /** The index at the settings in use, and the block that was open when the person left. */
      async start() {
        try {
          await this.judge();
          const open = BlockPlayer.holding();
          if (open) {
            await this.load(open.header.row.block_id);
            this.view = "block";
          }
        } catch (error) {
          this.error = errorText(error);
        }
        this.loading = false;
      },

      /** Every block's verdict and the totals at the settings in use, which the Settings page sets and the Replay page counts at too. */
      async judge() {
        const mine = ++latest;
        const index = await listBlocks({ ...(await settingsStore().load()) }, this.which);
        if (mine !== latest) return;
        chosen = this.which;
        this.tried = index.settings;
        this.rows = indexRows(index);
        this.totals = totalTiles(index.totals);
        this.judgedLine = judgedLine(index.settings, this.choices.length > 1 ? "" : datasetName(this.which));
        this.error = "";
        await BlockPlayer.holding()?.useSettings({ ...index.settings });
      },

      /** The dataset changed: judge again and say so when the API refuses. */
      async change() {
        this.busy = true;
        try {
          await this.judge();
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
        }
      },

      /** The settings in use changed, which the store is shared for: judge again at them. */
      async settingsChanged() {
        const next = settingsStore().current;
        if (this.loading || !next || JSON.stringify(next) === JSON.stringify(this.tried)) return;
        await this.change();
      },

      sortBy(key: string) {
        this.sort = clickHeader(this.sort, key);
      },
      arrow(key: string) {
        return sortArrow(this.sort, key);
      },
      toggle(row: IndexRow) {
        this.openId = this.openId === row.block_id ? "" : row.block_id;
      },
      facts: indexFacts,

      /** Load a block into the views at the settings tried. The zoom is kept when the block is the one already drawn. */
      async load(blockId: string) {
        player = await BlockPlayer.open(blockId, { ...this.tried! });
        const { header, arrays, windows, settings } = player;
        const scene = blockScene(header, windows.rows, settings, arrays.speed, player.speedTop);
        if (drawn !== blockId) {
          drawn = blockId;
          timeline.load(scene);
          map.load({ ...arrays, rateHz: header.rate_hz }, new EnvironmentBackdrop(header.geometry, extentOf(header.geometry, arrays.x, arrays.y)), player.speedTop);
          map.setStretches([{ first: 1, last: header.row.n_frames, ...THIN_PATH }]);
        } else timeline.setScene(scene);
        this.line = blockLine(header.row, windows.verdict);
        this.openFacts = openBlockFacts(header, windows);
        this.speedIndex = (SPEEDS as readonly number[]).indexOf(player.clock.speed);
        this.show();
      },

      async open(row: IndexRow) {
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
      changeSpeed(direction: -1 | 1) {
        this.speedIndex = stepSpeed(this.speedIndex, direction);
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
  html: folderPage("Blocks", blocksRoot, "processed", "environments"),
  register: registerBlocks,
};
