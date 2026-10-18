import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

const API_URL = "http://127.0.0.1:8060";

export default defineConfig({
  plugins: [tailwindcss()],
  server: { proxy: { "/api": API_URL } },
  test: { include: ["tests/**/*.test.ts"] },
});
