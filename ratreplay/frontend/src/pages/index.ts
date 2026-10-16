import type { Page } from "./page";
import { dataPage } from "./data";
import { sessionsPage } from "./sessions";
import { replayPage } from "./replay";
import { blocksPage } from "./blocks";
import { windowsPage } from "./windows";
import { apiPage } from "./api";
import { aboutPage } from "./about";

/** The pages in tab order. */
export const PAGES: readonly Page[] = [dataPage, sessionsPage, replayPage, blocksPage, windowsPage, apiPage, aboutPage];
