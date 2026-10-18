import { expect, test } from "@playwright/test";
import { resetProcessed, S1, S1_TRACK, S6, S6_TRACK, saveThroughApi, toast } from "./synthetic";

// The three blocks of S1 and S6 are built at the default settings before the story starts, without the Replay page.
test.beforeEach(async ({ request }) => {
  await saveThroughApi(request, S1);
  await saveThroughApi(request, S6);
});

test.afterEach(resetProcessed);

// The story a person lives to choose the settings: the verdicts at the defaults, at a shorter window, a block's windows, the selection.
// Nothing waits on a timer: each step waits for what it expects to see.
test("test the built blocks at another window, step the windows of a block, select the settings", async ({ page }) => {
  const row = (blockId: string) => page.getByTitle(blockId);
  const window = page.getByLabel("window (s)");
  const tried = page.getByTestId("tested");
  const number = page.getByLabel("Window number");

  await test.step("the Blocks page lists the three built blocks, none yields a window at the default 40 s", async () => {
    await page.goto("/#/blocks");
    await expect(page.getByRole("row")).toHaveCount(4); // the header and the three blocks
    await expect(page.getByRole("row").filter({ hasText: "trouble, no window fits" })).toHaveCount(3);
    await expect(page.getByRole("row").filter({ hasText: "as tried" })).toHaveCount(3);
    await expect(tried).toContainText("Verdicts at a 40 s window");
    await expect(page.getByTestId("selected")).toHaveText("No settings are selected for export yet.");
  });

  await test.step("a 5 s window changes the verdicts and marks the sessions as built at other settings", async () => {
    await window.fill("5");
    await window.press("Tab");
    await expect(tried).toContainText("Verdicts at a 5 s window");
    await expect(row(S1_TRACK).getByRole("cell", { name: "ok", exact: true })).toBeVisible();
    await expect(row(S6_TRACK)).toContainText("trouble, 0 complete trips under 1");
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
    await expect(page.getByTestId("window-verdict")).toHaveText("window trouble, measured heading 64% under 80%");
    await page.getByRole("button", { name: /Previous/ }).click();
    await expect(number).toHaveValue("1");
    await expect(page.getByTestId("window-verdict")).toHaveText("window ok");
  });

  await test.step("Select these settings writes windows.json and the selection is shown", async () => {
    await page.getByRole("navigation").getByRole("link", { name: "Blocks", exact: true }).click();
    await page.getByRole("button", { name: "Back to the index" }).click();
    await page.getByRole("button", { name: "Select these settings" }).click();
    const selected = toast(page, "Selected these settings, a new file");
    await expect(selected).toBeVisible();
    await expect(selected).toContainText("windows.json");
    await expect(page.getByTestId("selected")).toContainText("a 5 s window every 10 s");
    await expect(page.getByTestId("selected")).toContainText("They gave 2 of 3 blocks ok and 4 windows in them");
  });

  await test.step("a reload reads the selection back and starts from it", async () => {
    await page.reload();
    await expect(page.getByTestId("selected")).toContainText("a 5 s window every 10 s");
    await expect(window).toHaveValue("5");
    await expect(tried).toContainText("Verdicts at a 5 s window");
  });
});
