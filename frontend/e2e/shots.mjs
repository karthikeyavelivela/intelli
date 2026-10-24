// Visual QA: screenshots every page in light + dark and reports console errors / failed requests / horizontal overflow.
// Usage: node e2e/shots.mjs [outDir]   (dev servers on 5173/8000 must be running)
import { chromium } from "@playwright/test";
import fs from "node:fs";

const base = process.env.BASE || "http://127.0.0.1:5173";
const out = process.argv[2] || "shots";
fs.mkdirSync(out, { recursive: true });
const PUBLIC = ["/", "/about", "/login", "/register", "/forgot-password", "/reset-password?token=abc", "/403", "/nothing-here"];
const APP = ["dashboard", "metrics", "conflicts", "versions", "datasets", "connections", "ask", "generator", "lab", "dashboards", "evaluation", "reports", "notifications", "admin/users", "admin/audit", "settings", "profile"];
const b = await chromium.launch();
const problems = [];

async function run(theme, viewport, tag, paths, loginAs) {
  const ctx = await b.newContext({ viewport, colorScheme: theme });
  await ctx.addInitScript((t) => localStorage.setItem("im-theme", t), theme);
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push("PAGEERROR " + e.message.split("\n")[0]));
  page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource: the server responded with a status of 40[13]/.test(m.text()) && errs.push("CONSOLE " + m.text().slice(0, 200)));
  page.on("response", (r) => { if (r.status() >= 500) errs.push(`HTTP ${r.status()} ${r.url()}`); });
  if (loginAs) {
    await page.goto(base + "/login");
    await page.getByTestId("login-email").fill(loginAs[0]);
    await page.getByTestId("login-password").fill(loginAs[1]);
    await page.getByTestId("login-submit").click();
    await page.waitForURL(/app\/dashboard/);
  }
  for (const p of paths) {
    errs.length = 0;
    await page.goto(base + p);
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.waitForTimeout(900);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    const name = `${tag}-${theme}-${p.replace(/[^a-z0-9]+/gi, "_")}`;
    await page.screenshot({ path: `${out}/${name}.png`, fullPage: false });
    const dark = await page.evaluate(() => document.documentElement.classList.contains("dark"));
    if (errs.length) problems.push(`${name}: ${errs.join(" | ")}`);
    if (overflow > 2) problems.push(`${name}: horizontal overflow ${overflow}px`);
    if ((theme === "dark") !== dark) problems.push(`${name}: theme class mismatch`);
  }
  await ctx.close();
}

const D = { width: 1440, height: 900 }, M = { width: 390, height: 844 };
const admin = ["admin@intellimetrics.demo", "Admin@12345"];
for (const theme of ["light", "dark"]) {
  await run(theme, D, "pub", PUBLIC, null);
  await run(theme, D, "app", APP.map((p) => "/app/" + p), admin);
}
await run("light", M, "mob", ["/", "/login"], null);
await run("dark", M, "mobapp", ["/app/dashboard", "/app/metrics", "/app/ask"], admin);
await b.close();
console.log(problems.length ? "PROBLEMS:\n" + problems.join("\n") : "NO PROBLEMS");
