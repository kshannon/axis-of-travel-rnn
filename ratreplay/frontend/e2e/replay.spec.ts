import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { baseScale, laneBands } from "../src/draw/lanes";
import { SESSION_LANES } from "../src/draw/session-scene";
import { detachAll, openReplay, PROCESSED, pageScrolls, removeReviews, removeSettings } from "./synthetic";

// S6 has two automatic blocks, an arena block over frames 301 to 1500 and a track block over 3001 to 4200, in 90 s at 60 Hz.
const S1 = "NS14_rec1_20150101_001";
const S6 = "NS16_rec6_20150106_001";
const SESSION_S = 90;

test.beforeEach(({ request }) => detachAll(request));
test.afterEach(() => {
  removeReviews();
  removeSettings();
});

test("play and pause, zoom with the buttons, select a block by its bar and accept it with enter", async ({ page, request }) => {
  await openReplay(page, request, S6);
  const frame = page.getByTestId("tile-frame");
  await expect(frame).toHaveText("1");
  expect(await pageScrolls(page)).toBe(false);

  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(frame).not.toHaveText("1");
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  const paused = await frame.innerText();
  await page.waitForTimeout(300);
  await expect(frame).toHaveText(paused);

  const shown = page.getByTestId("shown");
  await expect(shown).toHaveText("0:00 to 1:30");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(shown).not.toHaveText("0:00 to 1:30");
  await page.getByRole("button", { name: "Zoom out" }).click();
  await expect(shown).toHaveText("0:00 to 1:30");
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.getByRole("button", { name: "Zoom all" }).click();
  await expect(shown).toHaveText("0:00 to 1:30");

  const timeline = (await page.getByTestId("timeline").boundingBox())!;
  const { blocks } = laneBands(timeline.height, SESSION_LANES);
  const scale = baseScale(SESSION_S, timeline.width);
  await page.mouse.click(timeline.x + scale(15), timeline.y + (blocks.top + blocks.bottom) / 2);
  const first = page.getByRole("article").first();
  await expect(first).toHaveAttribute("aria-current", "true");
  await page.getByRole("button", { name: "Fit block" }).click();
  await expect(shown).not.toHaveText("0:00 to 1:30");

  await page.keyboard.press("Enter");
  await expect(first).toContainText("confirmed");
  await expect(page.getByRole("status").filter({ hasText: "Added accept toggle at frame 301" })).toBeVisible();
  await expect(page.getByTestId("state")).toContainText("now 1 edit not saved yet");
});

test("a range over a block is refused, over a removed block it makes a new block, undo takes it back", async ({ page, request }) => {
  await openReplay(page, request, S6);
  const cards = page.getByRole("article");
  await expect(cards).toHaveCount(2);

  const timeline = (await page.getByTestId("timeline").boundingBox())!;
  const { runs } = laneBands(timeline.height, SESSION_LANES);
  await page.mouse.click(timeline.x + baseScale(SESSION_S, timeline.width)(10), timeline.y + (runs.top + runs.bottom) / 2);
  await page.getByRole("button", { name: "Mark in" }).click();
  for (let i = 0; i < 12; i++) await page.keyboard.press("Shift+ArrowRight");
  await page.getByRole("button", { name: "Mark out" }).click();
  await expect(page.getByText(/Marked frames \d+ to \d+, 12\.\d s\./)).toBeVisible();

  await page.getByRole("button", { name: "New block from marks" }).click();
  await expect(page.getByRole("status").filter({ hasText: "cannot overlap a block that is kept" })).toBeVisible();
  await expect(cards).toHaveCount(2);

  await page.getByRole("button", { name: "Reject block 1" }).click();
  await expect(cards.first()).toContainText("dropped");
  await page.getByRole("button", { name: "New block from marks" }).click();
  await expect(cards).toHaveCount(3);
  await expect(page.getByText("No range marked.")).toBeVisible();
  await expect(cards.nth(1)).toHaveAttribute("aria-current", "true");

  await page.keyboard.press("z");
  await expect(cards).toHaveCount(2);
  await expect(page.getByRole("status").filter({ hasText: "Undid the new block over frames" })).toBeVisible();
});

test("the edges of a new block over a removed block move the new block and the removed one is saved as it was", async ({ page, request }) => {
  await openReplay(page, request, S6);
  const cards = page.getByRole("article");
  await page.getByRole("button", { name: "Reject block 1" }).click();

  const timeline = (await page.getByTestId("timeline").boundingBox())!;
  const { runs } = laneBands(timeline.height, SESSION_LANES);
  await page.mouse.click(timeline.x + baseScale(SESSION_S, timeline.width)(10), timeline.y + (runs.top + runs.bottom) / 2);
  await page.getByRole("button", { name: "Mark in" }).click();
  for (let i = 0; i < 12; i++) await page.keyboard.press("Shift+ArrowRight");
  await page.getByRole("button", { name: "Mark out" }).click();
  const marked = await page.getByText(/Marked frames \d+ to \d+/).innerText();
  const [markIn, markOut] = marked.match(/\d+/g)!.map(Number);
  await page.getByRole("button", { name: "New block from marks" }).click();
  await expect(cards).toHaveCount(3);

  const seconds = 60;
  for (let i = 0; i < 11; i++) await page.keyboard.press("Shift+ArrowLeft");
  await page.getByRole("button", { name: "Start to cursor" }).click();
  await expect(page.getByRole("status").filter({ hasText: `Added move of the start to frame ${markOut - 11 * seconds}` })).toBeVisible();
  for (let i = 0; i < 10; i++) await page.keyboard.press("Shift+ArrowRight");
  await page.getByRole("button", { name: "End to cursor" }).click();
  await expect(page.getByRole("status").filter({ hasText: `Added move of the end to frame ${markOut - seconds}` })).toBeVisible();
  await expect(cards.first()).toContainText("dropped");
  await expect(cards.nth(1)).toContainText("edited");
  await expect(cards.nth(1)).toHaveAttribute("aria-current", "true");

  await page.getByRole("button", { name: "Accept all" }).click();
  await page.getByRole("button", { name: "Save session" }).click();
  await expect(page.getByRole("status").filter({ hasText: `review/${S6}.json, a new file` })).toBeVisible();
  const saved = JSON.parse(readFileSync(join(PROCESSED, "review", `${S6}.json`), "utf8"));
  const arena = saved.blocks.filter((b: { epoch: string }) => b.epoch === "arena");
  expect(arena.map((b: { frame_start: number; frame_end: number; status: string }) => [b.frame_start, b.frame_end, b.status])).toEqual([
    [301, 1500, "dropped"], [markOut - 11 * seconds, markOut - seconds, "edited"],
  ]);
  expect(markIn).toBeLessThan(markOut);
});

test("the keys step, jump and clear, and a letter typed in the notes stays a letter", async ({ page, request }) => {
  await openReplay(page, request, S1);
  const frame = page.getByTestId("tile-frame");
  await page.keyboard.press("ArrowRight");
  await expect(frame).toHaveText("2");
  await page.keyboard.press("Shift+ArrowRight");
  await expect(frame).toHaveText("62");
  await page.keyboard.press("]");
  await expect(frame).toHaveText("2200"); // the runs of the session start at lab frames 2200, 2400, 2600 and 4000
  await page.keyboard.press("]");
  await expect(frame).toHaveText("2400");
  await page.keyboard.press("ArrowRight");
  await expect(frame).toHaveText("2401");
  await page.keyboard.press("[");
  await expect(frame).toHaveText("2400");

  const first = page.getByRole("article").first();
  await first.click();
  await expect(first).toHaveAttribute("aria-current", "true");
  await page.keyboard.press("Escape");
  await expect(first).not.toHaveAttribute("aria-current", "true");

  await page.getByRole("button", { name: "Accept all" }).click();
  await expect(page.getByTestId("state")).toContainText("1 edit");
  await page.getByLabel("Notes on the session").fill("z");
  await page.getByLabel("Notes on the session").press("z");
  await expect(page.getByLabel("Notes on the session")).toHaveValue("zz");
  await expect(page.getByTestId("state")).toContainText("1 edit");
});

test("a save is refused while a block is auto, names its file, advances to the next session and shows as saved after a reload", async ({ page, request }) => {
  await openReplay(page, request, S1);
  await page.getByRole("button", { name: "Save session" }).click();
  await expect(page.getByRole("status").filter({ hasText: "some blocks are still auto" })).toBeVisible();

  await page.getByRole("button", { name: "Accept all" }).click();
  await page.getByLabel("Notes on the session").fill("shaky tracking");
  await page.getByRole("button", { name: "Save session" }).click();
  await expect(page.getByRole("status").filter({ hasText: `review/${S1}.json, a new file` })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: `Opened the next session to review, ${S6}` })).toBeVisible();
  await expect(page.getByTestId("session-id")).toHaveText(S6);

  await page.getByRole("link", { name: "Sessions" }).click();
  await expect(page.getByTestId("totals")).toHaveText("1 of 6 sessions reviewed, 2 blocks confirmed, confirmed hours: arena 0.01, track 0.01");
  await page.getByLabel("Filter sessions").fill("ns14");
  await page.getByRole("row").nth(1).click();
  await page.getByRole("button", { name: "Open in replay" }).click();
  await expect(page.getByTestId("state")).toContainText(/^saved .* by \S+, 1 edit$/);
  await page.reload();
  await expect(page.getByTestId("session-id")).toHaveText(S1);
  await expect(page.getByTestId("state")).toContainText(/^saved .* by \S+, 1 edit$/);
  await expect(page.getByLabel("Notes on the session")).toHaveValue("shaky tracking");
  await expect(page.getByRole("article").first()).toContainText("confirmed");

  await page.getByRole("button", { name: "Save session" }).click();
  await expect(page.getByRole("status").filter({ hasText: "replacing the earlier review" })).toBeVisible();
});

test("reset to automatic clears the edits in memory and says so", async ({ page, request }) => {
  await openReplay(page, request, S6);
  await page.getByRole("button", { name: "Accept all" }).click();
  await expect(page.getByRole("article").first()).toContainText("confirmed");
  await page.getByRole("button", { name: "Reset to automatic" }).click();
  await expect(page.getByRole("status").filter({ hasText: "The edits are cleared" })).toBeVisible();
  await expect(page.getByRole("article").first()).toContainText("auto");
  await expect(page.getByTestId("state")).toHaveText("automatic");
});

test("the block cards tell the training windows at the saved settings and grey a block shorter than one window", async ({ page, request }) => {
  await openReplay(page, request, S6);
  const cards = page.getByRole("article");
  await expect(cards.first()).toContainText("shorter than one window"); // 20 s blocks under the default 40 s window

  await page.getByRole("link", { name: "Blocks", exact: true }).click();
  await page.getByLabel("window (s)").fill("5");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();
  await page.getByRole("link", { name: "Replay", exact: true }).click();
  await expect(cards.first()).toContainText("2 training windows");
  await expect(cards.first()).not.toHaveClass(/opacity-60/);
});
