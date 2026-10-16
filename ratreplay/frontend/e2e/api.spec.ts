import { expect, test } from "@playwright/test";
import { pageScrolls } from "./synthetic";

test("the API page lists the data format and the routes, each route opening on its tables", async ({ page }) => {
  await page.goto("/#/api");
  await expect(page.getByText("sessions.csv", { exact: true })).toBeVisible();

  const attach = page.locator("details").filter({ hasText: "Attach Source" });
  await expect(attach.getByText("Request body, AttachBody")).toBeHidden();
  await attach.locator("summary").click();
  await expect(attach.getByText("Request body, AttachBody")).toBeVisible();
  await expect(attach.getByRole("cell", { name: "processed_path" })).toBeVisible();
  expect(await pageScrolls(page)).toBe(false);
});

test("the About page links to the API page", async ({ page }) => {
  await page.goto("/#/about");
  await expect(page.getByText("space", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "API page" }).click();
  await expect(page).toHaveURL(/#\/api$/);
});
