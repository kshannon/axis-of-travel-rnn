import { card, pageGrid } from "../ui/card";
import type { Page } from "./page";

export const aboutPage: Page = {
  id: "about",
  title: "About",
  html: pageGrid(card("About", `<p class="text-muted">What the tool is and the rules it follows.</p>`)),
};
