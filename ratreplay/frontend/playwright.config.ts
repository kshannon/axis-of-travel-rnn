import { defineConfig } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8060";

// The API serves the built frontend, so run npm run build first.
export default defineConfig({
  testDir: "e2e",
  use: { baseURL: BASE_URL, viewport: { width: 1440, height: 900 } },
  webServer: { command: "python -m ratreplay_api", url: BASE_URL, reuseExistingServer: true },
});
