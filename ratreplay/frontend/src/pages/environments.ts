import Alpine from "alpinejs";
import { errorText, getEnvironments } from "../api/client";
import type { EnvironmentEntry, RegisteredSession } from "../api/types";
import type { Extent } from "../draw/map";
import { folderPage } from "../ui/gate";
import { clickHeader, sortArrow, sortRows } from "../ui/table";
import type { Sort } from "../ui/table";
import { GeometryView } from "./environments-draw";
import { environmentsRoot } from "./environments-html";
import { COLUMNS, paramFacts, rangesLine, registrationFacts, rowId, rowTitle, sharedExtent, SORTABLE, warningsText } from "./environments-view";
import type { Page } from "./page";

function registerEnvironments(): void {
  Alpine.data("environmentsPage", () => {
    // The drawings are plain objects, only the environments go to Alpine.
    const views: GeometryView[] = [];
    let extent!: Extent;

    return {
      loading: true,
      error: "",
      environments: [] as EnvironmentEntry[],

      async init() {
        this.$watch("$store.shell.dark", () => views.forEach((view) => view.refresh()));
        try {
          const found = await getEnvironments();
          extent = sharedExtent(found.map((environment) => environment.geometry));
          this.environments = found;
        } catch (error) {
          this.error = errorText(error);
        }
        this.loading = false;
      },

      destroy() {
        views.forEach((view) => view.destroy());
      },

      /** Draw an environment's geometry into its host element, once it is in the page. */
      draw(host: HTMLElement, environment: EnvironmentEntry) {
        views.push(new GeometryView(host, environment.geometry, extent));
      },
    };
  });

  // One table per environment card, with its own sort and open row.
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
