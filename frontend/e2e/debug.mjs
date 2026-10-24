// Usage: node e2e/debug.mjs <path> [tabName]  -- logs in as analyst against the dev servers and prints console/page errors
import { chromium } from "@playwright/test";

const base = process.env.BASE || "http://127.0.0.1:5173";
const [, , target = "/app/datasets", tab] = process.argv;
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message.split("\n")[0]));
page.on("console", (m) => m.type() === "error" && console.log("CONSOLE", m.text().slice(0, 300)));
await page.goto(base + "/login");
await page.getByTestId("login-email").fill(process.env.EMAIL || "analyst@intellimetrics.demo");
await page.getByTestId("login-password").fill(process.env.PW || "Analyst@12345");
await page.getByTestId("login-submit").click();
await page.waitForURL(/app\/dashboard/);
await page.goto(base + target);
await page.waitForTimeout(2500);
if (target === "/app/datasets") {
  await page.getByTestId("dataset-card").first().click();
  await page.waitForTimeout(2000);
}
if (tab) { await page.getByRole("tab", { name: tab }).click(); await page.waitForTimeout(1500); }
await page.screenshot({ path: process.env.SHOT || "debug.png", fullPage: false });
console.log("TITLE", await page.title(), "| h1:", await page.locator("h1").first().textContent().catch(() => null));
await b.close();
