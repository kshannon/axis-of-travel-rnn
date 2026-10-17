import { defineConfig } from "@playwright/test";
import { PORT, SYNTHETIC_ROOT } from "./e2e/synthetic";

const BASE_URL = `http://127.0.0.1:${PORT}`;

// The API serves the built frontend, so run npm run build first. It runs on synthetic folders rebuilt under
// SYNTHETIC_ROOT, named by a local.yaml there, so no real data and not the repository's configs/local.yaml is touched.
// The tests share that server, so they run one at a time and each puts back what it changed.
export default defineConfig({
  testDir: "e2e",
  workers: 1,
  use: { baseURL: BASE_URL, viewport: { width: 1440, height: 900 } },
  webServer: {
    command: `python e2e/serve_synthetic.py --root ${SYNTHETIC_ROOT} --port ${PORT}`,
    url: BASE_URL,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
