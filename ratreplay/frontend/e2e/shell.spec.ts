import { expect, test } from "@playwright/test";

test("the shell shows the seven pages in a viewport that never scrolls", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation").getByRole("link")).toHaveCount(7);
  await page.getByRole("link", { name: "Replay" }).click();
  await expect(page).toHaveURL(/#\/replay$/);
  await expect(page.getByRole("heading", { name: "Replay" })).toBeVisible();
  const scrolls = await page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight);
  expect(scrolls).toBe(false);
});

test("the theme is dark by default and the toggle switches it", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Light mode" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});
