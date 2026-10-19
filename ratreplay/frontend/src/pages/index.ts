import type { Page } from "./page";
import { incomingPage } from "./incoming";
import { settingsPage } from "./settings";
import { replayPage } from "./replay";
import { blocksPage } from "./blocks";
import { windowsPage } from "./windows";
import { syntheticPage } from "./synthetic";
import { quizPage } from "./quiz";
import { outgoingPage } from "./outgoing";
import { environmentsPage } from "./environments";
import { aboutPage } from "./about";

/** The pages in tab order, which is the order a person walks the flow. A hash that names none of them gives the first. */
export const PAGES: readonly Page[] = [incomingPage, settingsPage, replayPage, blocksPage, windowsPage, syntheticPage, quizPage, outgoingPage, environmentsPage, aboutPage];
