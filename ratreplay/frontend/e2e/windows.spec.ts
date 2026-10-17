import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import { BLOCK_LANES } from "../src/draw/block-scene";
import { baseScale, laneBands } from "../src/draw/lanes";
import { detachAll, environmentPixels, openBlocks, openTrackBlock, pageScrolls, removeSettings, S1_TRACK, S6_TRACK, selectSource, WALL_PIXELS } from "./synthetic";

// At a 5 s window with the 10 s stride the 20 s track block has two windows. The first is ok. The second has the heading
// measured on 63.6% of its frames, under the 80% the settings ask for.
const BLOCK_S = 20;

test.beforeEach(({ request }) => detachAll(request));
test.afterEach(removeSettings);

/** Open the block on the Blocks page, tested at this window length when one is given, and go to its windows. */
async function openWindows(page: Page, request: APIRequestContext, blockId: string, windowS?: string): Promise<void> {
  await openBlocks(page, request);
  if (windowS) {
    await page.getByLabel("window (s)").fill(windowS);
    await page.getByRole("button", { name: "Test on all blocks" }).click();
  }
  await page.getByRole("button", { name: `Open ${blockId}` }).click();
  await expect(page.getByTestId("block-id")).toHaveText(blockId);
  await page.getByRole("link", { name: "Step through its windows" }).click();
}

test("without a block the page says so and leads to the Blocks page", async ({ page, request }) => {
  await selectSource(page, request);
  await page.goto("/#/windows");
  await page.reload();
  await expect(page.getByText("No block is open")).toBeVisible();
  await page.getByRole("link", { name: "Choose a block" }).click();
  await expect(page).toHaveURL(/#\/blocks$/);
});

test("the windows of the block opened on the Blocks page are stepped with the buttons, the keys, a jump and a click", async ({ page, request }) => {
  await openTrackBlock(page, request);
  await page.getByRole("link", { name: "Step through its windows" }).click();
  await expect(page).toHaveURL(/#\/windows$/);
  await expect(page.getByTestId("block-id")).toHaveText(S1_TRACK);
  await expect(page.getByTestId("window-count")).toHaveText("2");
  await expect(page.getByTestId("windows-ok")).toHaveText("1 of 2");
  await expect(page.getByLabel("Window number")).toHaveValue("1");
  await expect(page.getByTestId("window-verdict")).toHaveText("window ok");
  const heading = page.getByRole("listitem").filter({ hasText: "heading measured" });
  await expect(heading).toContainText("100%");
  await expect(heading).toContainText("ok");
  await expect(page.getByRole("button", { name: /Previous/ })).toBeDisabled();
  await expect(page.getByTestId("shown")).toHaveText("0:00 to 0:06");
  expect(await environmentPixels(page)).toBeGreaterThan(WALL_PIXELS);
  expect(await pageScrolls(page)).toBe(false);

  await page.getByRole("button", { name: /Next/ }).click();
  await expect(page.getByLabel("Window number")).toHaveValue("2");
  await expect(page.getByTestId("window-verdict")).toHaveText("window trouble");
  await expect(heading).toContainText("63.6%");
  await expect(heading).toContainText("trouble");
  await expect(page.getByTestId("window-span")).toHaveText("10.0 s to 15.0 s in the block, horizon to 15.5 s");
  await expect(page.getByTestId("shown")).toHaveText("0:10 to 0:16");
  await expect(page.getByRole("button", { name: /Next/ })).toBeDisabled();

  await page.keyboard.press("ArrowLeft");
  await expect(page.getByLabel("Window number")).toHaveValue("1");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByLabel("Window number")).toHaveValue("2");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByLabel("Window number")).toHaveValue("2");

  await page.getByLabel("Window number").fill("1");
  await page.getByLabel("Window number").press("Enter");
  await expect(page.getByTestId("window-verdict")).toHaveText("window ok");
  await page.getByLabel("Window number").fill("9");
  await page.getByLabel("Window number").press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "There is no window 9, the windows are numbered 1 to 2" })).toBeVisible();
  await expect(page.getByLabel("Window number")).toHaveValue("1");

  await page.getByRole("button", { name: "Whole block" }).click();
  await expect(page.getByTestId("shown")).toHaveText("0:00 to 0:20");
  const timeline = (await page.getByTestId("timeline").boundingBox())!;
  const { windows } = laneBands(timeline.height, BLOCK_LANES);
  await page.mouse.click(timeline.x + baseScale(BLOCK_S, timeline.width)(12.5), timeline.y + (windows.top + windows.bottom) / 2);
  await expect(page.getByLabel("Window number")).toHaveValue("2");
});

test("a block that yields no window says so instead of counting from one", async ({ page, request }) => {
  await openWindows(page, request, S6_TRACK); // the default 40 s window fits none of the 20 s blocks
  await expect(page.getByTestId("no-window")).toHaveText("no window fits");
  await expect(page.getByLabel("Window number")).toBeHidden();
  await expect(page.getByRole("button", { name: /Next/ })).toBeDisabled();
  await expect(page.getByTestId("block-verdict")).toHaveText("trouble, no window fits");
  expect(await pageScrolls(page)).toBe(false);
});
