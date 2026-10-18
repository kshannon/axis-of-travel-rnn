import { expect, test } from "@playwright/test";
import { countTile, nextHealth, readConfig, resetProcessed, S1, saveThroughApi, toast, writeConfig } from "./synthetic";

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

// The story a person lives on the Data page: a config that misses a folder, the way the other pages say so, the fix, rebuilding what was reviewed.
test("a config missing a key shows the problem and gates the pages, the fixed config reads again, Rebuild all rebuilds the reviewed sessions", async ({ page, request }) => {
  const transformed = page.getByTestId("transformed");
  const processed = page.getByTestId("processed");
  await saveThroughApi(request, S1);

  await test.step("a config without the processed folder shows the problem on the Data page and the gate on Sessions", async () => {
    await page.goto("/#/data");
    await expect(processed.getByText("ok", { exact: true })).toBeVisible();
    await expect(page.getByTestId("config-path")).toContainText("local.yaml");
    writeConfig(original.split("\n").filter((line) => !line.startsWith("PROCESSED_LAB_DATA")).join("\n"));
    await page.getByRole("button", { name: "Reload" }).click();
    await expect(processed.getByText("problem", { exact: true })).toBeVisible();
    await expect(processed).toContainText("PROCESSED_LAB_DATA is not set in");
    await expect(transformed.getByText("ok", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Rebuild all" })).toBeDisabled();

    await page.getByRole("navigation").getByRole("link", { name: "Sessions", exact: true }).click();
    await expect(page.getByText("The processed lab data cannot be used: PROCESSED_LAB_DATA is not set in")).toBeVisible();
    await page.getByRole("link", { name: "Open the Data page" }).click();
    await expect(page).toHaveURL(/#\/data$/);
  });

  await test.step("the fixed config is read again and the folders are ok", async () => {
    writeConfig(original);
    await page.getByRole("button", { name: "Reload" }).click();
    await expect(toast(page, "Read the config file again")).toBeVisible();
    for (const folder of ["transformed", "processed", "environments"]) await expect(page.getByTestId(folder).getByText("ok", { exact: true })).toBeVisible();
    await expect(page.getByTestId("config-path")).toContainText("local.yaml");
    await expect(countTile(processed, "reviews")).toHaveText("1");
    await expect(page.getByRole("heading", { name: "Data format" })).toBeVisible();
    await expect(page.getByText("sessions.csv", { exact: true })).toBeVisible();
  });

  await test.step("Rebuild all asks first, then rebuilds the reviewed session and toasts the totals", async () => {
    const asked = new Promise<string>((resolve) => page.once("dialog", (dialog) => { resolve(dialog.message()); void dialog.accept(); }));
    const read = nextHealth(page);
    await page.getByRole("button", { name: "Rebuild all" }).click();
    expect(await asked).toContain("Build the blocks of 1 reviewed session again");
    await expect(toast(page, "Rebuilt 1 session, 2 blocks built, 0 failed, 0 skipped (not in the dataset), 0 excluded by you, 0 errors")).toBeVisible();
    await read; // the folder is read again once the blocks are built
    await expect(countTile(processed, "blocks")).toHaveText("2");
    await expect(countTile(processed, "built sessions")).toHaveText("1");
  });

  await test.step("the About page gives the guide and its Under the hood section the routes, and there is no API page", async () => {
    const nav = page.getByRole("navigation");
    await expect(nav.getByRole("link", { name: "API", exact: true })).toHaveCount(0);
    await nav.getByRole("link", { name: "About", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Process and how to use it" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "What you can do and what it writes" })).toBeVisible();
    await page.getByRole("button", { name: "Under the hood" }).click();
    await expect(page.getByRole("heading", { name: "Under the hood" })).toBeVisible();
    await expect(page.getByText("/api/health", { exact: true })).toBeVisible();
  });
});
