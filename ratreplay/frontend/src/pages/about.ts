import Alpine from "alpinejs";
import { errorText, getOpenApi } from "../api/client";
import { endpoints, schemaTables } from "../api/describe";
import type { Endpoint, Table } from "../api/describe";
import { card, pageGrid } from "../ui/card";
import { BUTTON } from "../ui/style";
import { toast } from "../ui/toast";
import { actionsBody, linksBody, processBody, whatIsBody } from "./about-guide";
import { hoodBody, METHOD_COLOURS } from "./hood-html";
import type { Page } from "./page";

const hoodButton = `<button type="button" @click="showHood()" class="${BUTTON}">Under the hood</button>`;
const guideButton = `<button type="button" @click="view = 'guide'" class="${BUTTON}">Back to the guide</button>`;

const guide = pageGrid(
  card("What this is", whatIsBody, "col-span-3 row-span-6") +
    card("Process and how to use it", processBody, "col-span-6 row-span-6") +
    card("What you can do and what it writes", actionsBody, "col-span-3 row-span-5") +
    card("Links", linksBody, "col-span-3 row-span-1", hoodButton),
);

const hood = pageGrid(card("Under the hood", hoodBody, "col-span-12 row-span-6", guideButton));

function registerAbout(): void {
  Alpine.data("aboutPage", () => ({
    view: "guide" as "guide" | "hood",
    endpoints: [] as Endpoint[],
    schemas: [] as Table[],
    title: "",
    methodColour: METHOD_COLOURS,

    /** Show the routes, reading the OpenAPI document the first time. */
    async showHood() {
      this.view = "hood";
      if (this.endpoints.length) return;
      try {
        const document = await getOpenApi();
        this.endpoints = endpoints(document);
        this.schemas = schemaTables(document);
        this.title = `${document.info.title} ${document.info.version}, ${this.endpoints.length} routes`;
      } catch (error) {
        toast.error(errorText(error));
      }
    },
  }));
}

export const aboutPage: Page = {
  id: "about",
  title: "About",
  html: `
    <div x-data="aboutPage" class="h-full">
      <div x-show="view === 'guide'" class="h-full">${guide}</div>
      <div x-show="view === 'hood'" x-cloak class="h-full">${hood}</div>
    </div>`,
  register: registerAbout,
};
