import Alpine from "alpinejs";
import { errorText, getEnvironments } from "../api/client";
import type { EnvironmentEntry, RegisteredSession } from "../api/types";
import type { Extent } from "../draw/map";
import { folderPage } from "../ui/gate";
import { belongsToTarget, commandOf } from "../ui/keys";
import { clickHeader, sortArrow, sortRows } from "../ui/table";
import type { Sort } from "../ui/table";
import { GeometryView } from "./environments-draw";
import { environmentsRoot } from "./environments-html";
import { COLUMNS, neighbour, paramFacts, rangesLine, registrationFacts, rowId, rowTitle, sharedExtent, SORTABLE, startingSelection, thumbnails, warningsText } from "./environments-view";
import type { Page } from "./page";

const SELECTED_KEY = "ratreplay-environment";

function remembered(): string | null {
  try {
    return localStorage.getItem(SELECTED_KEY);
  } catch {
    return null;
  }
}

function remember(name: string): void {
  try {
    localStorage.setItem(SELECTED_KEY, name);
  } catch {
    // The choice then lasts until the page is closed, nothing more.
  }
}

function registerEnvironments(): void {
  Alpine.data("environmentsPage", () => {
    // The drawings are plain objects, only the environments and the selection go to Alpine.
    const thumbnailViews: GeometryView[] = [];
    let largeView: GeometryView | null = null;
    let extent!: Extent;
    let stopKeys = () => {};

    return {
      loading: true,
      error: "",
      environments: [] as EnvironmentEntry[],
      selected: "",

      async init() {
        const onKey = (event: KeyboardEvent) => {
          const command = commandOf(event);
          if ((command !== "back" && command !== "forward") || belongsToTarget({ key: event.key, target: event.target as Element | null })) return;
          event.preventDefault();
          this.select(neighbour(this.environments, this.selected, command === "back" ? -1 : 1));
        };
        addEventListener("keydown", onKey);
        stopKeys = () => removeEventListener("keydown", onKey);
        this.$watch("$store.shell.dark", () => [...thumbnailViews, largeView].forEach((view) => view?.refresh()));
        try {
          const found = await getEnvironments();
          extent = sharedExtent(found.map((environment) => environment.geometry));
          this.environments = found;
          this.selected = startingSelection(found, remembered());
        } catch (error) {
          this.error = errorText(error);
        }
        this.loading = false;
      },

      destroy() {
        stopKeys();
        [...thumbnailViews, largeView].forEach((view) => view?.destroy());
      },

      get thumbs() {
        return thumbnails(this.environments, this.selected);
      },

      /** The selected environment in a list of its own, so that the large card is built again on every choice. */
      get large() {
        return this.environments.filter((environment) => environment.name === this.selected);
      },

      select(name: string) {
        if (name === this.selected) return;
        this.selected = name;
        remember(name);
        // A strip wider than the window keeps the choice in sight.
        this.$nextTick(() => this.$refs.strip.querySelector("[aria-pressed=true]")?.scrollIntoView({ block: "nearest", inline: "nearest" }));
      },

      /** Draw an environment in its thumbnail, once that is in the page, all of them at one scale. */
      drawThumbnail(host: HTMLElement, name: string) {
        const environment = this.environments.find((e) => e.name === name)!;
        thumbnailViews.push(new GeometryView(host, environment.geometry, extent));
      },

      /** Draw the selected environment as large as its host, fitted to its own extent. */
      drawLarge(host: HTMLElement, environment: EnvironmentEntry) {
        largeView?.destroy();
        largeView = new GeometryView(host, environment.geometry, sharedExtent([environment.geometry]));
      },
    };
  });

  // The table of the selected environment, with its own sort and open row.
  Alpine.data("environmentSessions", (environment: EnvironmentEntry) => ({
    columns: COLUMNS,
    sort: null as Sort | null,
    openId: "",
    params: paramFacts(environment.params),
    line: rangesLine(environment.sessions, environment.summary),
    rowId,
    rowTitle,
    warningsText,
    facts: registrationFacts,

    get shown() {
      return sortRows(environment.sessions, SORTABLE, this.sort);
    },

    sortBy(key: string) {
      this.sort = clickHeader(this.sort, key);
    },
    arrow(key: string) {
      return sortArrow(this.sort, key);
    },
    toggle(row: RegisteredSession) {
      this.openId = this.openId === rowId(row) ? "" : rowId(row);
    },
  }));
}

export const environmentsPage: Page = {
  id: "environments",
  title: "Environments",
  html: folderPage("Environments", environmentsRoot, "processed", "environments"),
  register: registerEnvironments,
};
