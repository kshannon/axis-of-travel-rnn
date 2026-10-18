import { afterEach, expect, test, vi } from "vitest";
import { ApiError, errorText, FORMAT_VERSION, getHealth, STALE_API, staleApi } from "../../src/api/client";

afterEach(() => vi.unstubAllGlobals());

function answer(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status })));
}

test("a refused request throws the API's error text with the status", async () => {
  answer(400, { error: "TRANSFORMED_LAB_DATA is not set in /x/local.yaml" });
  const failure = await getHealth().catch((error) => error);
  expect(failure).toBeInstanceOf(ApiError);
  expect(failure.status).toBe(400);
  expect(errorText(failure)).toBe("TRANSFORMED_LAB_DATA is not set in /x/local.yaml");
});

test("only a request that cannot be made says the API is unreachable, a bug in the page says what it is", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
  const failure = await getHealth().catch((error) => error);
  expect(errorText(failure)).toMatch(/Cannot reach the API/);
  expect(errorText(new TypeError("undefined is not a function"))).toBe("TypeError: undefined is not a function");
});

test("the API is older than the page when its format is another version or lacks a key the pages read", () => {
  const format = { version: FORMAT_VERSION, transformed: { files: [] }, processed: { files: [] }, settings: {}, rules: {} } as never;
  expect(staleApi(format)).toBe(false);
  expect(staleApi({ ...(format as object), version: FORMAT_VERSION + 1 } as never)).toBe(true);
  expect(staleApi({ ...(format as object), rules: undefined } as never)).toBe(true);
  expect(staleApi({ ...(format as object), settings: undefined } as never)).toBe(true);
  expect(STALE_API).toBe("The API is older than this page, restart it (pixi run ratreplay-api)");
});
