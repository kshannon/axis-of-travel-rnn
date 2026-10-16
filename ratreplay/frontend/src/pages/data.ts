import { card, pageGrid } from "../ui/card";
import type { Page } from "./page";

export const dataPage: Page = {
  id: "data",
  title: "Data",
  html: pageGrid(card("Data", `<p class="text-muted">Attached sources as cards, with their counts, status and last change, and the form to attach more.</p>`)),
};
