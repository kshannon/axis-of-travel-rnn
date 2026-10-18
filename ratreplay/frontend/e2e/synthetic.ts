import { readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect } from "@playwright/test";
import type { APIRequestContext, Locator, Page, Response } from "@playwright/test";

export const PORT = 8061;

// serve_synthetic.py rebuilds this folder on every start: the transformed folder of six sessions, an empty processed folder and the local.yaml naming them.
export const SYNTHETIC_ROOT = join(tmpdir(), "ratreplay-e2e");
export const TRANSFORMED = join(SYNTHETIC_ROOT, "transformed");
export const PROCESSED = join(SYNTHETIC_ROOT, "processed");
export const LOCAL_CONFIG = join(SYNTHETIC_ROOT, "local.yaml");
// What environmentPixels counts on a map: the track's walls and centerline give 2000 and more, a map without the environment 350 at most, the letters of the site names and of the speed legend.
export const WALL_PIXELS = 1000;

// The two synthetic sessions in the dataset, 90 s at 60 Hz each. S1 has an arena block over lab frames 301 to 1500 and a track block over 2101 to 3300, S6 only a track block over 3001 to 4200. Every block lasts 20 s.
export const S1 = "NS14_rec1_20150101_001";
export const S6 = "NS16_rec6_20150106_001";
export const S1_TRACK = `${S1}_track_01`;
export const S6_TRACK = `${S6}_track_01`;

/** The reviewed folder and what the tool built from it go back to the empty folder the tool finds before its first save. */
export function resetProcessed(): void {
  for (const name of readdirSync(PROCESSED)) rmSync(join(PROCESSED, name), { recursive: true, force: true });
}

/** The config file as the server started with it, to put back after a test has changed it. */
export function readConfig(): string {
  return readFileSync(LOCAL_CONFIG, "utf8");
}

export function writeConfig(text: string): void {
  writeFileSync(LOCAL_CONFIG, text);
}

/** Review and build a session through the API alone, accepting every block the rules cut, as Accept all and Save blocks do on the Replay page. */
export async function saveThroughApi(request: APIRequestContext, sessionId: string): Promise<void> {
  const response = await request.put(`/api/sessions/${sessionId}/blocks`, { data: { edits: [{ op: "accept" }] } });
  expect(response.ok()).toBe(true);
}

/** The count tile of a folder card on the Data page, such as "reviews" on the processed card. */
export function countTile(card: Locator, label: string): Locator {
  return card.locator("dl > div").filter({ has: card.page().getByText(label, { exact: true }) }).locator("dd");
}

/** The next read of the folders' health the page makes, started before the click that ends in one so a test does not finish, and clear the folders, while the API is still reading them. */
export function nextHealth(page: Page): Promise<Response> {
  return page.waitForResponse((response) => new URL(response.url()).pathname === "/api/health");
}

/** The toast whose text contains this one, a success at the bottom or a warning or error in the stack at the top right. */
export function toast(page: Page, text: string): Locator {
  return page.getByRole("status").or(page.getByRole("alert")).filter({ hasText: text });
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
