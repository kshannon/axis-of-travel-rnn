import Alpine from "alpinejs";
import { errorText, getFormat, getSelected, listBlocks, listSessions, rebuildAll } from "../api/client";
import { formatGroups } from "../api/describe";
import type { FormatGroup } from "../api/describe";
import { Visit } from "../router";
import { healthStore } from "../state/health";
import { settingsStore } from "../state/settings";
import { clickHeader, sortArrow, sortRows } from "../ui/table";
import type { Sort } from "../ui/table";
import { counted } from "../ui/text";
import { stampWithSince } from "../ui/time";
import { toast } from "../ui/toast";
import { outgoingRoot } from "./outgoing-html";
import { COLUMNS, failedLines, outgoingGroups, outRows, rebuildPrompt, rebuildSummary, rowNote, syntheticView, writeView } from "./outgoing-view";
import type { OutRow } from "./outgoing-view";
import type { Page } from "./page";
import { selectedLine } from "./settings-view";

function registerOutgoing(): void {
  Alpine.data("outgoingPage", () => {
    // Each read of what is built is numbered so that only the latest answer counts.
    let latest = 0;
    const visit = new Visit();

    return {
      groups: [] as FormatGroup[],
      version: 0,
      rows: [] as OutRow[],
      loading: true,
      error: "",
      selectedLine: "",
      columns: COLUMNS,
      sort: null as Sort | null,
      openId: "",
      busy: false,
      rebuilding: false,
      stamp: stampWithSince,

      get view() {
        const { found } = healthStore();
        return found && writeView(found.processed);
      },
      get syntheticView() {
        const { found } = healthStore();
        return found && syntheticView(found.synthetic);
      },
      /** Why what is built cannot be listed, none when the three folders are usable. */
      get blocked() {
        return healthStore().problem("transformed", "processed", "environments");
      },
      get reviews() {
        return healthStore().found?.processed.counts.reviews ?? 0;
      },
      get canRebuild() {
        return !this.blocked && this.reviews > 0;
      },
      get shown() {
        return sortRows(this.rows, COLUMNS, this.sort);
      },
      get summary() {
        const blocks = this.rows.reduce((total, row) => total + row.blocks, 0);
        const failed = this.rows.reduce((total, row) => total + row.failed.length, 0);
        return `${counted(this.rows.length, "session")}, ${counted(blocks, "block")} built, ${failed} failed`;
      },

      /** Read the format once, then what is built each time the folders are read. */
      async init() {
        void this.loadFormat();
        this.$watch("$store.health.found", () => void this.refresh());
        await healthStore().load();
      },
      destroy() {
        visit.hide();
      },
      async loadFormat() {
        try {
          const contract = await getFormat();
          this.groups = outgoingGroups(formatGroups(contract));
          this.version = contract.version;
        } catch (error) {
          visit.say(() => toast.error(errorText(error)));
        }
      },
      /** The table of what is built, at the settings in use, and the settings selected for export. */
      async refresh() {
        const mine = ++latest;
        if (this.blocked) {
          this.rows = [];
          this.selectedLine = "";
          this.loading = false;
          return;
        }
        try {
          const settings = await settingsStore().load();
          const [readiness, sessions, selected] = await Promise.all([listBlocks({ ...settings }), listSessions(), getSelected()]);
          if (mine !== latest) return;
          this.rows = outRows(readiness, sessions);
          this.selectedLine = selectedLine(selected.selected);
          this.error = "";
        } catch (error) {
          if (mine === latest) this.error = errorText(error);
        }
        this.loading = false;
      },

      sortBy(key: string) {
        this.sort = clickHeader(this.sort, key);
      },
      arrow(key: string) {
        return sortArrow(this.sort, key);
      },
      toggle(row: OutRow) {
        this.openId = this.openId === row.session_id ? "" : row.session_id;
      },
      failedLines,
      rowNote,

      /** Build every reviewed session's blocks again after a confirmation, at the settings selected for export when there are some, else the settings in use. */
      async rebuildAll() {
        this.busy = true;
        try {
          const { selected } = await getSelected();
          const settings = selected?.settings ?? (await settingsStore().load());
          if (!confirm(rebuildPrompt(this.reviews, settings, healthStore().found!.processed.root!))) return;
          this.rebuilding = true;
          const result = await rebuildAll(settings);
          const { failed, errors } = result.totals;
          if (failed || errors) toast.warning(rebuildSummary(result));
          else toast.success(rebuildSummary(result), healthStore().found!.processed.root!);
          await healthStore().load();
        } catch (error) {
          toast.error(errorText(error));
        } finally {
          this.busy = false;
          this.rebuilding = false;
        }
      },
    };
  });
}

export const outgoingPage: Page = {
  id: "outgoing",
  title: "Outgoing",
  html: outgoingRoot,
  register: registerOutgoing,
};
