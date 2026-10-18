import { afterEach, expect, test, vi } from "vitest";
import { ApiError, errorText, getHealth, getSession, listBlocks, rebuildAll } from "./client";

afterEach(() => vi.unstubAllGlobals());

function answer(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status })));
}

const urls = () => vi.mocked(fetch).mock.calls.map(([url]) => url);

test("a refused request throws the API's error text with the status", async () => {
  answer(400, { error: "TRANSFORMED_LAB_DATA is not set in /x/local.yaml" });
  const failure = await getHealth().catch((error) => error);
  expect(failure).toBeInstanceOf(ApiError);
  expect(failure.status).toBe(400);
  expect(errorText(failure)).toBe("TRANSFORMED_LAB_DATA is not set in /x/local.yaml");
});

test("a body is sent as json", async () => {
  answer(200, {});
  await rebuildAll({ window_s: 40 } as never);
  const [url, init] = vi.mocked(fetch).mock.calls[0];
  expect(url).toBe("/api/rebuild");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(init?.body as string)).toEqual({ settings: { window_s: 40 } });
});

test("only a request that cannot be made says the API is unreachable, a bug in the page says what it is", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
  const failure = await getHealth().catch((error) => error);
  expect(errorText(failure)).toMatch(/Cannot reach the API/);
  expect(errorText(new TypeError("undefined is not a function"))).toBe("TypeError: undefined is not a function");
});

test("the folders are read again from the config file only when asked", async () => {
  answer(200, {});
  await getHealth();
  await getHealth(true);
  expect(urls()).toEqual(["/api/health", "/api/health?reload=true"]);
});

test("the window settings travel as query parameters on a GET, the dataset beside them", async () => {
  answer(200, {});
  await getSession("S1");
  await getSession("S1", { window_s: 5, rate_hz: 20 });
  await listBlocks({ stride_s: 2.5 });
  expect(urls()).toEqual(["/api/sessions/S1", "/api/sessions/S1?window_s=5&rate_hz=20", "/api/blocks?which=real&stride_s=2.5"]);
});
