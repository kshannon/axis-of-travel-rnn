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

// The data path first, with the pages it passes through in the order a person walks them. Environments and About sit beside the path.
const FLOW: readonly (readonly [string, boolean])[] = [
  ["Lab files", false], ["Converter", false], ["Transformed folder", false],
  ["Incoming", true], ["Settings", true], ["Replay", true], ["Blocks", true], ["Windows", true], ["Outgoing", true],
  ["Processed folder", false], ["RNN project", false],
];
const BESIDE: readonly string[] = ["Environments", "About"];

const flowLine = `
  <ol class="flex flex-wrap items-center gap-x-1.5 gap-y-1.5 text-xs">${FLOW.map(([name, inTool], index) => `
    <li class="flex items-center gap-1.5">${index ? `<span class="text-muted">&rarr;</span>` : ""}<span class="${inTool ? CHIP_ACCENT : CHIP_MUTED}">${name}</span></li>`).join("")}
  </ol>
  <p class="flex flex-wrap items-center gap-1.5 text-xs text-muted">Beside the path: ${BESIDE.map((name) => `<span class="${CHIP_ACCENT}">${name}</span>`).join(" ")}
    (the registration each built session was given, and this guide)</p>`;

const keys = `
  <dl class="mt-1 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1">${KEYS.map(({ keys: pressed, action }) => `
    <dt><kbd class="${KBD}" title="press ${pressed}: ${action}">${pressed}</kbd></dt><dd>${action}</dd>`).join("")}
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
      ${step(`Check what is read and find a session on ${link("incoming", "Incoming")}`,
        `${lead("Do:")} open Incoming. The strip at the top gives where the lab data and the environment geometry are read from and the config file that names them, each with ok or problem and any problem found under it. To change a folder, edit the config file and reload the config file, which reads it again and checks the folders. Below it the sessions: click a header to sort, type in the filter box to find a session or a rat, click a row to see its epochs, blocks and review, then press Open in replay. The sessions in the dataset come first, those still to review before those reviewed.`,
        `${lead("Look for:")} ok on the strip and a session count you expect. A problem names its cause, and any page that needs a folder shows it with a link to Incoming, or to Outgoing for the processed folder. The tiles over the table count the sessions in the dataset, reviewed, excluded, the blocks confirmed, the hours confirmed per kind and the blocks built. A session the tool cannot work with (no frames, or no arena or track epoch under baseline) is greyed and its details say why. Confirmed blocks and Built blocks tell what its review kept and what is built on disk, and Reviewed says by whom and when. If the session open in Replay has edits that are not saved, you are asked before they are dropped. The incoming data format is folded at the bottom: every file and column of the transformed folder the tool reads.`,
        `${lead("Excluded")} shows the sessions you left out. No rule leaves a session out because of its group or protocol, that is your decision: Exclude on a row's details asks for a short note and clears the session's built blocks at once, Include takes it back and leaves the session to build again. The lab's annotations file may mark a session excluded, that shows as a note and is not applied.`)}
      ${step(`Choose the window settings on ${link("settings", "Settings")}`,
        `${lead("Do:")} set the seven window settings: window, stride, burn-in and horizon in seconds, the training rate, the least measured heading share, and the least complete trips on a track block. Each has a line saying what it protects and its default beside it. The API checks a change at once, and the settings become the ones in use on every page, so Replay counts windows at them too. They start from the selection when there is one, else from the defaults, and Reset to the defaults puts them back. The defaults are fine for the first review.`,
        `${lead("Look for:")} the sentence under the fields, which spells out what the verdicts are tested at. Judge the settings on Blocks and Windows, then come back and press ${lead("Select these settings")} when they suit. It writes ${code("windows.json")} whole, the toast names it and whether it replaced one, and the line under the button says which settings are selected and how many blocks and windows they gave. It is refused while nothing is built.`,
        `The ${lead("Rules")} card below lists the engine's rules, read only, each with its value and meaning (the pause and jump sizes, the minimum block length, the heading fill and so on). They are fixed in the engine. Changing one is a code change, and a Rebuild all on Outgoing is what makes it reach what is already built.`)}
      ${step(`Review the session in ${link("replay", "Replay")}`,
        `${lead("Do:")} Replay plays the session on a map in metres and over a timeline that shows where the rules cut it (pauses, gaps, jumps, epoch bounds) and the blocks that remain. Press space to play, click a lane to put the cursor there, click a block bar to select a block, use the wheel to zoom and drag to pan. The checkboxes along the bottom of the timeline switch its layers on and off (hover one for what it means and the number of its rule), the checkboxes under the map title switch the map's layers, and the ? buttons explain the map and the timeline.`,
        `Every block is a card with its status and its window count and verdict at the settings in use. The status is auto (automatically derived, not looked at yet), confirmed (accepted by you), edited (moved, split, cut or made by you, not accepted yet) or dropped. Decide each block with the buttons in the row above the lanes:
          ${list([
            "Accept approves a block, an automatic block as drawn and an edited block after you changed it. Accept all approves every automatic and edited block at once. An accepted block stays accepted until Undo takes the accept back. Reject removes one.",
            "Start here and End here move the selected block's edge to the cursor. Split here cuts it in two.",
            "Mark in and Mark out set a range, New block from marks makes a block of it.",
            "Split here makes two blocks of one, Cut marks out removes the marked range from every block it touches, such as a jump or a short tracking loss in the middle of a block, and a piece left under 10 s is dropped and says so in its note.",
            "Flag run marks the run under the cursor as suspect, press it again to take the flag back. Notes are free text on the session.",
            "Undo takes back the last edit, Reset drops them all so the blocks are automatic again.",
          ])}`,
        `${lead("Look for:")} anything you would not train on inside a block, such as a pause, a jump or a long stretch where the heading is lost (the layers show where). A block with no window at the settings in use is dimmed. When the server refuses an edit it says why and changes nothing: the edit would overlap a block you keep, leave a kept block under the minimum length, reach outside its epoch, or change a block you removed. Edits and previews write nothing.`,
        `${lead("Exclude or Include")} sits beside Save blocks too. Excluding a session is your decision and not a rule: it keeps its review and your note, clears its built blocks at once, Save blocks is disabled until you include it, and Rebuild all builds no blocks for it.`,
        `${lead("Save blocks")} is refused until every kept block is accepted: an automatic block as drawn and an edited block after you changed it, and Accept all does both at once. A removed block needs no Accept. It writes the review (${code(SID)}, whole) and then builds the session's blocks. The toast names the review file and whether it replaced one, and warns if the build failed or a block failed a check. The next session still to review then opens. A saved session loads again with its review.`,
        `${lead("Keys:")}${keys}`)}
      ${step(`Judge readiness on ${link("blocks", "Blocks")}`,
        `${lead("Do:")} read the line at the top, it says which settings the verdicts are judged at, and a link takes you to Settings to change them. The dataset is the real one for now.`,
        `${lead("Look for:")} the totals, then the index. Each block has a window count and a verdict, ok or trouble with every rule it breaks, each reason naming the setting that decides it (no window of the window plus horizon fits in the block, head dir measured on too little of the block's frames, too few complete trips in a track block). Built with says when a block's session was built at other settings than the ones judged at. That changes only the counts and verdicts recorded at the build, never the blocks. A click on a row compares the two sets of settings, and Open plays the block in metres over its environment.`)}
      ${step(`Step through the windows on ${link("windows", "Windows")}`,
        `${lead("Do:")} from an open block, press Step through its windows. One window shows at a time. Previous and Next (the left and right keys) or a window number move through them, and the map and the lanes mark its burn-in, the window and its horizon.`,
        `${lead("Look for:")} the verdict of each window and its checks: finite position, measured heading, trips, burn-in and horizon. A window in trouble is red and says why. Use this to understand a block that fails. The settings are changed on Settings.`)}
      ${step(`Check what is built and hand over the export on ${link("outgoing", "Outgoing")}`,
        `${lead("Do:")} open Outgoing. The Write path card gives where the blocks are written, its status, how many reviews, blocks and built sessions it holds and when it last changed. The Selected for export card names the settings in ${code("windows.json")}, which are chosen on Settings. The Built card lists each session with the blocks built, those that failed, whether you excluded it, the settings it was built with and when. A row opens to the blocks that failed with their problems and the settings in use beside the ones it was built with. A reviewed session with no build says why.`,
        `${lead("Look for:")} counts that match what you reviewed, no failed blocks, and Built with in the warning colour when a session was built at other settings than the ones in use. The processed folder does not exist before your first save, which is fine. A problem names its cause. The outgoing data format is folded at the bottom: every file and column the tool writes.`,
        `${lead("Rebuild all")} is on the Built card. After a confirmation it builds the blocks of every reviewed session again from its saved review. Use it after a rule or setting change that should reach what is already built, not to start. It builds at the settings selected for export when there are some, else at the settings in use, and it never changes a review.`,
        `${lead("The export")} needs nothing to press. A separate RNN project reads the processed folder as files (${code("blocks/*.parquet")}, ${code("blocks.csv")}, ${code("metadata/")} and ${code("windows.json")}) and cuts the windows itself as windows.json says, so windows are never stored here. Heading, phase and trip are there for validation and analysis, and must not reach the network's inputs.`)}
      ${step(`Check the registrations on ${link("environments", "Environments")}`,
        `${lead("Do:")} open Environments. Each environment is drawn at one scale with the parameters of its config, and under it every built session registered in it, with the scale, rotation, LED separation and LED offset its build gave it. Click a row for the rest. The page only reads, nothing here changes a build.`,
        `${lead("Look for:")} the sessions of an environment agreeing in scale and rotation, within the ranges the line over the table gives, and the warnings chip of a session. A chip above zero lists what the build warned about in the row's details.`)}
      ${step(`Read how it works on ${link("about", "About")}`,
        `${lead("Do:")} open About for what the tool is and the rules it follows, this guide, and what each action writes. Under the hood lists the internal routes the browser uses, a cheat sheet of how the tool works and not a public API.`)}
    </ol>
  </div>`;

const ACTIONS: readonly (readonly [action: string, page: string, writes: string])[] = [
  ["Save blocks", "Replay",
    `${code(SID)} whole. Then the session's build: ${code(BID)} for each block, the session's rows of ${code("blocks.csv")} replaced together, and ${code("metadata/&lt;session_id&gt;.json")} whole. A failed build leaves the previous one in place.`],
  ["Exclude or Include", "Incoming, Replay",
    `${code(SID)} whole, with the excluded flag, who set it and when, and the note added to the session's notes. The reviewer and the review time are not changed. Excluding then builds the session with no blocks, so its blocks and metadata are replaced at once. Including writes the review only and the session builds again at your next Save blocks or Rebuild all. When the review only recorded the exclusion, including removes the file and the session's build, leaving the session as before.`],
  ["Rebuild all", "Outgoing",
    `The same build for every session that has a review, from the review as saved. The review files are not touched. A session you excluded is written with no blocks, and a review of a session the tool cannot work with is skipped.`],
  ["Select these settings", "Settings", `${code("windows.json")} whole: the settings, the totals at them, when and by whom.`],
  ["Reload", "Incoming", "Nothing. It reads the config file and the folders again."],
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
