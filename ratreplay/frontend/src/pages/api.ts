import { card, pageGrid } from "../ui/card";
import type { Page } from "./page";

export const apiPage: Page = {
  id: "api",
  title: "API",
  html: pageGrid(card("API", `<p class="text-muted">The data format contract and the API schema.</p>`)),
};
