import { afterEach, expect, test, vi } from "vitest";
import { ApiError, errorText, getSources, putWindowSettings } from "./client";

afterEach(() => vi.unstubAllGlobals());

function answer(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status })));
}

test("a refused request throws the API's error text with the status", async () => {
  answer(400, { error: "TRANSFORMED_LAB_DATA is not set in /x/local.yaml" });
  const failure = await getSources().catch((error) => error);
  expect(failure).toBeInstanceOf(ApiError);
  expect(failure.status).toBe(400);
  expect(errorText(failure)).toBe("TRANSFORMED_LAB_DATA is not set in /x/local.yaml");
});

test("a body is sent as json", async () => {
  answer(200, {});
  await putWindowSettings({ window_s: 40 } as never);
  const [url, init] = vi.mocked(fetch).mock.calls[0];
  expect(url).toBe("/api/windows/settings");
  expect(init?.method).toBe("PUT");
  expect(JSON.parse(init?.body as string)).toEqual({ settings: { window_s: 40 } });
});

test("only a request that cannot be made says the API is unreachable, a bug in the page says what it is", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
  const failure = await getSources().catch((error) => error);
  expect(errorText(failure)).toMatch(/Cannot reach the API/);
  expect(errorText(new TypeError("undefined is not a function"))).toBe("TypeError: undefined is not a function");
});

test("the sources are read again from the config file only when asked", async () => {
  answer(200, {});
  await getSources();
  await getSources(true);
  expect(vi.mocked(fetch).mock.calls.map(([url]) => url)).toEqual(["/api/sources", "/api/sources?reload=true"]);
});
