import { expect, test } from "@playwright/test";
import { countTile, goTo, nextHealth, resetProcessed, resetSynthetic, S1, S6, saveThroughApi, toast } from "./synthetic";

// Generating runs the generator and the blocking over two minutes of each kind, so the test gets more than the default time.
test.setTimeout(180_000);

// What the Generate form is filled with: the seed and the minutes of each kind.
const SEED = "7";
const MINUTES = "2";

// The three blocks of S1 and S6 are built at the default settings before the story starts, without the Replay page.
test.beforeEach(async ({ request }) => {
  await saveThroughApi(request, S1);
  await saveThroughApi(request, S6);
});

test.afterEach(() => {
  resetSynthetic();
  resetProcessed();
});

// The story a person lives on the Synthetic page: no set yet, a set generated from the two built sessions, the recipes compared, the set as a dataset on Blocks and a count on Outgoing, then deleted.
test("generate a synthetic set from the built sessions, compare its recipe with the real one, find it on the Blocks and Outgoing pages, and delete it", async ({ page }) => {
  const sources = page.getByTestId("sources");
  const setCount = page.getByTestId("set-count");
  let setId = "";

  await test.step("the Synthetic page lists no set and offers the two built sessions as sources", async () => {
    await page.goto("/#/synthetic");
    await expect(page.getByText("No synthetic set yet. Generate one from the built sessions.")).toBeVisible();
    await expect(setCount).toHaveText("0 sets");
    await expect(sources.getByRole("checkbox")).toHaveCount(2);
    await expect(sources).toContainText(S1);
    await expect(sources).toContainText(S6);
    await expect(page.getByRole("button", { name: "Generate" })).toBeDisabled();
    await expect(page.getByText("Choose a set in the table to see its recipe beside the real one.")).toBeVisible();
  });

  await test.step("two minutes of each kind are generated from both sessions with seed 7, toasted, listed, and compared kind by kind with a value in both columns", async () => {
    await sources.getByRole("checkbox").nth(0).check();
    await sources.getByRole("checkbox").nth(1).check();
    await page.getByLabel("Seed").fill(SEED);
    await page.getByLabel("arena minutes").fill(MINUTES);
    await page.getByLabel("track minutes").fill(MINUTES);
    const read = nextHealth(page);
    await page.getByRole("button", { name: "Generate" }).click();
    const made = toast(page, "Generated set syn_");
    await expect(made).toBeVisible();
    await expect(made).toContainText("2 blocks built (arena, track), 0 failed");
    await read;
    await expect(setCount).toHaveText("1 set");
    const row = page.getByRole("row").filter({ hasText: "syn_" });
    await expect(row).toHaveCount(1);
    setId = (await row.getAttribute("title"))!;
    expect(setId).toMatch(new RegExp(`^syn_\\d{8}_\\d{6}_${SEED}$`));
    await expect(row).toContainText(`arena ${MINUTES}, track ${MINUTES}`);
    await expect(row).toContainText("2 (arena, track)");
    await expect(row).toContainText("none");
    await expect(page.getByTestId("compare-caption")).toContainText(`on the blocks of set ${setId} (right, seed ${SEED})`);
    await expect(page.getByTestId("compare-caption")).toContainText(`${S1}, ${S6}`);
    const comparison = page.getByTestId("comparison");
    await expect(comparison.getByRole("heading")).toHaveText(["arena", "track"]);
    await expect(comparison.getByRole("columnheader", { name: "Real" })).toHaveCount(2);
    await expect(comparison.getByRole("columnheader", { name: "Synthetic" })).toHaveCount(2);
    const blocks = comparison.getByRole("row").filter({ has: page.getByRole("cell", { name: "blocks", exact: true }) });
    await expect(blocks.nth(0).getByRole("cell")).toHaveText(["blocks", "1", "1"]); // the arena block of S1 against the set's
    await expect(blocks.nth(1).getByRole("cell")).toHaveText(["blocks", "2", "1"]); // the track blocks of S1 and S6 against the set's
    const seconds = comparison.getByRole("row").filter({ has: page.getByRole("cell", { name: "seconds", exact: true }) });
    await expect(seconds.nth(0).getByRole("cell")).toHaveText(["seconds", /^\d+\.\d{2}$/, /^\d+\.\d{2}$/]);
    await expect(seconds.nth(1).getByRole("cell")).toHaveText(["seconds", /^\d+\.\d{2}$/, /^\d+\.\d{2}$/]);
    await expect(comparison.getByRole("row").filter({ hasText: "speed (m/s) median" })).toHaveCount(2);
    await expect(comparison.getByRole("row").filter({ hasText: "trips per minute" })).toHaveCount(1);
    await expect(comparison.getByRole("row").filter({ hasText: "boundary distance (m) median" })).toHaveCount(1);
    if (process.env.SYNTHETIC_SCREENSHOT) await page.screenshot({ path: process.env.SYNTHETIC_SCREENSHOT });
  });

  await test.step("the Blocks page offers the set as a dataset and judges its two blocks", async () => {
    await goTo(page, "Blocks");
    const dataset = page.getByLabel("Dataset");
    await expect(dataset.locator("option")).toHaveText(["real lab blocks", `synthetic set ${setId}`]);
    await dataset.selectOption(`set:${setId}`);
    await expect(page.getByTestId("judged")).toContainText(`judged at: synthetic set ${setId}`);
    await expect(page.getByRole("row")).toHaveCount(3); // the header and the two synthetic blocks
    await dataset.selectOption("real");
    await expect(page.getByTestId("judged")).toContainText("judged at: real lab blocks");
  });

  await test.step("the quiz opens a track pair of the set, draws both sides without a word of where they came from, and reveals the answer with the tally", async () => {
    await goTo(page, "Real or synthetic");
    await expect(page.getByLabel("Set")).toHaveValue(setId);
    await expect(page.getByLabel("Kind").locator("option")).toHaveText(["any kind", "arena", "track"]);
    await expect(page.getByTestId("tally")).toHaveText("No pair answered yet.");
    await expect(page.getByRole("button", { name: "Left is real" })).toBeDisabled();
    await page.getByLabel("Kind").selectOption("track");
    await page.getByRole("button", { name: "New pair" }).click();
    await expect(page.getByTestId("pair-kind")).toHaveText("track");
    await expect(page.getByRole("button", { name: "Left is real" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Right is real" })).toBeEnabled();
    const cards = page.locator("section").filter({ has: page.getByTestId(/^map-/) });
    await expect(cards).toHaveCount(2);
    for (const card of [cards.nth(0), cards.nth(1)]) await expect(card).not.toContainText(/NS1|syn_|track_01|run|path|phase/);
    await expect(page.getByTestId("chip-left")).toBeHidden();
    await page.getByRole("button", { name: "Play" }).click();
    await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();
    await expect.poll(() => page.getByTestId("time").textContent()).not.toBe("0:00");
    await page.getByRole("button", { name: "Pause" }).click();
    if (process.env.QUIZ_SCREENSHOTS) await page.screenshot({ path: `${process.env.QUIZ_SCREENSHOTS}/quiz-pair.png` });
    await page.getByRole("button", { name: "Left is real" }).click();
    const verdict = page.getByTestId("verdict");
    await expect(verdict).toHaveText(/^(Right|Wrong), the (left|right) block is real \(NS1\d_rec\d_\d{8}_001_track_01\) and the (left|right) one is synthetic \(syn_.*_track_01\)\.$/);
    const chips = [await page.getByTestId("chip-left").textContent(), await page.getByTestId("chip-right").textContent()];
    expect(chips.sort()).toEqual(["real", "synthetic"]);
    await expect(page.getByTestId("tally")).toHaveText(/^1 pair answered, [01] right, (0|100) percent\.$/);
    await expect(page.getByRole("button", { name: "Left is real" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Right is real" })).toBeDisabled();
    if (process.env.QUIZ_SCREENSHOTS) await page.screenshot({ path: `${process.env.QUIZ_SCREENSHOTS}/quiz-reveal.png` });
    await page.getByRole("button", { name: "New pair" }).click();
    await expect(page.getByTestId("chip-left")).toBeHidden();
    await expect(verdict).toBeHidden();
    await expect(page.getByRole("button", { name: "Left is real" })).toBeEnabled();
  });

  await test.step("the Outgoing page counts the set, its blocks and the one guess under the synthetic write path", async () => {
    const read = nextHealth(page);
    await goTo(page, "Outgoing");
    await read;
    const synthetic = page.getByTestId("synthetic");
    await expect(synthetic.getByText("ok", { exact: true })).toBeVisible();
    await expect(countTile(synthetic, "sets")).toHaveText("1");
    await expect(countTile(synthetic, "blocks")).toHaveText("2");
    await expect(countTile(synthetic, "guesses")).toHaveText("1");
  });

  await test.step("Delete asks first, names the set, and the page is empty again", async () => {
    await goTo(page, "Synthetic");
    await expect(setCount).toHaveText("1 set");
    const asked = new Promise<string>((resolve) => page.once("dialog", (dialog) => { resolve(dialog.message()); void dialog.accept(); }));
    await page.getByRole("button", { name: `Delete ${setId}` }).click();
    expect(await asked).toBe(`Delete set ${setId}? Its blocks and guesses go with it.`);
    await expect(toast(page, `Deleted set ${setId}, 2 blocks with it`)).toBeVisible();
    await expect(setCount).toHaveText("0 sets");
    await expect(page.getByText("No synthetic set yet. Generate one from the built sessions.")).toBeVisible();
  });
});
