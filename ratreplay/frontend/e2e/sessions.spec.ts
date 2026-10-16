import { expect, test } from "@playwright/test";
import { detachAll, pageScrolls, PROCESSED, TRANSFORMED } from "./synthetic";

const SESSION = "NS16_rec6_20150106_001";

test.beforeEach(({ request }) => detachAll(request));

test("attach, select, sort the sessions, open one in the replay", async ({ page }) => {
  await page.goto("/#/data");
  await page.getByLabel("Folder path", { exact: true }).fill(TRANSFORMED);
  await page.getByLabel("Processed folder path").fill(PROCESSED);
  await page.getByRole("button", { name: "Attach" }).click();
  await page.getByRole("button", { name: "Select", exact: true }).click();

  await page.getByRole("link", { name: "Sessions" }).click();
  const rows = page.getByRole("row");
  await expect(rows).toHaveCount(7); // the header and six sessions
  await expect(rows.nth(1)).toContainText("NS14");

  await page.getByRole("button", { name: "Minutes" }).click();
  await expect(rows.nth(1)).toContainText("NS15");
  await page.getByRole("button", { name: "Minutes" }).click();
  await expect(rows.nth(1)).toContainText("NS16");

  await page.getByLabel("Filter sessions").fill("ns16");
  await expect(rows).toHaveCount(2);
  await rows.nth(1).click();
  await expect(page.getByRole("heading", { name: "Automatic blocks" })).toBeVisible();
  await expect(page.getByText("LED offset")).toBeVisible();
  expect(await pageScrolls(page)).toBe(false);

  await page.getByRole("button", { name: "Open in replay" }).click();
  await expect(page).toHaveURL(/#\/replay$/);
  await expect(page.getByTestId("session-id")).toHaveText(SESSION);
});
