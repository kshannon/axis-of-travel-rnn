import Alpine from "alpinejs";
import { blockScene } from "../draw/block-scene";
import { EnvironmentBackdrop, extentOf } from "../draw/environment";
import { timeLabel } from "../draw/lanes";
import { MapView } from "../draw/map";
import { Timeline } from "../draw/timeline";
import { BlockPlayer } from "../session/block";
import { sourceStore } from "../state/source";
import { sourcePage } from "../ui/gate";
import { belongsToTarget, commandOf } from "../ui/keys";
import { toast } from "../ui/toast";
import { blockLine, NO_LINE, testedLine } from "./blocks-view";
import type { Page } from "./page";
import { windowsRoot } from "./windows-html";
import { jumpTarget, stepWindow, windowChecks, windowsOk, windowSpan, windowStretches } from "./windows-view";
import type { Check } from "./windows-view";

function registerWindows(): void {
  Alpine.data("windowsPage", () => {
    // The block comes from the Blocks page, its arrays and views are plain objects.
    const player = BlockPlayer.holding(sourceStore().id);
    let timeline!: Timeline;
    let map!: MapView;
    let stopKeys = () => {};
    let alive = true;

    return {
      ready: player !== null,
      line: player ? blockLine(player.header) : NO_LINE,
      settingsLine: player ? testedLine(player.header.settings) : "",
      count: player?.header.windows.length ?? 0,
      okCount: player ? windowsOk(player.header.windows) : 0,
      index: 0,
      jump: 1,
      checks: [] as Check[],
      windowOk: true,
      span: "",
      viewing: "",

      async init() {
        if (!player) return;
        await this.$nextTick();
        if (!alive) return;
        const { header, arrays } = player;
        timeline = new Timeline(this.$refs.timeline, {
          select: (index) => this.goTo(index + 1),
          view: (from, to) => (this.viewing = `${timeLabel(from)} to ${timeLabel(to)}`),
        });
        map = new MapView(this.$refs.map);
        timeline.load(blockScene(header, arrays.speed, player.speedTop));
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
        if (this.count) this.show();
      },

      destroy() {
        alive = false;
        stopKeys();
        timeline?.destroy();
        map?.destroy();
      },

      /** Draw the window: its checks, its path on the map and the lanes zoomed to it. */
      show() {
        const { header } = player!;
        const window = header.windows[this.index];
        this.jump = this.index + 1;
        this.checks = windowChecks(window, header);
        this.windowOk = window.ok;
        this.span = windowSpan(window, header.rate_hz);
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
  html: sourcePage("Windows", windowsRoot),
  register: registerWindows,
};
