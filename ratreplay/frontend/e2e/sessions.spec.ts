import { expect, test } from "@playwright/test";
import { openReplay, pageScrolls, S1, S6 } from "./synthetic";

test("sort the sessions, open one in the replay", async ({ page }) => {
  await page.goto("/#/sessions");
  const rows = page.getByRole("row");
  await expect(rows).toHaveCount(7); // the header and six sessions
  await expect(page.getByTestId("totals")).toHaveText("0 of 6 sessions reviewed, 0 blocks confirmed, confirmed hours: arena 0.00, track 0.00");
  await expect(page.getByRole("button", { name: "Confirmed blocks" })).toBeVisible();
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
  await expect(page.getByTestId("session-id")).toHaveText(S6);
});

test("opening another session while the replay has unsaved edits asks first, the session already open does not", async ({ page }) => {
  await openReplay(page, S6);
  await page.getByRole("button", { name: "Accept all" }).click();
  await expect(page.getByTestId("state")).toContainText("now 1 edit not saved yet");

  await page.getByRole("link", { name: "Sessions" }).click();
  await page.getByLabel("Filter sessions").fill("ns16");
  await page.getByRole("row").nth(1).click();
  await page.getByRole("button", { name: "Open in replay" }).click();
  await expect(page).toHaveURL(/#\/replay$/);
  await expect(page.getByTestId("state")).toContainText("now 1 edit not saved yet");

  await page.getByRole("link", { name: "Sessions" }).click();
  await page.getByLabel("Filter sessions").fill("ns14");
  await page.getByRole("row").nth(1).click();
  await page.getByRole("button", { name: "Open in replay" }).click();
  await expect(page.getByText(`The edits to ${S6} in the replay are not saved and would be lost`)).toBeVisible();
  await expect(page).toHaveURL(/#\/sessions$/);
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("button", { name: "Open in replay" })).toBeVisible();

  await page.getByRole("button", { name: "Open in replay" }).click();
  await page.getByRole("button", { name: "Open and drop them" }).click();
  await expect(page).toHaveURL(/#\/replay$/);
  await expect(page.getByTestId("session-id")).toHaveText(S1);
  await expect(page.getByTestId("state")).toHaveText("automatic");
});
