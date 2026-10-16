import { card, pageGrid } from "../ui/card";
import type { Page } from "./page";

export const sessionsPage: Page = {
  id: "sessions",
  title: "Sessions",
  html: pageGrid(card("Sessions", `<p class="text-muted">A sortable index of the sessions, a row opening into its details.</p>`)),
};
