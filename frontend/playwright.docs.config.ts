import { defineConfig, devices } from "@playwright/test";
import base from "./playwright.config";

// Documentation screenshot run: same isolated servers as the E2E suite, different test directory.
export default defineConfig({
  ...base,
  testDir: "./e2e-docs",
  timeout: 1_500_000,
  reporter: [["list"]],
  projects: [{ name: "docs", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
