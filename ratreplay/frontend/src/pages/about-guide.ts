import { KEYS } from "../ui/keys";
import { CHIP_ACCENT, CHIP_MUTED, KBD } from "../ui/style";

// The text of the About page's guide. Paths in the processed folder are written as the files hold them.
const SID = "review/&lt;session_id&gt;.json";
const BID = "blocks/&lt;block_id&gt;.parquet";

const code = (text: string) => `<code class="font-mono text-xs">${text}</code>`;
const link = (page: string, text: string) => `<a href="#/${page}" class="text-accent underline">${text}</a>`;
const lead = (text: string) => `<span class="font-medium">${text}</span>`;
const list = (items: string[]) => `<ul class="list-disc space-y-1 pl-5">${items.map((item) => `<li>${item}</li>`).join("")}</ul>`;

const RULES = [
  "It never edits the lab data and never removes behavior from it. The transformed folder is only read.",
  "A review is the only thing a person writes. The blocks are built from it.",
  "The science is in the backend: the cuts, the heading fills, the window counts and the verdicts. The browser draws and takes your clicks.",
  "It listens on localhost only. The data never leaves this machine.",
  "The window settings travel with every call. They are recorded in a session's metadata when its blocks are built, and in windows.json when you select them for export.",
];

export const whatIsBody = `
  <div class="flex flex-col gap-3 text-sm leading-5">
    <p>
      RatReplay turns the lab's transformed rat recordings into training ready trajectory blocks. You replay each session, decide
      which stretches to keep, and save. Saving writes your review and builds the blocks, in metres at 60 Hz, with trip and phase labels.
    </p>
    <p>
      The blocks feed a separate RNN project that asks whether an axis of travel representation emerges in a network trained only
      to predict future position. So the blocks carry heading and labels for checking the result, and nothing that encodes axis of
      travel may reach training. Training is not done here, the RNN project reads the files.
    </p>
    <h3 class="font-medium">The rules it follows</h3>
    ${list(RULES)}
  </div>`;

const FLOW: readonly (readonly [string, boolean])[] = [
  ["Lab files", false], ["Converter", false], ["Transformed folder", false],
  ["Data", true], ["Sessions", true], ["Replay", true], ["Blocks", true], ["Windows", true],
  ["Processed folder", false], ["RNN project", false],
];

const flowLine = `
  <ol class="flex flex-wrap items-center gap-x-1.5 gap-y-1.5 text-xs">${FLOW.map(([name, inTool], index) => `
    <li class="flex items-center gap-1.5">${index ? `<span class="text-muted">&rarr;</span>` : ""}<span class="${inTool ? CHIP_ACCENT : CHIP_MUTED}">${name}</span></li>`).join("")}
  </ol>`;

const keys = `
  <dl class="mt-1 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1">${KEYS.map(({ keys: pressed, action }) => `
    <dt><kbd class="${KBD}">${pressed}</kbd></dt><dd>${action}</dd>`).join("")}
  </dl>
  <p class="mt-1 text-xs text-muted">On the Windows page left and right step a window. Everything else is a button or a chip.</p>`;

const step = (title: string, ...parts: string[]) => `
  <li class="pl-1">
    <h3 class="font-medium">${title}</h3>
    <div class="mt-1 flex flex-col gap-1.5">${parts.map((part) => `<div>${part}</div>`).join("")}</div>
  </li>`;

export const processBody = `
  <div class="flex flex-col gap-3 text-sm leading-6">
    <p>The data takes this path. The steps below follow it, in order the first time. Each says what to do and what to look for.</p>
    ${flowLine}
    <ol class="flex list-decimal flex-col gap-4 pl-6 marker:font-medium marker:text-accent">
      ${step("Convert the lab data (outside the tool)",
        `${lead("Do:")} run the converter, ${code("pixi run transform-lab-data")} (the root README has the steps). RatReplay never runs it and never changes its output. Run it again only when the lab files change.`,
        `${lead("Look for:")} a transformed folder with sessions.csv, epochs.csv, runs.csv, a frames file for each session and manifest.json. The frames are at 60 Hz in pixels.`)}
      ${step(`Check the folders on ${link("data", "Data")}`,
        `${lead("Do:")} open Data. Three cards show the transformed folder, the processed folder and the environments, each with its path, its status, every problem found, its counts and the times it changed. The config file is named at the bottom. To change a folder, edit that file and press Reload, which reads it again and checks the folders.`,
        `${lead("Look for:")} ok on all three cards and counts that match what you expect. The processed folder does not exist before your first save, which is fine. A problem names its cause, and any page that needs that folder shows it with a link back here. The Data format card lists every file and column the tool reads and writes.`,
        `${lead("Rebuild all")} is on the processed card. After a confirmation it builds the blocks of every reviewed session again from its saved review. Use it after a rule or setting change that should reach what is already built, not to start. It builds at the settings selected for export when there are some, else at the settings in use, and it never changes a review.`)}
      ${step(`Find a session on ${link("sessions", "Sessions")}`,
        `${lead("Do:")} click a header to sort, type in the filter box to find a session or a rat, click a row to see its epochs, blocks and review, then press Open in replay. The sessions in the dataset come first, those still to review before those reviewed.`,
        `${lead("Look for:")} In dataset. A session the tool cannot work with (no frames, or no arena or track epoch under baseline) is greyed and its details say why. Confirmed blocks and Built blocks tell what its review kept and what is built on disk, and Reviewed says by whom and when. The line above the table counts the sessions reviewed and the hours confirmed. If the session open in Replay has edits that are not saved, you are asked before they are dropped.`,
        `${lead("Excluded")} shows the sessions you left out. No rule leaves a session out because of its group or protocol, that is your decision: Exclude on a row's details asks for a short note and clears the session's built blocks at once, Include takes it back and leaves the session to build again. The lab's annotations file may mark a session excluded, that shows as a note and is not applied.`)}
      ${step(`Review the session in ${link("replay", "Replay")}`,
        `${lead("Do:")} Replay plays the session on a map in metres and over a timeline that shows where the rules cut it (pauses, gaps, jumps, epoch bounds) and the blocks that remain. Press space to play, click a lane to put the cursor there, click a block bar to select a block, use the wheel to zoom and drag to pan. The chips above the timeline switch layers on and off, and the ? buttons explain the map and the timeline.`,
        `Every block is a card with its status and its window count and verdict at the settings in use. The status is auto (cut by the rules, not looked at yet), confirmed, edited (moved, split or made by you) or dropped. Decide each block:
          ${list([
            "Accept keeps a block as it is, Accept all keeps every block, Reject removes one.",
            "Start to cursor and End to cursor move the selected block's edge to the cursor. Split at cursor cuts it in two.",
            "Mark in and Mark out set a range, New block from marks makes a block of it.",
            "Flag run marks the run under the cursor as suspect, press it again to take the flag back. Notes are free text on the session.",
            "Undo takes back the last edit, Reset to automatic drops them all.",
          ])}`,
        `${lead("Look for:")} anything you would not train on inside a block, such as a pause, a jump or a long stretch where the heading is lost (the layer chips show where). A block with no window at the settings in use is dimmed. When the server refuses an edit it says why and changes nothing: the edit would overlap a block you keep, leave a kept block under the minimum length, reach outside its epoch, or change a block you removed. Edits and previews write nothing.`,
        `${lead("Exclude or Include")} sits beside Save blocks too. Excluding a session is your decision and not a rule: it keeps its review and your note, clears its built blocks at once, Save blocks is disabled until you include it, and Rebuild all builds no blocks for it.`,
        `${lead("Save blocks")} is refused while any block is still auto, so accept or reject each one first. It writes the review (${code(SID)}, whole) and then builds the session's blocks. The toast names the review file and whether it replaced one, and warns if the build failed or a block failed a check. The next session still to review then opens. A saved session loads again with its review.`,
        `${lead("Keys:")}${keys}`)}
      ${step(`Judge readiness on ${link("blocks", "Blocks")}`,
        `${lead("Do:")} set the window settings you want to try: window, stride, burn-in and horizon in seconds, the training rate, the least measured heading share, and the least complete trips on a track block. Hover a field for what it protects. They start from the selection when there is one, and Replay counts windows at the same settings.`,
        `${lead("Look for:")} the totals, then the index. Each block has a window count and a verdict, ok or trouble with every rule it breaks, each reason naming the setting that decides it (no window of the window plus horizon fits in the block, head dir measured on too little of the block's frames, too few complete trips in a track block). Built with says when a block's session was built at other settings than the ones you are trying. That changes only the counts and verdicts recorded at the build, never the blocks. A click on a row compares the two sets of settings, and Open plays the block in metres over its environment.`,
        `When the settings suit, press ${lead("Select these settings")}. It writes ${code("windows.json")} whole, and the toast names it and whether it replaced one. It is refused while nothing is built.`)}
      ${step(`Step through the windows on ${link("windows", "Windows")}`,
        `${lead("Do:")} from an open block, press Step through its windows. One window shows at a time. Previous and Next (the left and right keys) or a window number move through them, and the map and the lanes mark its burn-in, the window and its horizon.`,
        `${lead("Look for:")} the verdict of each window and its checks: finite position, measured heading, trips, burn-in and horizon. A window in trouble is red and says why. Use this to understand a block that fails. The settings are changed on Blocks.`)}
      ${step("Hand over the export",
        `Nothing to press. A separate RNN project reads the processed folder as files (${code("blocks/*.parquet")}, ${code("blocks.csv")}, ${code("metadata/")} and ${code("windows.json")}) and cuts the windows itself as windows.json says, so windows are never stored here. Heading, phase and trip are there for validation and analysis, and must not reach the network's inputs.`)}
    </ol>
  </div>`;

const ACTIONS: readonly (readonly [action: string, page: string, writes: string])[] = [
  ["Save blocks", "Replay",
    `${code(SID)} whole. Then the session's build: ${code(BID)} for each block, the session's rows of ${code("blocks.csv")} replaced together, and ${code("metadata/&lt;session_id&gt;.json")} whole. A failed build leaves the previous one in place.`],
  ["Exclude or Include", "Sessions, Replay",
    `${code(SID)} whole, with the excluded flag, who set it and when, and the note added to the session's notes. The reviewer and the review time are not changed. Excluding then builds the session with no blocks, so its blocks and metadata are replaced at once. Including writes the review only and the session builds again at your next Save blocks or Rebuild all. When the review only recorded the exclusion, including removes the file and the session's build, leaving the session as before.`],
  ["Rebuild all", "Data",
    `The same build for every session that has a review, from the review as saved. The review files are not touched. A session you excluded is written with no blocks, and a review of a session the tool cannot work with is skipped.`],
  ["Select these settings", "Blocks", `${code("windows.json")} whole: the settings, the totals at them, when and by whom.`],
  ["Reload", "Data", "Nothing. It reads the config file and the folders again."],
  ["Everything else", "any page",
    "Nothing. Edits, notes, marks and the settings being tried stay in the browser until you press Save blocks or Select these settings."],
];

export const actionsBody = `
  <div class="flex flex-col gap-3 text-sm leading-5">
    <p>Every file is written whole, replacing the earlier one. Nothing is appended. The transformed folder is only read.</p>
    <dl class="flex flex-col gap-3">${ACTIONS.map(([action, page, writes]) => `
      <div>
        <dt class="flex items-center gap-2"><span class="font-medium">${action}</span><span class="${CHIP_MUTED}">${page}</span></dt>
        <dd class="text-muted">${writes}</dd>
      </div>`).join("")}
    </dl>
    <p>The browser keeps only the theme and the open session.</p>
  </div>`;

export const linksBody = `
  <ul class="text-sm leading-5">
    <li>${code("ratreplay/README.md")} how to run it</li>
    <li>${code("ratreplay/docs/architecture.md")} the design</li>
  </ul>`;
