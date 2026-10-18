import { expect, test } from "@playwright/test";
import { countTile, environmentPixels, nextHealth, resetProcessed, S1, S6, toast, WALL_PIXELS } from "./synthetic";

test.afterEach(resetProcessed);

// The story a person lives on the synthetic data: the folders are ok, a session is chosen and reviewed, the review is saved and found saved again.
// Nothing waits on a timer: each step waits for what it expects to see, and a save for the toast it ends in.
test("read the folders, review a session, refuse a split, split the track block, save, and find the blocks saved", async ({ page }) => {
  const goTo = (name: string) => page.getByRole("navigation").getByRole("link", { name, exact: true }).click();
  const cards = page.getByRole("article");
  const frame = page.getByTestId("tile-frame");
  const state = page.getByTestId("state");
  const processed = page.getByTestId("processed");

  await test.step("the Data page shows the three folders ok, with no review yet", async () => {
    await page.goto("/#/data");
    for (const folder of ["transformed", "processed", "environments"]) await expect(page.getByTestId(folder).getByText("ok", { exact: true })).toBeVisible();
    await expect(countTile(processed, "reviews")).toHaveText("0");
    await expect(countTile(processed, "blocks")).toHaveText("0");
  });

  await test.step("the Sessions page lists the dataset sessions first and opens one in the Replay", async () => {
    await goTo("Sessions");
    const rows = page.getByRole("row");
    await expect(rows).toHaveCount(7); // the header and six sessions
    await expect(rows.nth(1)).toContainText(/NS14.*yes/);
    await expect(rows.nth(2)).toContainText(/NS16.*yes/);
    await expect(rows.nth(3)).toContainText(/NS14.*rotation.*no/);
    await expect(page.getByTestId("totals")).toContainText("0 of 6 sessions reviewed, 0 blocks confirmed");
    await rows.nth(1).click();
    await page.getByRole("button", { name: "Open in replay" }).click();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await expect(frame).toHaveText("1");
  });

  await test.step("the blocks are drawn with the windows they yield at the default 40 s window", async () => {
    await expect(cards).toHaveCount(2); // the arena block and the track block
    await expect(cards.first()).toContainText("0 training windows");
    await expect(cards.first().getByTestId("verdict")).toHaveText("no window fits");
    await expect(page.getByTestId("settings")).toContainText("window 40 s, stride 10 s");
    await expect(page.getByTestId("map").locator("canvas")).toBeVisible();
    await expect(state).toHaveText("automatic");
  });

  await test.step("a split that leaves a piece under 10 s is refused and toasted with the API's reason", async () => {
    await cards.nth(1).click();
    await expect(cards.nth(1)).toHaveAttribute("aria-current", "true");
    for (let i = 0; i < 39; i++) await page.keyboard.press("Shift+ArrowRight");
    await expect(frame).toHaveText("2341"); // 4 s into the track block
    await expect.poll(() => environmentPixels(page)).toBeGreaterThan(WALL_PIXELS); // the track's walls are drawn in metres
    await page.getByRole("button", { name: "Split at cursor" }).click();
    await expect(toast(page, "a kept block must last 10 s or more")).toBeVisible();
    await expect(cards).toHaveCount(2);
  });

  await test.step("the track block splits in half at frame 2701, accept all confirms the rest", async () => {
    for (let i = 0; i < 6; i++) await page.keyboard.press("Shift+ArrowRight");
    await expect(frame).toHaveText("2701"); // the middle of the track block, the only split that leaves two blocks of 10 s
    await page.getByRole("button", { name: "Split at cursor" }).click();
    await expect(toast(page, "Added split at frame 2701")).toBeVisible();
    await expect(cards).toHaveCount(3);
    await page.getByRole("button", { name: "Accept all" }).click();
    await expect(cards.first()).toContainText("confirmed");
    await expect(cards.nth(1)).toContainText("edited");
    await expect(cards.nth(2)).toContainText("edited");
    await expect(state).toContainText("now 2 edits not saved yet");
  });

  await test.step("Save blocks names the review file and the blocks built, then opens the next session", async () => {
    await page.getByLabel("Notes on the session").fill("the whole story");
    await page.getByRole("button", { name: "Save blocks" }).click();
    const saved = toast(page, "Saved, a new file, built 3 blocks");
    await expect(saved).toBeVisible();
    await expect(saved).toContainText(`review/${S1}.json`);
    await expect(toast(page, `Opened the next session to review, ${S6}`)).toBeVisible();
    await expect(page.getByTestId("session-id")).toHaveText(S6);
  });

  await test.step("a reload shows the saved blocks", async () => {
    await goTo("Sessions");
    await expect(page.getByTestId("totals")).toContainText("1 of 6 sessions reviewed, 3 blocks confirmed");
    await page.getByLabel("Filter sessions").fill("ns14");
    await page.getByRole("row").nth(1).click();
    await page.getByRole("button", { name: "Open in replay" }).click();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await page.reload();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await expect(state).toContainText(/^saved .* by \S+, 2 edits$/);
    await expect(page.getByLabel("Notes on the session")).toHaveValue("the whole story");
    await expect(cards).toHaveCount(3);
    await expect(cards.first()).toContainText("confirmed");
    await expect(cards.nth(1)).toContainText("edited");
    await expect(cards.nth(2)).toContainText("edited");
  });

  await test.step("the Data page counts the review and the blocks built from it", async () => {
    const read = nextHealth(page);
    await goTo("Data");
    await read; // the counts are the folder's as it is now, not those the page kept from before
    await expect(countTile(processed, "reviews")).toHaveText("1");
    await expect(countTile(processed, "blocks")).toHaveText("3");
    await expect(countTile(processed, "built sessions")).toHaveText("1");
  });
});
