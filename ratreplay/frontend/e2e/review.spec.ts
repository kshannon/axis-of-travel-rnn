import { expect, test } from "@playwright/test";
import { countTile, environmentPixels, goTo, nextHealth, resetProcessed, S1, S6, toast, WALL_PIXELS } from "./synthetic";

test.afterEach(resetProcessed);

// The Excluded cell of a row of the sessions index on the Incoming page: rat, date, protocol, in dataset, excluded.
const EXCLUDED_CELL = 4;

// The story a person lives on the synthetic data: the Incoming page reads ok, a session is chosen and reviewed, the review is saved and found saved again,
// the Outgoing page counts it, and a session is excluded and included from the Incoming page.
// Nothing waits on a timer: each step waits for what it expects to see, and a save for the toast it ends in.
test("read the folders, review a session, refuse a split, split the track block, save, find the blocks saved, and exclude and include a session", async ({ page }) => {
  const cards = page.getByRole("article");
  const frame = page.getByTestId("tile-frame");
  const state = page.getByTestId("state");
  const processed = page.getByTestId("processed");
  const strip = page.getByTestId("strip");
  const totals = page.getByTestId("totals");

  await test.step("the Incoming page reads the folders ok and counts the sessions, none reviewed yet", async () => {
    await page.goto("/#/incoming");
    await expect(strip.getByText("ok", { exact: true })).toHaveCount(3); // the lab data, the environment geometry and the config file
    await expect(strip.getByText("problem", { exact: true })).toHaveCount(0);
    await expect(page.getByTestId("config-path")).toContainText("local.yaml");
    await expect(totals).toHaveAttribute("aria-label", /2 of 6 sessions in the dataset, 0 reviewed, 0 excluded, 0 blocks confirmed/);
    await expect(totals.getByText("2 of 6", { exact: true })).toBeVisible();
  });

  await test.step("the sessions list the dataset first and one opens in the Replay", async () => {
    const rows = page.getByRole("row");
    await expect(rows).toHaveCount(7); // the header and six sessions
    await expect(rows.nth(1)).toContainText(/NS14.*yes/);
    await expect(rows.nth(2)).toContainText(/NS16.*yes/);
    await expect(rows.nth(3)).toContainText(/NS14.*rotation.*no/);
    await rows.nth(1).click();
    await page.getByRole("button", { name: "Open in replay" }).click();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await expect(frame).toHaveText("1");
  });

  await test.step("the blocks are drawn with the windows they yield at the default 40 s window", async () => {
    await expect(cards).toHaveCount(2); // the arena block and the track block
    await expect(cards.first()).toContainText("0 training windows");
    await expect(cards.first().getByTestId("verdict")).toHaveText("no window of 40 s plus 0.5 s horizon fits in this 20 s block");
    await expect(page.getByTestId("settings")).toContainText("window 40 s, stride 10 s");
    await expect(page.getByTestId("map").locator("canvas")).toBeVisible();
    await expect(state).toHaveText("automatic, nothing reviewed yet");
  });

  await test.step("a split that leaves a piece under 10 s is refused and toasted with the API's reason", async () => {
    await cards.nth(1).click();
    await expect(cards.nth(1)).toHaveAttribute("aria-current", "true");
    await expect(page.getByTestId("selection")).toContainText("block 2");
    for (let i = 0; i < 39; i++) await page.keyboard.press("Shift+ArrowRight");
    await expect(frame).toHaveText("2341"); // 4 s into the track block
    await expect.poll(() => environmentPixels(page)).toBeGreaterThan(WALL_PIXELS); // the track's walls are drawn in metres
    await page.getByRole("button", { name: "Split here" }).click();
    const refused = toast(page, "a kept block must last 10 s or more");
    await expect(refused).toBeVisible();
    await expect(refused).toContainText("Warning"); // a warning is held in the stack at the top right with the time, until it is closed
    await refused.getByRole("button", { name: "Close" }).click();
    await expect(refused).toBeHidden();
    await expect(cards).toHaveCount(2);
  });

  await test.step("the track block splits in half at frame 2701, accept all confirms the rest", async () => {
    for (let i = 0; i < 6; i++) await page.keyboard.press("Shift+ArrowRight");
    await expect(frame).toHaveText("2701"); // the middle of the track block, the only split that leaves two blocks of 10 s
    await page.getByRole("button", { name: "Split here" }).click();
    await expect(toast(page, "Added split at frame 2701")).toBeVisible();
    await expect(cards).toHaveCount(3);
    await page.getByRole("button", { name: "Accept all" }).click();
    await expect(cards.first()).toContainText("confirmed");
    await expect(cards.nth(1)).toContainText("edited");
    await expect(cards.nth(2)).toContainText("edited");
    await expect(state).toHaveText("2 edits not saved");
  });

  await test.step("a click on the frames lane selects a frame, a second click on it and escape let go of it", async () => {
    const box = (await page.getByTestId("timeline").boundingBox())!;
    const unit = (box.height - 38) / 8; // the lanes weigh 1, 2, 3 and 2, the frames lane is the third
    const frames = { x: box.width / 2, y: 12 + 4.5 * unit };
    const selection = page.getByTestId("selection");
    await page.getByTestId("timeline").click({ position: frames });
    await expect(selection).toContainText(/^frame \d+, at /);
    await page.getByTestId("timeline").click({ position: frames });
    await expect(selection).toHaveText("nothing selected");
    await page.getByTestId("timeline").click({ position: frames });
    await expect(selection).toContainText("frame");
    await page.keyboard.press("Escape");
    await expect(selection).toHaveText("nothing selected");
  });

  await test.step("a start offset the maze cannot close around is refused and not kept, 0.12 registers the session again and waits for the save", async () => {
    const offset = page.getByLabel("Start offset, m");
    await expect(offset).toHaveValue("0.00"); // the yaml's default
    await offset.fill("0.4");
    const refused = toast(page, "Could not move the start offset");
    await expect(refused).toBeVisible();
    await refused.getByRole("button", { name: "Close" }).click();
    await expect(offset).toHaveValue("0.00");
    const registered = page.waitForResponse((response) => response.url().includes("/arrays?start_offset_m=0.12"));
    await offset.fill("0.12");
    await registered;
    await expect(page.getByTestId("start-offset").getByText("not saved")).toBeVisible();
    await expect(state).toHaveText("2 edits not saved"); // the edits and the status header are as they were
    await expect(cards).toHaveCount(3);
    await expect(page.getByTestId("map").locator("canvas")).toBeVisible();
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

  await test.step("the session id is a picker: filter and open a session, step back with the arrow, and unsaved edits are asked about first", async () => {
    const picker = page.getByTestId("picker");
    const sessionId = page.getByTestId("session-id");
    const previous = page.getByRole("button", { name: "Previous session" });
    const filter = page.getByLabel("Find a session");
    await sessionId.click();
    await expect(picker).toBeVisible();
    await expect(picker.getByRole("button", { name: S6 })).toContainText("open"); // the session open is marked
    await expect(picker.getByRole("button", { name: S1 })).toContainText("reviewed");
    await expect(picker.getByRole("button", { name: /not in the dataset/ }).first()).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(picker).toBeHidden();
    await sessionId.click();
    await filter.fill("ns14");
    await page.keyboard.press("Enter"); // enter opens the first session the filter leaves, the dataset first
    await expect(sessionId).toHaveText(S1);
    await expect(picker).toBeHidden();
    await sessionId.click();
    await filter.fill("ns16");
    await picker.getByRole("button", { name: S6 }).click();
    await expect(sessionId).toHaveText(S6);
    await page.getByRole("button", { name: "Accept all" }).click();
    await expect(state).toHaveText("1 edit not saved");
    let asked = "";
    page.once("dialog", (dialog) => { asked = dialog.message(); void dialog.dismiss(); });
    await previous.click();
    await expect.poll(() => asked).toContain(`${S6} has 1 edit not saved`);
    await expect(sessionId).toHaveText(S6); // dismissed, so it stays
    page.once("dialog", (dialog) => void dialog.accept());
    await previous.click(); // the index's order has S1 before S6
    await expect(sessionId).toHaveText(S1);
    await expect(previous).toBeDisabled();
    await expect(previous).toHaveAttribute("title", `${S1} is the first session of the index`);
  });

  await test.step("a reload shows the saved blocks", async () => {
    await goTo(page, "Incoming");
    await expect(totals).toHaveAttribute("aria-label", /of 6 sessions in the dataset, 1 reviewed, 0 excluded, 3 blocks confirmed/);
    await page.getByLabel("Filter sessions").fill("ns14");
    await page.getByRole("row").nth(1).click();
    await page.getByRole("button", { name: "Open in replay" }).click();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await page.reload();
    await expect(page.getByTestId("session-id")).toHaveText(S1);
    await expect(state).toHaveText(/^saved by \S+ on \d{4}-\d{2}-\d{2}, 2 edits$/);
    await expect(page.getByLabel("Notes on the session")).toHaveValue("the whole story");
    await expect(page.getByLabel("Start offset, m")).toHaveValue("0.12"); // the saved review's offset, which the session is registered with
    await expect(page.getByTestId("start-offset").getByText("not saved")).toBeHidden();
    await expect(cards).toHaveCount(3);
    await expect(cards.first()).toContainText("confirmed");
    await expect(cards.nth(1)).toContainText("edited");
    await expect(cards.nth(2)).toContainText("edited");
  });

  await test.step("the Outgoing page counts the review and the blocks built from it", async () => {
    const read = nextHealth(page);
    await goTo(page, "Outgoing");
    await read; // the counts are the folder's as it is now, not those the page kept from before
    await expect(countTile(processed, "reviews")).toHaveText("1");
    await expect(countTile(processed, "blocks")).toHaveText("3");
    await expect(countTile(processed, "built sessions")).toHaveText("1");
    await expect(page.getByText("1 session, 3 blocks built, 0 failed", { exact: true })).toBeVisible();
  });

  await test.step("a session is excluded from the Incoming page with a note and shown in the Excluded column", async () => {
    await goTo(page, "Incoming");
    await expect(page.getByRole("columnheader", { name: "Excluded" })).toBeVisible();
    await page.getByLabel("Filter sessions").fill("ns16");
    const row = page.getByRole("row").nth(1);
    await expect(row).toContainText("NS16");
    await expect(row.getByRole("cell").nth(EXCLUDED_CELL)).toHaveText("");
    await row.click();
    page.once("dialog", (dialog) => void dialog.accept("camera moved"));
    await page.getByRole("button", { name: "Exclude", exact: true }).click();
    const left = toast(page, `Excluded ${S6}`);
    await expect(left).toBeVisible();
    await expect(left).toContainText(`review/${S6}.json`);
    await expect(row.getByRole("cell").nth(EXCLUDED_CELL)).toHaveText("yes");
    await expect(totals).toHaveAttribute("aria-label", /of 6 sessions in the dataset, 2 reviewed, 1 excluded/);
    await expect(page.getByRole("paragraph").filter({ hasText: "camera moved" })).toBeVisible(); // the notes of its review, in the open details
  });

  await test.step("in the Replay the excluded session shows its chip and cannot be saved, and Include takes it back", async () => {
    await page.getByRole("button", { name: "Open in replay" }).click();
    await expect(page.getByTestId("session-id")).toHaveText(S6);
    await expect(state).toHaveText("excluded");
    await expect(page.getByRole("button", { name: "Save blocks" })).toBeDisabled();
    page.once("dialog", (dialog) => void dialog.accept(""));
    await page.getByRole("button", { name: "Include", exact: true }).click();
    await expect(toast(page, `Included ${S6} again`)).toBeVisible();
    await expect(state).not.toHaveText("excluded");
    await expect(page.getByRole("button", { name: "Save blocks" })).toBeEnabled();
    const read = nextHealth(page);
    await goTo(page, "Incoming");
    await read; // the page reads the folders as it opens, and the test must not end, and clear them, while the API is still reading
    await expect(totals).toHaveAttribute("aria-label", /of 6 sessions in the dataset, 1 reviewed, 0 excluded/);
    await expect(page.getByRole("row").nth(1).getByRole("cell").nth(EXCLUDED_CELL)).toHaveText("");
  });
});
