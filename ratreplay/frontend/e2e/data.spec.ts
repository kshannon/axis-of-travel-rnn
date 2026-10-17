import { realpathSync, renameSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { pageScrolls, PROCESSED, SYNTHETIC_ROOT, TRANSFORMED } from "./synthetic";

test("the Data page shows the flow, the two folders of the config with their counts and times, and the config file", async ({ page }) => {
  await page.goto("/#/data");
  await expect(page.getByText("built by the processor into processed data")).toBeVisible();

  const transformed = page.getByTestId("transformed");
  await expect(transformed).toContainText("incoming");
  await expect(transformed).toContainText(realpathSync(TRANSFORMED));
  await expect(transformed.getByText("ok", { exact: true })).toBeVisible();
  await expect(transformed.locator("dl > div").filter({ hasText: "sessions" }).first()).toContainText("6");
  await expect(transformed.getByText("converter run")).toBeVisible();

  const processed = page.getByTestId("processed");
  await expect(processed).toContainText("outbound");
  await expect(processed).toContainText(realpathSync(PROCESSED));
  await expect(processed.locator("dl > div").filter({ hasText: "blocks" }).first()).toContainText("3");
  await expect(processed.getByText("processor run")).toBeVisible();

  await expect(page.getByTestId("config-path")).toHaveText(realpathSync(join(SYNTHETIC_ROOT, "local.yaml")));
  await expect(page.getByText("Changing a folder means editing this file")).toBeVisible();
  expect(await pageScrolls(page)).toBe(false);
});

test("a folder that breaks the format shows why, the pages that need it say so and link to Data, and Reload clears it once fixed", async ({ page }) => {
  const epochs = join(TRANSFORMED, "epochs.csv");
  const transformed = page.getByTestId("transformed");
  await page.goto("/#/data");
  await expect(transformed.getByText("ok", { exact: true })).toBeVisible();

  renameSync(epochs, `${epochs}.off`);
  try {
    await page.getByRole("button", { name: "Reload" }).click();
    await expect(transformed.getByText("invalid", { exact: true })).toBeVisible();
    await expect(transformed).toContainText("missing epochs.csv");

    await page.getByRole("link", { name: "Sessions" }).click();
    await expect(page.getByText("The transformed lab data cannot be used: missing epochs.csv")).toBeVisible();
    await page.getByRole("link", { name: "Open the Data page" }).click();
    await expect(page).toHaveURL(/#\/data$/);
  } finally {
    renameSync(`${epochs}.off`, epochs);
  }

  await page.getByRole("button", { name: "Reload" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Read the config file again" })).toBeVisible();
  await expect(transformed.getByText("ok", { exact: true })).toBeVisible();
  await expect(transformed).not.toContainText("missing epochs.csv");
});
