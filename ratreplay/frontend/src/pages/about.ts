import { card, pageGrid } from "../ui/card";
import { KBD } from "../ui/style";
import { KEYS } from "../ui/keys";
import type { Page } from "./page";

const RULES = [
  "It never edits the lab data and never removes behavior from it, the transformed folder is only read.",
  "A review is the only thing a person writes, the blocks are built from it.",
  "The cuts, heading fills and training windows come from the backend's engine, none of the science is rewritten in the browser.",
  "It listens on localhost only, the data never leaves this machine.",
];

const FILES = [
  ["review of a session", "review/&lt;session_id&gt;.json under the processed folder, overwritten whole on each save"],
  ["built blocks", "blocks/, blocks.csv and metadata/ under the processed folder, built by Save blocks and Rebuild all"],
  ["selected window settings", "windows.json in the processed folder, written by Select these settings"],
  ["theme and open session", "kept in this browser only"],
];

const intro = `
  <p class="text-sm leading-6">
    RatReplay is a review tool for rat trajectory data. It reads the transformed lab data and writes to the processed folder, the
    two that configs/local.yaml names. Replay a session and save its blocks, which writes the review and builds the blocks. Then judge
    the built blocks at window settings and select the settings for export. What it writes is plain files that other tools read.
  </p>`;

const rules = `<ul class="list-disc space-y-1.5 pl-5 text-sm leading-6">${RULES.map((rule) => `<li>${rule}</li>`).join("")}</ul>`;

const keys = `
  <table class="w-full text-sm">
    <tbody>${KEYS.map(({ keys: pressed, action }) => `
      <tr><td class="py-1 pr-4"><kbd class="${KBD}">${pressed}</kbd></td><td class="py-1">${action}</td></tr>`).join("")}
    </tbody>
  </table>
  <p class="mt-2 text-xs text-muted">Everything else is a button or a chip.</p>`;

const files = `
  <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">${FILES.map(([what, where]) => `
    <dt class="text-muted">${what}</dt><dd class="font-mono text-xs leading-5">${where}</dd>`).join("")}
  </dl>`;

const more = `
  <p class="text-sm leading-6">
    The routes and the data format are on the <a href="#/api" class="text-accent underline">API page</a>.
    The design this tool is reviewed against is in <code class="font-mono text-xs">ratreplay/docs/architecture.md</code>.
  </p>`;

export const aboutPage: Page = {
  id: "about",
  title: "About",
  html: pageGrid(
    card("What it is", intro, "col-span-7 row-span-2") +
      card("Keyboard essentials", keys, "col-span-5 row-span-3") +
      card("The rules it follows", rules, "col-span-7 row-span-3") +
      card("Where files are written", files, "col-span-5 row-span-2") +
      card("More", more, "col-span-12 row-span-1"),
  ),
};
