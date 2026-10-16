import { card, pageGrid } from "../ui/card";
import type { Page } from "./page";

export const windowsPage: Page = {
  id: "windows",
  title: "Windows",
  html: pageGrid(card("Windows", `<p class="text-muted">Step through the windows of a block, each with its checks.</p>`)),
};
