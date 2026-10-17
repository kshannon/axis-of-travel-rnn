import { readFileSync, realpathSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { baseScale, laneBands } from "../src/draw/lanes";
import { SESSION_LANES } from "../src/draw/session-scene";
import { detachAll, PROCESSED, removeReviews, removeSettings, S1, S1_TRACK, S6, SESSION_S, SETTINGS_FILE, TRANSFORMED } from "./synthetic";

test.beforeEach(({ request }) => detachAll(request));
test.afterEach(() => {
  removeReviews();
  removeSettings();
});

// The story a person lives on the synthetic data, from no source to the windows of a block. Nothing waits on a timer:
// each step waits for what it expects to see, and a save for the toast it ends in.
test("attach the data, review a session, test the blocks and inspect their windows", async ({ page }) => {
  test.setTimeout(60_000);
  const goTo = (name: string) => page.getByRole("navigation").getByRole("link", { name, exact: true }).click();
  const toast = (text: string) => page.getByRole("status").filter({ hasText: text });
  const cards = page.getByRole("article");
  const frame = page.getByTestId("tile-frame");
  const shown = page.getByTestId("shown");

  await test.step("attach the transformed source with its processed folder and select it", async () => {
    await page.goto("/#/data");
    await expect(page.getByText("Nothing is attached yet")).toBeVisible();
    await page.getByLabel("Folder path", { exact: true }).fill(TRANSFORMED);
    await page.getByLabel("Processed folder path").fill(PROCESSED);
    await page.getByRole("button", { name: "Attach" }).click();
    await page.getByRole("button", { name: "Select", exact: true }).click();
    await expect(page.getByRole("button", { name: "Selected" })).toBeDisabled();
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

  await test.step("split the new block, remove the second piece and undo it", async () => {
    for (let i = 0; i < 6; i++) await page.keyboard.press("Shift+ArrowLeft");
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
    await expect(cards.last()).toContainText("confirmed");
    await expect(page.getByTestId("state")).toContainText("now 5 edits not saved yet");

    await page.getByLabel("Notes on the session").fill("the whole story");
    await page.getByRole("button", { name: "Save session" }).click();
    await expect(toast(`Saved ${realpathSync(PROCESSED)}/review/${S1}.json, a new file`)).toBeVisible();
    await expect(toast(`Opened the next session to review, ${S6}`)).toBeVisible();
    const saved = JSON.parse(readFileSync(join(PROCESSED, "review", `${S1}.json`), "utf8"));
    expect(saved.blocks.map((b: { status: string }) => b.status)).toEqual(["dropped", "edited", "edited", "confirmed"]);
    expect(saved.edits).toHaveLength(5);
  });

  await test.step("the sessions index counts the review and the replay shows it saved after a reload", async () => {
    await goTo("Sessions");
    await expect(page.getByTestId("totals")).toContainText("1 of 6 sessions reviewed, 3 blocks confirmed");
    await page.getByLabel("Filter sessions").fill("ns14");
    await page.getByRole("row").nth(1).click();
    await page.getByRole("button", { name: "Open in replay" }).click();
    const state = page.getByTestId("state");
    await expect(state).toContainText(/^saved .* by \S+, 5 edits$/);
    await page.reload();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await expect(state).toContainText(/^saved .* by \S+, 5 edits$/);
    await expect(page.getByLabel("Notes on the session")).toHaveValue("the whole story");
    await expect(cards.first()).toContainText("dropped");
  });

  await test.step("the blocks index shows the processed dataset, a window length is tested and saved", async () => {
    await goTo("Blocks");
    await expect(page.getByRole("row")).toHaveCount(4);
    await page.getByLabel("window (s)").fill("5");
    await page.getByRole("button", { name: "Test on all blocks" }).click();
    await expect(toast("Tested 3 blocks, 2 ok and 1 in trouble")).toBeVisible();
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(toast(`Saved ${SETTINGS_FILE}, a new file`)).toBeVisible();
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
