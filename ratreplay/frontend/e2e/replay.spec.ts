import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { baseScale, laneBands } from "../src/draw/lanes";
import { SESSION_LANES } from "../src/draw/session-scene";
import { environmentPixels, openReplay, PROCESSED, pageScrolls, removeReviews, removeSettings, S1, S6, SESSION_S, WALL_PIXELS } from "./synthetic";

test.afterEach(() => {
  removeReviews();
  removeSettings();
});

test("play and pause, zoom with the buttons, select a block by its bar and accept it with enter", async ({ page }) => {
  await openReplay(page, S1);
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

test("a range over a block is refused, over a removed block it makes a new block, undo takes it back", async ({ page }) => {
  await openReplay(page, S1);
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

test("the edges of a new block over a removed block move the new block and the removed one is saved as it was", async ({ page }) => {
  await openReplay(page, S1);
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
  await page.getByRole("button", { name: "Save blocks" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved, a new file" }).filter({ hasText: `review/${S1}.json` })).toBeVisible();
  const saved = JSON.parse(readFileSync(join(PROCESSED, "review", `${S1}.json`), "utf8"));
  const arena = saved.blocks.filter((b: { epoch: string }) => b.epoch === "arena");
  expect(arena.map((b: { frame_start: number; frame_end: number; status: string }) => [b.frame_start, b.frame_end, b.status])).toEqual([
    [301, 1500, "dropped"], [markOut - 11 * seconds, markOut - seconds, "edited"],
  ]);
  expect(markIn).toBeLessThan(markOut);
});

test("a new block that starts on the frame of a removed block has its own card, and each card reaches its own block", async ({ page }) => {
  await openReplay(page, S1);
  const cards = page.getByRole("article");
  await page.getByRole("button", { name: "Reject block 1" }).click();

  for (let i = 0; i < 5; i++) await page.keyboard.press("Shift+ArrowRight");
  await expect(page.getByTestId("tile-frame")).toHaveText("301");
  await page.getByRole("button", { name: "Mark in" }).click();
  for (let i = 0; i < 15; i++) await page.keyboard.press("Shift+ArrowRight");
  await page.getByRole("button", { name: "Mark out" }).click();
  await page.getByRole("button", { name: "New block from marks" }).click();
  await expect(cards).toHaveCount(3);
  await expect(cards.first()).toContainText("dropped");
  await expect(cards.nth(1)).toContainText("edited");
  await expect(cards.nth(1)).toHaveAttribute("aria-current", "true");

  await page.getByRole("button", { name: "Reject block 2" }).click();
  await expect(cards.nth(1)).toContainText("dropped");
  await page.getByRole("button", { name: "Reject block 1" }).click();
  await expect(cards.first()).toContainText("edited");
  await expect(cards.nth(1)).toContainText("dropped");
});

test("the keys step, jump and clear, and a letter typed in the notes stays a letter", async ({ page }) => {
  await openReplay(page, S1);
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

test("a save is refused while a block is auto, names its file, advances to the next session and shows as saved after a reload", async ({ page }) => {
  await openReplay(page, S1);
  await page.getByRole("button", { name: "Save blocks" }).click();
  await expect(page.getByRole("status").filter({ hasText: "some blocks are still auto" })).toBeVisible();

  await page.getByRole("button", { name: "Accept all" }).click();
  await page.getByLabel("Notes on the session").fill("shaky tracking");
  await page.getByRole("button", { name: "Save blocks" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved, a new file" }).filter({ hasText: `review/${S1}.json` })).toBeVisible();
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

  await page.getByRole("button", { name: "Save blocks" }).click();
  await expect(page.getByRole("status").filter({ hasText: "replacing the earlier review" })).toBeVisible();
});

test("reset to automatic clears the edits in memory and says so", async ({ page }) => {
  await openReplay(page, S6);
  await page.getByRole("button", { name: "Accept all" }).click();
  await expect(page.getByRole("article").first()).toContainText("confirmed");
  await page.getByRole("button", { name: "Reset to automatic" }).click();
  await expect(page.getByRole("status").filter({ hasText: "The edits are cleared" })).toBeVisible();
  await expect(page.getByRole("article").first()).toContainText("auto");
  await expect(page.getByTestId("state")).toHaveText("automatic");
});

test("the block cards show the manager's window count and verdict at the settings in use, and the settings are shown", async ({ page }) => {
  await openReplay(page, S6);
  const card = page.getByRole("article").first();
  await expect(card).toContainText("0 training windows"); // 20 s blocks under the default 40 s window
  await expect(card.getByTestId("verdict")).toContainText("no window fits");
  await expect(page.getByTestId("settings")).toContainText("window 40 s, stride 10 s");
  await expect(card).toHaveClass(/opacity-60/);
});

test("the room is drawn in metres, a split changes the windows counted, a save names the review file and the blocks built, a reload shows them", async ({ page }) => {
  // The synthetic blocks last 20 s, so the settings in use are shortened to give windows: the API's defaults, read once by the page, are changed on the way.
  await page.route("**/api/format", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, settings: { ...body.settings, window_s: 5, stride_s: 5 } } });
  });
  await openReplay(page, S1);
  const cards = page.getByRole("article");
  await expect(cards.nth(1)).toContainText("3 training windows");
  await expect(page.getByTestId("notices")).toContainText("positions outside the room");
  for (let i = 0; i < 45; i++) await page.keyboard.press("Shift+ArrowRight");
  await expect(page.getByTestId("tile-frame")).toHaveText("2701"); // the middle of the track block, the only split that leaves two blocks of 10 s
  expect(await environmentPixels(page)).toBeGreaterThan(WALL_PIXELS);

  await cards.nth(1).click();
  await page.getByRole("button", { name: "Split at cursor" }).click();
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(1)).toContainText("1 training window");
  await expect(cards.nth(2)).toContainText("0 complete trips under 1");
  await expect(page.getByRole("status").filter({ hasText: "Added split at frame 2701" })).toBeVisible();

  await page.getByRole("button", { name: "Accept all" }).click();
  await page.getByRole("button", { name: "Save blocks" }).click();
  const saved = page.getByRole("status").filter({ hasText: "Saved, a new file, built 3 blocks" });
  await expect(saved).toBeVisible();
  await expect(saved).toContainText(`review/${S1}.json`);
  await expect(page.getByTestId("session-id")).toHaveText(S6);

  await openReplay(page, S1);
  await expect(page.getByTestId("state")).toContainText(/^saved .* by \S+, 2 edits$/);
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(2)).toContainText("edited");
  await expect(page.getByTestId("notices")).not.toContainText("saved blocks differ");
});

test("a session the rules leave out can be replayed but not saved, and its reason is shown", async ({ page }) => {
  await page.route(new RegExp(`/api/sessions/${S6}\\?`), async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, in_dataset: false, reason: "protocol rotation, not standard" } });
  });
  await openReplay(page, S6);
  await expect(page.getByRole("button", { name: "Save blocks" })).toBeDisabled();
  await expect(page.getByTestId("notices")).toContainText("Not in the dataset: protocol rotation, not standard");
});
