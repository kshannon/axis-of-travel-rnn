import { card, pageGrid } from "../ui/card";
import type { Page } from "./page";

export const blocksPage: Page = {
  id: "blocks",
  title: "Blocks",
  html: pageGrid(card("Blocks", `<p class="text-muted">A sortable index of the built blocks, and a player for one in metres.</p>`)),
};
