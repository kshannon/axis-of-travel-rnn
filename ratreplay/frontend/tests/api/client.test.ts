import { afterEach, expect, test, vi } from "vitest";
import { ApiError, errorText, getHealth } from "../../src/api/client";

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
