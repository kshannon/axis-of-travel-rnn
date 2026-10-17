import { expect, test } from "@playwright/test";
import { detachAll, PROCESSED, TRANSFORMED } from "./synthetic";

test.beforeEach(({ request }) => detachAll(request));

test("the form says what is wrong, then a source is attached, selected, kept over a reload and detached", async ({ page }) => {
  await page.goto("/#/data");
  await expect(page.getByText("Nothing is attached yet")).toBeVisible();

  await page.getByRole("button", { name: "Attach" }).click();
  await expect(page.getByRole("alert")).toContainText("Enter the path of the folder");
  await page.getByLabel("Folder path", { exact: true }).fill("/no/such/folder");
  await page.getByLabel("Processed folder path").fill(PROCESSED);
  await page.getByRole("button", { name: "Attach" }).click();
  await expect(page.getByRole("alert")).toContainText("folder does not exist");

  await page.getByLabel("Folder path", { exact: true }).fill(TRANSFORMED);
  await page.getByRole("button", { name: "Attach" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Attached" })).toBeVisible();
  const source = page.getByRole("article");
  await expect(source).toContainText("ok");
  await expect(source.locator("dl > div").filter({ hasText: "sessions" }).first()).toContainText("6");
  await expect(source.getByText("converter run")).toBeVisible();

  await page.getByLabel("Folder path", { exact: true }).fill(TRANSFORMED);
  await page.getByLabel("Processed folder path").fill(`${PROCESSED}-elsewhere`);
  await page.getByRole("button", { name: "Attach" }).click();
  await expect(page.getByRole("alert")).toContainText("is already attached as transformed with its reviews and blocks in");
  await expect(page.getByRole("article")).toHaveCount(1);

  await source.getByRole("button", { name: "Select", exact: true }).click();
  await expect(source.getByRole("button", { name: "Selected" })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole("article").getByRole("button", { name: "Selected" })).toBeDisabled();

  await page.getByRole("button", { name: "Detach" }).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("article")).toHaveCount(1);
  await page.getByRole("button", { name: "Detach" }).click();
  await page.getByRole("button", { name: "Confirm detach" }).click();
  await expect(page.getByRole("article")).toHaveCount(0);

  await page.getByRole("link", { name: "Sessions" }).click();
  await expect(page.getByText("No source is selected.")).toBeVisible();
  await page.getByRole("link", { name: "Choose a source on the Data page" }).click();
  await expect(page).toHaveURL(/#\/data$/);
});
