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
// What environmentPixels counts on a map: the track's walls and centerline give 2000 and more, the arena's ring about 650,
// and a map without the environment 350 at most, the letters of the site names and of the speed legend.
export const WALL_PIXELS = 1000;
export const RING_PIXELS = 400;
export const SETTINGS_FILE = join(SYNTHETIC_ROOT, "lab_blocks.yaml");

export async function detachAll(request: APIRequestContext): Promise<void> {
  for (const source of await (await request.get("/api/sources")).json()) await request.delete(`/api/sources/${source.id}`);
}

export async function pageScrolls(page: Page): Promise<boolean> {
  return page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight);
}

/** Attach the synthetic transformed source, paired with its processed folder, and select it with a session open, as the Data and Sessions pages do by hand in their own flows. Gives back the source's id. */
export async function selectSource(page: Page, request: APIRequestContext, sessionId = ""): Promise<string> {
  const source = await (await request.post("/api/sources", { data: { path: TRANSFORMED, kind: "transformed", processed_path: PROCESSED } })).json();
  await page.goto("/");
  await page.evaluate(
    ([s, id]) => localStorage.setItem("ratreplay-source", JSON.stringify({ id: s.id, kind: s.kind, path: s.path, counts: s.counts, sessionId: id })),
    [source, sessionId] as const,
  );
  return source.id;
}

/** Select the synthetic source and open a session in the replay. */
export async function openReplay(page: Page, request: APIRequestContext, sessionId: string): Promise<void> {
  await selectSource(page, request, sessionId);
  await page.goto("/#/replay");
  await page.reload(); // the page read its selection when it booted
  await expect(page.getByTestId("tile-frame")).toHaveText("1"); // the session has loaded
}

// The synthetic processed dataset has three blocks of 20 s at 60 Hz: the arena and the track block of S1 and the track block of S6.
// At the default 40 s window none yields a window. At a 5 s window the first two are ok and S6's track block has no complete trip.
export const S1_TRACK = "NS14_rec1_20150101_001_track_01";
export const S1_ARENA = "NS14_rec1_20150101_001_arena_01";
export const S6_TRACK = "NS16_rec6_20150106_001_track_01";

/** Select the synthetic source and open the Blocks page with its index loaded. */
export async function openBlocks(page: Page, request: APIRequestContext): Promise<void> {
  await selectSource(page, request);
  await page.goto("/#/blocks");
  await page.reload(); // the page read its selection when it booted
  await expect(page.getByRole("row")).toHaveCount(4); // the header and the three blocks
}

/** Test the blocks at a 5 s window and open the block of S1's track on the Blocks page. */
export async function openTrackBlock(page: Page, request: APIRequestContext): Promise<void> {
  await openBlocks(page, request);
  await page.getByLabel("window (s)").fill("5");
  await page.getByRole("button", { name: "Test on all blocks" }).click();
  await page.getByRole("button", { name: `Open ${S1_TRACK}` }).click();
  await expect(page.getByTestId("block-id")).toHaveText(S1_TRACK);
}

/** The pixels of the map in the theme's muted colour, which is what the walls, the arena's boundary and the centerline are drawn in, and the letters of the site names and of the speed legend. */
export async function environmentPixels(page: Page): Promise<number> {
  return page.getByTestId("map").locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
    const muted = getComputedStyle(document.documentElement).getPropertyValue("--muted").trim();
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(muted.slice(i, i + 2), 16));
    const { data } = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height);
    let count = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] > 200 && Math.abs(data[i] - r) < 8 && Math.abs(data[i + 1] - g) < 8 && Math.abs(data[i + 2] - b) < 8) count++;
    }
    return count;
  });
}

/** Take the reviews a test saved away again, so the next test sees the sessions as the processor left them. */
export function removeReviews(): void {
  rmSync(join(PROCESSED, "review"), { recursive: true, force: true });
}

/** Take the window settings a test saved away again, so the next test starts from the project's defaults. */
export function removeSettings(): void {
  rmSync(SETTINGS_FILE, { force: true });
}
