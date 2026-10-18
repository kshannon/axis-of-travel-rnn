import { expect, test } from "@playwright/test";
import { goTo, resetProcessed, S1, S1_TRACK, S6, S6_TRACK, saveThroughApi, toast } from "./synthetic";

// The three blocks of S1 and S6 are built at the default settings before the story starts, without the Replay page.
test.beforeEach(async ({ request }) => {
  await saveThroughApi(request, S1);
  await saveThroughApi(request, S6);
});

test.afterEach(resetProcessed);

// The story a person lives to choose the settings: the defaults on Settings, the verdicts at a shorter window on Blocks, a block's windows, the selection back on Settings.
// Nothing waits on a timer: each step waits for what it expects to see.
test("set a 5 s window, read the verdicts of the built blocks, step the windows of a block, select the settings", async ({ page }) => {
  const row = (blockId: string) => page.getByTitle(blockId);
  const window = page.getByLabel("window (s)");
  const tried = page.getByTestId("tested");
  const selected = page.getByTestId("selected");
  const judged = page.getByTestId("judged");
  const number = page.getByLabel("Window number");

  await test.step("the Settings page starts at the defaults with their hints, the sentence and the rules read only", async () => {
    await page.goto("/#/settings");
    await expect(window).toHaveValue("40");
    await expect(page.getByText("The slice of a block the network sees.")).toBeVisible();
    await expect(tried).toContainText("Verdicts at a 40 s window");
    await expect(selected).toHaveText("No settings are selected for export yet.");
    await expect(page.getByTestId("rules")).toContainText("min_block_s");
    await expect(page.getByTestId("rules").locator("input")).toHaveCount(0);
  });

  await test.step("a 5 s window changes the sentence", async () => {
    await window.fill("5");
    await window.press("Tab");
    await expect(tried).toContainText("Verdicts at a 5 s window");
  });

  await test.step("the Blocks page judges the three built blocks at 5 s, and names the settings it judged at", async () => {
    await goTo(page, "Blocks");
    await expect(judged).toContainText("judged at: real lab blocks, 5 s window");
    await expect(page.getByRole("link", { name: "Change on the Settings page" })).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount(4); // the header and the three blocks
    await expect(row(S1_TRACK).getByRole("cell", { name: "ok", exact: true })).toBeVisible();
    await expect(row(S6_TRACK)).toContainText("trouble, 0 complete trips in this track block, under the minimum complete trips setting of 1");
    await expect(page.getByRole("row").filter({ hasText: "built at other settings" })).toHaveCount(3);
  });

  await test.step("a block opens and its windows are stepped on the Windows page, each with its own verdict", async () => {
    await page.getByRole("button", { name: `Open ${S1_TRACK}` }).click();
    await expect(page.getByTestId("block-id")).toHaveText(S1_TRACK);
    await expect(page.getByTestId("block-verdict")).toHaveText("ok");
    await page.getByRole("link", { name: "Step through its windows" }).click();
    await expect(page).toHaveURL(/#\/windows$/);
    await expect(page.getByTestId("window-count")).toHaveText("2");
    await expect(page.getByTestId("windows-ok")).toHaveText("1 of 2");
    await expect(page.getByTestId("window-verdict")).toHaveText("window ok");
    await page.getByRole("button", { name: /Next/ }).click();
    await expect(number).toHaveValue("2");
    await expect(page.getByTestId("window-verdict")).toHaveText("window trouble, head dir measured on 64% of this window, under the minimum measured heading setting of 80%");
    await page.getByRole("button", { name: /Previous/ }).click();
    await expect(number).toHaveValue("1");
    await expect(page.getByTestId("window-verdict")).toHaveText("window ok");
  });

  await test.step("back on Settings the 5 s window is still in use, and Select writes windows.json and shows the selection", async () => {
    await goTo(page, "Settings");
    await expect(window).toHaveValue("5");
    await page.getByRole("button", { name: "Select these settings" }).click();
    const saved = toast(page, "Selected these settings, a new file");
    await expect(saved).toBeVisible();
    await expect(saved).toContainText("windows.json");
    await expect(selected).toContainText("a 5 s window every 10 s");
    await expect(selected).toContainText("They gave 2 of 3 blocks ok and 4 windows in them");
  });

  await test.step("a reload reads the selection back and starts from it, and the Outgoing page shows it", async () => {
    await page.reload();
    await expect(selected).toContainText("a 5 s window every 10 s");
    await expect(window).toHaveValue("5");
    await expect(tried).toContainText("Verdicts at a 5 s window");
    await goTo(page, "Outgoing");
    await expect(selected).toContainText("a 5 s window every 10 s");
  });
});
