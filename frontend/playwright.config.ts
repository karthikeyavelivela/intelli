import { defineConfig, devices } from "@playwright/test";

const API = process.env.E2E_API_PORT || "8100";
const WEB = process.env.E2E_WEB_PORT || "5273";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: `http://127.0.0.1:${WEB}`, trace: "retain-on-failure", screenshot: "only-on-failure", viewport: { width: 1440, height: 900 } },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    { command: "node e2e/start-backend.mjs", url: `http://127.0.0.1:${API}/health`, timeout: 120_000, reuseExistingServer: !process.env.CI },
    {
      command: `npx vite --port ${WEB} --host 127.0.0.1 --strictPort`,
      url: `http://127.0.0.1:${WEB}`,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: { VITE_API_PROXY: `http://127.0.0.1:${API}` },
    },
  ],
});
