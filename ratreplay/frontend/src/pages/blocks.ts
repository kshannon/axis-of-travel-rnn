import { card, pageGrid } from "../ui/card";
import { sourceGate } from "../ui/gate";
import type { Page } from "./page";

const placeholder = `<p class="text-muted">A sortable index of the built blocks, and a player for one in metres.</p>`;

export const blocksPage: Page = {
  id: "blocks",
  title: "Blocks",
  html: pageGrid(card("Blocks", sourceGate(placeholder))),
};
