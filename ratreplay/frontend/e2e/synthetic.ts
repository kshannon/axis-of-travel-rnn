import { rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

export const PORT = 8061;

// serve_synthetic.py rebuilds this folder on every start. It sits outside the repository, where the processor refuses to write.
export const SYNTHETIC_ROOT = join(tmpdir(), "ratreplay-e2e");
export const TRANSFORMED = join(SYNTHETIC_ROOT, "transformed");
export const PROCESSED = join(SYNTHETIC_ROOT, "processed");

export async function detachAll(request: APIRequestContext): Promise<void> {
  for (const source of await (await request.get("/api/sources")).json()) await request.delete(`/api/sources/${source.id}`);
}

export async function pageScrolls(page: Page): Promise<boolean> {
  return page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight);
}

/** Attach the synthetic transformed source and open a session in the replay, which the Data and Sessions pages do by hand in their own flows. */
export async function openReplay(page: Page, request: APIRequestContext, sessionId: string): Promise<void> {
  const source = await (await request.post("/api/sources", { data: { path: TRANSFORMED, kind: "transformed", processed_path: PROCESSED } })).json();
  await page.goto("/");
  await page.evaluate(
    ([s, id]) => localStorage.setItem("ratreplay-source", JSON.stringify({ id: s.id, kind: s.kind, path: s.path, counts: s.counts, sessionId: id })),
    [source, sessionId] as const,
  );
  await page.goto("/#/replay");
  await page.reload(); // the page read its selection when it booted
  await expect(page.getByTestId("tile-frame")).toHaveText("1"); // the session has loaded
}

/** Take the reviews a test saved away again, so the next test sees the sessions as the processor left them. */
export function removeReviews(): void {
  rmSync(join(PROCESSED, "review"), { recursive: true, force: true });
}
