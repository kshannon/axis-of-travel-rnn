import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { detachAll, environmentPixels, openBlocks, openTrackBlock, pageScrolls, removeSettings, RING_PIXELS, S1_ARENA, S1_TRACK, S6_TRACK, SETTINGS_FILE, WALL_PIXELS } from "./synthetic";

test.beforeEach(({ request }) => detachAll(request));
test.afterEach(removeSettings);

const row = (page: Page, blockId: string) => page.getByTitle(blockId);

test("the index lists the blocks with their verdicts, sorts, expands a row to its facts and the totals follow", async ({ page, request }) => {
  await openBlocks(page, request);
  expect(await pageScrolls(page)).toBe(false);
  await expect(page.getByRole("row").filter({ hasText: "no window fits" })).toHaveCount(3);
  await expect(page.getByTestId("tested")).toContainText("Verdicts at a 40 s window plus a 0.5 s horizon every 10 s");
  await expect(page.getByTestId("totals")).toContainText("track");
  await expect(page.getByTestId("totals")).toContainText("overall");

  await page.getByRole("button", { name: "Session" }).click();
  await page.getByRole("button", { name: "Session" }).click();
  await expect(page.getByRole("row").nth(1)).toContainText("NS16");

  await row(page, S1_TRACK).click();
  await expect(page.getByText("kinematics version")).toBeVisible();
  await expect(page.getByText("frame scale")).toBeVisible();
  await expect(page.getByText("reviewed by")).toBeVisible();
  expect(await pageScrolls(page)).toBe(false);
});

test("a changed window setting changes the verdicts once tested, and the settings are saved to the file the pipeline reads", async ({ page, request }) => {
  await openBlocks(page, request);
  await page.getByLabel("window (s)").fill("5");
  await expect(row(page, S1_TRACK)).toContainText("no window fits"); // nothing changes until the test is run

  await page.getByRole("button", { name: "Test on all blocks" }).click();
  await expect(row(page, S1_TRACK)).not.toContainText("trouble");
  await expect(row(page, S1_ARENA)).not.toContainText("trouble");
  await expect(row(page, S6_TRACK)).toContainText("trouble, 0 complete trips under 1");
  await expect(page.getByRole("status").filter({ hasText: "Tested 3 blocks, 2 ok and 1 in trouble" })).toBeVisible();
  await expect(page.getByTestId("tested")).toContainText("Verdicts at a 5 s window");

  await page.getByLabel("min complete trips").fill("0");
  await page.getByRole("button", { name: "Test on all blocks" }).click();
  await expect(row(page, S6_TRACK)).not.toContainText("trouble");

  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByRole("status").filter({ hasText: `Saved ${SETTINGS_FILE}, a new file` })).toBeVisible();
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByRole("status").filter({ hasText: `Saved ${SETTINGS_FILE}, replacing the earlier file` })).toBeVisible();
  expect(readFileSync(SETTINGS_FILE, "utf8")).toContain("window_s: 5.0");

  await page.getByLabel("window (s)").fill("0");
  await page.getByRole("button", { name: "Test on all blocks" }).click();
  await expect(page.getByRole("status").filter({ hasText: "window_s" })).toBeVisible();
});

test("saving the settings tests at them, so the inputs and the verdicts are still those after a visit to another page", async ({ page, request }) => {
  await openBlocks(page, request);
  await page.getByLabel("window (s)").fill("5");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByTestId("tested")).toContainText("Verdicts at a 5 s window");

  await page.getByRole("link", { name: "Replay", exact: true }).click();
  await page.getByRole("link", { name: "Blocks", exact: true }).click();
  await expect(page.getByLabel("window (s)")).toHaveValue("5");
  await expect(row(page, S1_TRACK)).not.toContainText("trouble");
});

test("a block opens with the environment drawn under its path in metres, plays and shows its lanes", async ({ page, request }) => {
  await openTrackBlock(page, request);
  await expect(page.getByTestId("block-verdict")).toHaveText("ok");
  await expect(page.getByTestId("shown")).toHaveText("0:00 to 0:20");
  await expect(page.getByTestId("tile-frame")).toHaveText("2101"); // the lab frame of the block's first row
  expect(await environmentPixels(page)).toBeGreaterThan(WALL_PIXELS);
  expect(await pageScrolls(page)).toBe(false);

  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("tile-frame")).toHaveText("2102");
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(page.getByTestId("tile-frame")).not.toHaveText("2102");
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.getByTestId("shown")).not.toHaveText("0:00 to 0:20");
  await page.getByRole("button", { name: "Whole block" }).click();
  await expect(page.getByTestId("shown")).toHaveText("0:00 to 0:20");

  await page.getByRole("button", { name: "Back to the index" }).click();
  await page.getByRole("button", { name: `Open ${S1_ARENA}` }).click();
  await expect(page.getByTestId("block-id")).toHaveText(S1_ARENA);
  expect(await environmentPixels(page)).toBeGreaterThan(RING_PIXELS); // the arena's circle

  await page.getByRole("button", { name: "Back to the index" }).click();
  await page.getByRole("button", { name: `Open ${S6_TRACK}` }).click();
  await expect(page.getByTestId("block-verdict")).toHaveText("trouble, 0 complete trips under 1");
});
