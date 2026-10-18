import Alpine from "alpinejs";
import { errorText } from "../api/client";
import { blockScene } from "../draw/block-scene";
import { EnvironmentBackdrop, extentOf } from "../draw/environment";
import { timeLabel } from "../draw/lanes";
import { MapView } from "../draw/map";
import { Timeline } from "../draw/timeline";
import { BlockPlayer } from "../session/block";
import { settingsStore } from "../state/settings";
import { folderPage } from "../ui/gate";
import { belongsToTarget, commandOf } from "../ui/keys";
import { settingsText } from "../ui/text";
import { toast } from "../ui/toast";
import { blockLine, NO_LINE } from "./blocks-view";
import type { Page } from "./page";
import { windowsRoot } from "./windows-html";
import { jumpTarget, noWindowReason, stepWindow, windowChecks, windowsOk, windowSpan, windowStretches, windowVerdict } from "./windows-view";
import type { Check } from "./windows-view";

function registerWindows(): void {
  Alpine.data("windowsPage", () => {
    // The block comes from the Blocks page, its arrays and views are plain objects.
    const player = BlockPlayer.holding();
    let timeline!: Timeline;
    let map!: MapView;
    let stopKeys = () => {};
    let alive = true;

    return {
      ready: player !== null,
      line: player ? blockLine(player.header.row, player.windows.verdict) : NO_LINE,
      settingsLine: player ? settingsText(player.settings) : "",
      count: player?.windows.count ?? 0,
      noWindow: player ? noWindowReason(player.windows) : "",
      okCount: player ? windowsOk(player.windows.rows) : 0,
      index: 0,
      jump: 1,
      checks: [] as Check[],
      windowOk: true,
      verdict: "",
      span: "",
      viewing: "",

      async init() {
        if (!player) return;
        try {
          await player.useSettings({ ...(await settingsStore().load()) }); // changed on the Replay page since the block was opened
        } catch (error) {
          toast.error(errorText(error));
        }
        await this.$nextTick();
        if (!alive) return;
        const { header, arrays } = player;
        timeline = new Timeline(this.$refs.timeline, {
          select: (index) => this.goTo(index + 1),
          view: (from, to) => (this.viewing = `${timeLabel(from)} to ${timeLabel(to)}`),
        });
        map = new MapView(this.$refs.map);
        timeline.load(blockScene(header, player.windows.rows, player.settings, arrays.speed, player.speedTop));
        map.load({ ...arrays, rateHz: header.rate_hz }, new EnvironmentBackdrop(header.geometry, extentOf(header.geometry, arrays.x, arrays.y)), player.speedTop, false);
        const onKey = (event: KeyboardEvent) => {
          const command = commandOf(event);
          if (!this.count || (command !== "back" && command !== "forward") || belongsToTarget({ key: event.key, target: event.target as Element | null })) return;
          event.preventDefault();
          this.step(command === "back" ? -1 : 1);
        };
        addEventListener("keydown", onKey);
        stopKeys = () => removeEventListener("keydown", onKey);
        this.$watch("$store.shell.dark", () => {
          timeline.refresh();
          map.refresh();
        });
        this.summarize();
        if (this.count) this.show();
      },

      destroy() {
        alive = false;
        stopKeys();
        timeline?.destroy();
        map?.destroy();
      },

      /** The block's totals and the settings, from the server's answer at the settings in use. */
      summarize() {
        const { windows, header, settings } = player!;
        this.line = blockLine(header.row, windows.verdict);
        this.settingsLine = settingsText(settings);
        this.count = windows.count;
        this.noWindow = noWindowReason(windows);
        this.okCount = windowsOk(windows.rows);
      },

      /** Draw the window: its checks and verdict from its row, its path on the map and the lanes zoomed to it. */
      show() {
        const { windows, header, settings } = player!;
        const window = windows.rows[this.index];
        this.jump = this.index + 1;
        this.checks = windowChecks(window, settings);
        this.windowOk = window.ok;
        this.verdict = windowVerdict(window);
        this.span = windowSpan(window);
        timeline.setSelection({ lane: "windows", first: window.first + 1, last: window.stop });
        timeline.fitSelected();
        map.setStretches(windowStretches(header, window));
      },

      step(direction: 1 | -1) {
        this.index = stepWindow(this.index, direction, this.count);
        this.show();
      },
      /** Show the window with this number, counted from 1 as the jump box shows them. */
      goTo(typed: unknown) {
        const target = jumpTarget(typed, this.count);
        if (target === null) toast.warning(`There is no window ${typed}, the windows are numbered 1 to ${this.count}.`);
        else this.index = target;
        this.show();
      },
      fitWindow() {
        timeline.fitSelected();
      },
      zoomAll() {
        timeline.zoomAll();
      },
    };
  });
}

export const windowsPage: Page = {
  id: "windows",
  title: "Windows",
  html: folderPage("Windows", windowsRoot, "processed", "environments"),
  register: registerWindows,
};
