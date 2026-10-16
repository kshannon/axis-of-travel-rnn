import { card, pageGrid } from "../ui/card";
import { sourceGate } from "../ui/gate";
import type { Page } from "./page";

const placeholder = `<p class="text-muted">Step through the windows of a block, each with its checks.</p>`;

export const windowsPage: Page = {
  id: "windows",
  title: "Windows",
  html: pageGrid(card("Windows", sourceGate(placeholder))),
};
