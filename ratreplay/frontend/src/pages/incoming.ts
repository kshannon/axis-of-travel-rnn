import Alpine from "alpinejs";
import { errorText, getFormat, getSession, listSessions } from "../api/client";
import { formatGroups } from "../api/describe";
import type { FormatGroup } from "../api/describe";
import type { SessionHeader, SessionRow } from "../api/types";
import { Workspace } from "../session/workspace";
import { healthStore } from "../state/health";
import { settingsStore } from "../state/settings";
import { clickHeader, sortArrow, sortRows } from "../ui/table";
import type { Sort } from "../ui/table";
import { counted } from "../ui/text";
import { toast } from "../ui/toast";
import { askAndChange } from "./exclusion";
import { incomingRoot } from "./incoming-html";
import { blockText, COLUMNS, filterRows, incomingGroups, reviewText, rowTitle, sessionFacts, stripLines, stripProblems, tiles, totalsText } from "./incoming-view";
import type { Page } from "./page";

const REPLAY_HASH = "#/replay";

function registerIncoming(): void {
  // The strip of read paths and the format. `reloaded` counts the times the config was read again, which the sessions list follows.
  Alpine.data("incomingPage", () => ({
    groups: [] as FormatGroup[],
    version: 0,
    busy: false,
    reloaded: 0,

    get lines() {
      const { found } = healthStore();
      return found ? stripLines(found) : [];
    },
    get problems() {
      return stripProblems(this.lines);
    },
    /** Why the sessions cannot be listed yet, none when the three folders are usable. */
    get blocked() {
      return healthStore().problem("transformed", "processed", "environments");
    },

    async init() {
      void this.loadFormat();
      await healthStore().load();
    },
    /** Read the formats of the files once, they do not change while the tool runs. */
    async loadFormat() {
      try {
        const contract = await getFormat();
        this.groups = incomingGroups(formatGroups(contract));
        this.version = contract.version;
      } catch (error) {
        toast.error(errorText(error));
      }
    },
    async reload() {
      this.busy = true;
      if (await healthStore().load(true)) {
        this.reloaded++;
        toast.success("Read the config file again and checked the folders");
      }
      this.busy = false;
    },
  }));

  Alpine.data("incomingSessions", () => ({
    rows: [] as SessionRow[],
    loading: true,
    error: "",
    filter: "",
    sort: null as Sort | null,
    openId: "",
    header: null as SessionHeader | null,
    detailsError: "",
    confirming: "",
    busy: false,
    columns: COLUMNS,

    get shown() {
      return sortRows(filterRows(this.rows, this.filter), COLUMNS, this.sort);
    },
    get summary() {
      const inDataset = this.rows.filter((row) => row.in_dataset).length;
      return `${this.shown.length} of ${this.rows.length} sessions, ${inDataset} in the dataset`;
    },
    get tiles() {
      return tiles(this.rows);
    },
    get totalsLabel() {
      return totalsText(this.rows);
    },

    async init() {
      this.$watch("reloaded", () => void this.refresh());
      await this.refresh();
    },
    async refresh() {
      try {
        this.rows = await listSessions();
        this.error = "";
      } catch (error) {
        this.error = errorText(error);
      }
      this.loading = false;
    },
    sortBy(key: string) {
      this.sort = clickHeader(this.sort, key);
    },
    arrow(key: string) {
      return sortArrow(this.sort, key);
    },
    async toggle(row: SessionRow) {
      this.header = null;
      this.detailsError = "";
      this.confirming = "";
      if (this.openId === row.session_id) {
        this.openId = "";
        return;
      }
      this.openId = row.session_id;
      try {
        const header = await getSession(row.session_id);
        if (this.openId === row.session_id) this.header = header;
      } catch (error) {
        if (this.openId === row.session_id) this.detailsError = errorText(error);
      }
    },
    /** Exclude the session or include it again after asking for a note, then read the index and the open details again. */
    async changeExclusion(row: SessionRow) {
      this.busy = true;
      try {
        const saved = await askAndChange(row.session_id, !row.excluded, async (note) => Workspace.exclude(row.session_id, !row.excluded, note, { ...(await settingsStore().load()) }));
        if (!saved) return;
        this.rows = await listSessions();
        if (this.openId === row.session_id) this.header = await getSession(row.session_id);
      } catch (error) {
        toast.error(errorText(error));
      } finally {
        this.busy = false;
      }
    },
    facts(row: SessionRow) {
      return sessionFacts(row, this.header);
    },
    reviewOf: reviewText,
    titleOf: rowTitle,
    blockText,
    /** What the blocks listed are: those of the saved review when there is one, else the ones the rules cut. */
    blocksNote() {
      const { header } = this;
      if (!header) return "";
      return `${counted(header.n_initial_blocks, "block")} cut by the rules, ${header.review ? "the list is the saved review's" : "not reviewed yet"}`;
    },
    /** Open the session in the replay, asking first when the session open there has edits that are not saved. */
    openInReplay(row: SessionRow, drop = false) {
      const unsaved = Workspace.unsavedWhenOpening(row.session_id);
      if (unsaved && !drop) {
        this.confirming = unsaved.header.session_id;
        return;
      }
      this.confirming = "";
      healthStore().openSession(row.session_id);
      toast.success(`Opened ${row.session_id} in the replay`);
      location.hash = REPLAY_HASH;
    },
  }));
}

export const incomingPage: Page = {
  id: "incoming",
  title: "Incoming",
  html: incomingRoot,
  register: registerIncoming,
};
