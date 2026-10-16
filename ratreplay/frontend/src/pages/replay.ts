import { card, pageGrid } from "../ui/card";
import type { Page } from "./page";

export const replayPage: Page = {
  id: "replay",
  title: "Replay",
  html: pageGrid(card("Replay", `<p class="text-muted">The session review: the map, the playback, the timeline and the block cards.</p>`)),
};
