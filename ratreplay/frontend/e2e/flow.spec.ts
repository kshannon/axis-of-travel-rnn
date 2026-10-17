import { readFileSync, realpathSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { baseScale, laneBands } from "../src/draw/lanes";
import { SESSION_LANES } from "../src/draw/session-scene";
import { PROCESSED, removeReviews, removeSettings, S1, S1_TRACK, S6, SESSION_S, SETTINGS_FILE } from "./synthetic";

test.afterEach(() => {
  removeReviews();
  removeSettings();
});

// The story a person lives on the synthetic data, from the configured folders to the windows of a block. Nothing waits on a timer:
// each step waits for what it expects to see, and a save for the toast it ends in.
/** Step the cursor one frame at a time until the lab frame tile reads the frame wanted. */
async function goToFrame(page: Page, frame: number) {
  const tile = page.getByTestId("tile-frame");
  for (let i = 0; i < 20; i++) {
    const at = Number((await tile.textContent())!.replace(/\D/g, ""));
    if (at === frame) return;
    await page.keyboard.press(at < frame ? "ArrowRight" : "ArrowLeft");
  }
  throw new Error(`could not reach frame ${frame}`);
}

test("read the data folders, review a session, test the blocks and inspect their windows", async ({ page }) => {
  test.setTimeout(60_000);
  const goTo = (name: string) => page.getByRole("navigation").getByRole("link", { name, exact: true }).click();
  const toast = (text: string) => page.getByRole("status").filter({ hasText: text });
  const cards = page.getByRole("article");
  const frame = page.getByTestId("tile-frame");
  const shown = page.getByTestId("shown");
  const processed = page.getByTestId("processed");

  await test.step("the Data page shows the two folders of the config, ok, with no review yet", async () => {
    await page.goto("/#/data");
    await expect(page.getByTestId("transformed").getByText("ok", { exact: true })).toBeVisible();
    await expect(page.getByTestId("processed").getByText("ok", { exact: true })).toBeVisible();
    await expect(processed.locator("dl > div").filter({ hasText: "reviews" }).first()).toContainText("0");
  });

  await test.step("the sessions index lists the dataset sessions first and opens one in the replay", async () => {
    await goTo("Sessions");
    const rows = page.getByRole("row");
    await expect(rows).toHaveCount(7);
    await expect(rows.nth(1)).toContainText(/NS14.*yes/);
    await expect(rows.nth(2)).toContainText(/NS16.*yes/);
    await expect(rows.nth(3)).toContainText(/NS14.*rotation.*no/);
    await rows.nth(1).click();
    await page.getByRole("button", { name: "Open in replay" }).click();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await expect(frame).toHaveText("1");
  });

  let paused = "";
  await test.step("play and pause, zoom in and back to the whole session", async () => {
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect(frame).not.toHaveText("1");
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();
    paused = await frame.innerText();

    await expect(shown).toHaveText("0:00 to 1:30");
    await page.getByRole("button", { name: "Zoom in" }).click();
    await expect(shown).not.toHaveText("0:00 to 1:30");
    await page.getByRole("button", { name: "Whole session" }).click();
    await expect(shown).toHaveText("0:00 to 1:30");
  });

  await test.step("select the arena block and accept it, the cursor stays where the pause left it", async () => {
    await cards.first().click();
    await expect(cards.first()).toHaveAttribute("aria-current", "true");
    await page.getByRole("button", { name: "Accept block 1" }).click();
    await expect(cards.first()).toContainText("confirmed");
    await expect(frame).toHaveText(paused);
  });

  await test.step("a range over the kept block is refused, over the block removed it makes a new block", async () => {
    const timeline = (await page.getByTestId("timeline").boundingBox())!;
    const { runs } = laneBands(timeline.height, SESSION_LANES);
    await page.mouse.click(timeline.x + baseScale(SESSION_S, timeline.width)(10), timeline.y + (runs.top + runs.bottom) / 2);
    await page.getByRole("button", { name: "Mark in" }).click();
    for (let i = 0; i < 12; i++) await page.keyboard.press("Shift+ArrowRight");
    await page.getByRole("button", { name: "Mark out" }).click();
    await expect(page.getByText(/Marked frames \d+ to \d+, 12\.\d s\./)).toBeVisible();
    await page.getByRole("button", { name: "New block from marks" }).click();
    await expect(toast("cannot overlap a block that is kept")).toBeVisible();

    await page.getByRole("button", { name: "Reject block 1" }).click();
    await expect(cards.first()).toContainText("dropped");
    await page.getByRole("button", { name: "New block from marks" }).click();
    await expect(cards).toHaveCount(3);
    await expect(cards.nth(1)).toHaveAttribute("aria-current", "true");
  });

  await test.step("a split that would leave a piece under the minimum is refused, the track block splits in half", async () => {
    for (let i = 0; i < 6; i++) await page.keyboard.press("Shift+ArrowLeft");
    await page.getByRole("button", { name: "Split at cursor" }).click();
    await expect(toast("must last 10 s or more")).toBeVisible();
    const timeline = (await page.getByTestId("timeline").boundingBox())!;
    const { runs } = laneBands(timeline.height, SESSION_LANES);
    await page.mouse.click(timeline.x + baseScale(SESSION_S, timeline.width)(45), timeline.y + (runs.top + runs.bottom) / 2);
    await goToFrame(page, 2701);
    await cards.nth(2).click();
    await expect(cards.nth(2)).toHaveAttribute("aria-current", "true");
    await page.getByRole("button", { name: "Split at cursor" }).click();
    await expect(cards).toHaveCount(4);
    await page.getByRole("button", { name: "Reject block 3" }).click();
    await expect(cards.nth(2)).toContainText("dropped");
    await page.keyboard.press("z");
    await expect(toast("Undid the")).toBeVisible();
    await expect(cards.nth(2)).toContainText("edited");
  });

  await test.step("accept all, then save and read the toast with the file written", async () => {
    await page.getByRole("button", { name: "Accept all" }).click();
    await expect(cards.last()).toContainText("edited");
    await expect(page.getByTestId("state")).toContainText(/now [45] edits not saved yet/);

    await page.getByLabel("Notes on the session").fill("the whole story");
    await page.getByRole("button", { name: "Save session" }).click();
    await expect(toast("Saved, a new file")).toContainText(`${realpathSync(PROCESSED)}/review/${S1}.json`);
    await expect(toast(`Opened the next session to review, ${S6}`)).toBeVisible();
    const saved = JSON.parse(readFileSync(join(PROCESSED, "review", `${S1}.json`), "utf8"));
    expect(saved.blocks.map((b: { status: string }) => b.status)).toEqual(["dropped", "edited", "edited", "edited"]);
    expect(saved.edits.length).toBeGreaterThanOrEqual(4);
  });

  await test.step("the sessions index counts the review and the replay shows it saved after a reload", async () => {
    await goTo("Sessions");
    await expect(page.getByTestId("totals")).toContainText("1 of 6 sessions reviewed, 3 blocks confirmed");
    await page.getByLabel("Filter sessions").fill("ns14");
    await page.getByRole("row").nth(1).click();
    await page.getByRole("button", { name: "Open in replay" }).click();
    const state = page.getByTestId("state");
    await expect(state).toContainText(/^saved .* by \S+, [45] edits$/);
    await page.reload();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await expect(state).toContainText(/^saved .* by \S+, [45] edits$/);
    await expect(page.getByLabel("Notes on the session")).toHaveValue("the whole story");
    await expect(cards.first()).toContainText("dropped");
  });

  await test.step("the Data page counts the review in the processed folder", async () => {
    await goTo("Data");
    await expect(processed.locator("dl > div").filter({ hasText: "reviews" }).first()).toContainText("1");
  });

  await test.step("the blocks index shows the processed dataset, a window length is tested and saved", async () => {
    await goTo("Blocks");
    await expect(page.getByRole("row")).toHaveCount(4);
    await page.getByLabel("window (s)").fill("5");
    await page.getByRole("button", { name: "Test on all blocks" }).click();
    await expect(toast("Tested 3 blocks, 2 ok and 1 in trouble")).toBeVisible();
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(toast("Saved, a new file")).toContainText(SETTINGS_FILE);
    expect(readFileSync(SETTINGS_FILE, "utf8")).toContain("window_s: 5.0");
  });

  await test.step("open a block and step through its two windows", async () => {
    await page.getByRole("button", { name: `Open ${S1_TRACK}` }).click();
    await expect(page.getByTestId("block-id")).toHaveText(S1_TRACK);
    await page.getByRole("link", { name: "Step through its windows" }).click();
    await expect(page.getByTestId("window-count")).toHaveText("2");
    await expect(page.getByTestId("window-verdict")).toHaveText("window ok");
    await page.getByRole("button", { name: /Next/ }).click();
    await expect(page.getByLabel("Window number")).toHaveValue("2");
    await expect(page.getByTestId("window-verdict")).toHaveText("window trouble");
    await page.getByRole("button", { name: /Previous/ }).click();
    await expect(page.getByLabel("Window number")).toHaveValue("1");
  });

  await test.step("the About and API pages render", async () => {
    await goTo("About");
    await expect(page.getByRole("heading", { name: "The rules it follows" })).toBeVisible();
    await goTo("API");
    await expect(page.getByText("sessions.csv", { exact: true })).toBeVisible();
  });
});
