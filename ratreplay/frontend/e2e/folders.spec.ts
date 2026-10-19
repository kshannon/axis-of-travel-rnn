import { expect, test } from "@playwright/test";
import { countTile, goTo, nextHealth, readConfig, resetProcessed, S1, saveThroughApi, toast, writeConfig } from "./synthetic";

let original = "";
test.beforeAll(() => {
  original = readConfig();
});

// The server keeps the folders it read at the last Reload, so a config put back is read again before the next test.
test.afterEach(async ({ request }) => {
  writeConfig(original);
  await request.get("/api/health", { params: { reload: "true" } });
  resetProcessed();
});

const without = (key: string) => original.split("\n").filter((line) => !line.startsWith(key)).join("\n");

// The story a person lives on the folders: a config that misses a key, the way the pages say so, the fix, rebuilding what was reviewed, then the environments and the guide.
test("a config missing a key shows the problem and gates the pages, the fixed config reads again, Rebuild all rebuilds the reviewed sessions, Environments and About render", async ({ page, request }) => {
  const strip = page.getByTestId("strip");
  const processed = page.getByTestId("processed");
  const rebuild = page.getByRole("button", { name: "Rebuild all" });
  await saveThroughApi(request, S1);

  // Reload ends in a toast. A click dismisses it, so the next Reload's toast is the only one on screen.
  const reload = async () => {
    await page.getByRole("button", { name: "Reload config file" }).click();
    const done = toast(page, "Read the config file again and checked the folders");
    await expect(done).toBeVisible();
    await done.click();
    await expect(done).toBeHidden();
  };

  await test.step("a config without the lab data folder shows the problem on the Incoming strip and no sessions", async () => {
    await page.goto("/#/incoming");
    await expect(strip.getByText("ok", { exact: true })).toHaveCount(4); // the lab data, the environment geometry, the synthetic sets and the config file
    await expect(page.getByTestId("config-path")).toContainText("local.yaml");
    writeConfig(without("TRANSFORMED_LAB_DATA"));
    await reload();
    await expect(strip.getByText("problem", { exact: true })).toHaveCount(1);
    await expect(page.getByTestId("strip-problems")).toContainText("TRANSFORMED_LAB_DATA is not set in");
    await expect(page.getByText("The transformed lab data cannot be used: TRANSFORMED_LAB_DATA is not set in")).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount(0);
  });

  await test.step("the Outgoing page is gated too, cannot rebuild, and links back to Incoming", async () => {
    await goTo(page, "Outgoing");
    await expect(page.getByText("The transformed lab data cannot be used")).toBeVisible();
    await expect(rebuild).toBeDisabled();
    await page.getByRole("link", { name: "Open the Incoming page" }).click();
    await expect(page).toHaveURL(/#\/incoming$/);
  });

  await test.step("a config without the processed folder gates the sessions with a link to Outgoing, where the write path shows the problem", async () => {
    writeConfig(without("PROCESSED_LAB_DATA"));
    await reload();
    await expect(strip.getByText("ok", { exact: true })).toHaveCount(4); // the strip names only what is read, the lab data is back
    await expect(page.getByText("The processed lab data cannot be used: PROCESSED_LAB_DATA is not set in")).toBeVisible();
    await page.getByRole("link", { name: "Open the Outgoing page" }).click();
    await expect(page).toHaveURL(/#\/outgoing$/);
    await expect(processed.getByText("problem", { exact: true })).toBeVisible();
    await expect(processed).toContainText("PROCESSED_LAB_DATA is not set in");
    await expect(rebuild).toBeDisabled();
  });

  await test.step("the fixed config is read again, the sessions come back and the incoming format opens at the bottom", async () => {
    await goTo(page, "Incoming");
    writeConfig(original);
    await reload();
    await expect(strip.getByText("ok", { exact: true })).toHaveCount(4);
    await expect(strip.getByText("problem", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("row")).toHaveCount(7); // the header and six sessions
    await page.getByText("Incoming data format").click();
    await expect(page.getByText("sessions.csv", { exact: true })).toBeVisible();
  });

  await test.step("Rebuild all on Outgoing asks first, then rebuilds the reviewed session and toasts the totals", async () => {
    const mounted = nextHealth(page);
    await goTo(page, "Outgoing");
    await mounted;
    await expect(processed.getByText("ok", { exact: true })).toBeVisible();
    await expect(countTile(processed, "reviews")).toHaveText("1");
    const asked = new Promise<string>((resolve) => page.once("dialog", (dialog) => { resolve(dialog.message()); void dialog.accept(); }));
    const read = nextHealth(page);
    await rebuild.click();
    expect(await asked).toContain("Build the blocks of 1 reviewed session again");
    await expect(toast(page, "Rebuilt 1 session, 2 blocks built, 0 failed, 0 skipped (not in the dataset), 0 excluded by you, 0 errors")).toBeVisible();
    await read; // the folder is read again once the blocks are built
    await expect(countTile(processed, "blocks")).toHaveText("2");
    await expect(countTile(processed, "built sessions")).toHaveText("1");
    await expect(page.getByText("1 session, 2 blocks built, 0 failed", { exact: true })).toBeVisible();
  });

  await test.step("the Environments page shows a strip of the four environments and the selected one large, with its drawing and the registration the built session was given, a choice surviving a reload", async () => {
    await goTo(page, "Environments");
    const large = page.getByTestId("environment");
    await expect(page.getByTestId("thumbnail")).toHaveCount(4);
    await expect(large.getByRole("heading")).toHaveText("open_arena"); // the first of the environments with one built session
    await expect(large.getByTestId("geometry").locator("canvas")).toBeVisible();
    await expect(large.getByTestId("ranges")).toContainText("1 session, scale");
    await page.getByTestId("thumbnail").filter({ hasText: "plus_maze" }).click();
    await expect(large.getByRole("heading")).toHaveText("plus_maze");
    await expect(large.getByTestId("no-sessions")).toBeVisible();
    await page.reload();
    await expect(large.getByRole("heading")).toHaveText("plus_maze");
  });

  await test.step("the About page gives the guide and its Under the hood section the routes, and the top bar has the ten pages in order", async () => {
    const nav = page.getByRole("navigation");
    await expect(nav.getByRole("link")).toHaveText(["Incoming", "Settings", "Replay", "Blocks", "Windows", "Synthetic", "Real or synthetic", "Outgoing", "Environments", "About"]);
    await goTo(page, "About");
    await expect(page.getByRole("heading", { name: "Process and how to use it" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "What you can do and what it writes" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Choose the window settings on Settings" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Generate synthetic behavior on Synthetic and test it on Real or synthetic" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Check what is built and hand over the export on Outgoing" })).toBeVisible();
    await page.getByRole("button", { name: "Under the hood" }).click();
    await expect(page.getByRole("heading", { name: "Under the hood" })).toBeVisible();
    await expect(page.getByText("/api/health", { exact: true })).toBeVisible();
    await expect(page.getByText("/api/environments", { exact: true })).toBeVisible();
  });
});
