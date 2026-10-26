// Captures every page of the running app in light and dark mode for the project report (docs/screenshots).
// Run: npx playwright test -c playwright.docs.config.ts
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const OUT = path.resolve(process.cwd(), "..", "docs", "screenshots"); // run from /frontend
const H = { "X-Requested-With": "IntelliMetrics", "Content-Type": "application/json" };
const CREDS = { admin: ["admin@intellimetrics.demo", "Admin@12345"], reviewer: ["reviewer@intellimetrics.demo", "Reviewer@12345"], analyst: ["analyst@intellimetrics.demo", "Analyst@12345"], business: ["business@intellimetrics.demo", "Business@12345"] } as const;
const manifest: { theme: string; file: string; title: string; path: string }[] = [];

async function shot(page: Page, theme: string, n: number, slug: string, title: string, full = true) {
  const dir = path.join(OUT, theme);
  fs.mkdirSync(dir, { recursive: true });
  await page.waitForTimeout(1800); // pages poll in the background, so "networkidle" never settles
  const file = `${String(n).padStart(2, "0")}_${slug}.png`;
  await page.screenshot({ path: path.join(dir, file), fullPage: full });
  manifest.push({ theme, file, title, path: new URL(page.url()).pathname });
}

async function login(page: Page, who: keyof typeof CREDS) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(CREDS[who][0]);
  await page.getByTestId("login-password").fill(CREDS[who][1]);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/app\/dashboard/);
}

async function api(page: Page, method: "get" | "post", url: string, data?: unknown) {
  const r = await page.request[method](url, { headers: H, data: data as any });
  expect(r.ok(), `${method} ${url}`).toBeTruthy();
  return r.json();
}

test("capture all pages in both themes", async ({ browser }) => {
  // ---------- one-time state through the real UI/API so screenshots show real data
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await login(page, "reviewer");
    await api(page, "post", "/api/conflicts/detect");
    await ctx.close();
    const c2 = await browser.newContext();
    const p2 = await c2.newPage();
    await login(p2, "analyst");
    await api(p2, "post", "/api/evaluation/run");
    await c2.close();
  }

  for (const theme of ["light", "dark"] as const) {
    // ---------- public pages
    const pub = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await pub.addInitScript((t) => localStorage.setItem("im-theme", t), theme);
    const p = await pub.newPage();
    const publicPages: [string, string, string][] = [["/", "landing", "Landing page"], ["/about", "about", "About / product tour"], ["/login", "login", "Login with demo accounts panel"], ["/register", "register", "Register"], ["/forgot-password", "forgot_password", "Forgot password"], ["/reset-password?token=demo", "reset_password", "Reset password"], ["/403", "forbidden_403", "403 Forbidden"], ["/no-such-page", "not_found_404", "404 Not found"]];
    let n = 1;
    for (const [u, slug, title] of publicPages) {
      await p.goto(u);
      await shot(p, theme, n++, slug, title);
    }
    await pub.close();

    // ---------- app pages (admin sees everything)
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await ctx.addInitScript((t) => localStorage.setItem("im-theme", t), theme);
    const page = await ctx.newPage();
    await login(page, "admin");
    const metrics = (await api(page, "get", "/api/metrics?q=Revenue&page_size=50")).items;
    const revenue = metrics.find((m: any) => m.name === "Revenue" && m.is_live);
    const datasets = (await api(page, "get", "/api/datasets?page_size=50")).items;
    const sales = datasets.find((d: any) => d.name === "sales_transactions");
    const conflicts = (await api(page, "get", "/api/conflicts?status=active&page_size=50")).items;
    const finConflict = conflicts.find((c: any) => c.metric_b.department === "Finance" && c.metric_key === "revenue") || conflicts[0];
    const dashboards = (await api(page, "get", "/api/dashboards")).items;
    const salesDash = dashboards.find((d: any) => d.name === "Sales Overview");

    const plain: [string, string, string][] = [
      ["/app/dashboard", "dashboard", "Main dashboard"], ["/app/metrics", "metrics_catalog", "Metrics catalog"], [`/app/metrics/${revenue.id}`, "metric_detail", "Metric detail (Revenue)"],
      ["/app/datasets", "datasets_catalog", "Datasets catalog"], [`/app/datasets/${sales.id}`, "dataset_detail", "Dataset detail (preview)"], ["/app/connections", "connections", "Database connections"],
      ["/app/conflicts", "conflict_center", "Conflict detection center"], [`/app/conflicts/${finConflict.id}`, "conflict_detail", "Conflict detail (side-by-side)"],
      [`/app/versions/${revenue.id}`, "version_control", "Version control (Revenue history)"], ["/app/dashboards", "dashboards_list", "Saved dashboards and templates"],
      [`/app/dashboards/${salesDash.id}`, "dashboard_builder", "Dashboard builder (Sales Overview)"], ["/app/evaluation", "evaluation", "Performance evaluation"], ["/app/reports", "reports", "Reports and exports"],
      ["/app/profile", "profile", "User profile"], ["/app/admin/users", "admin_users", "Workspace and user management"], ["/app/admin/audit", "audit_log", "Audit log"], ["/app/settings", "settings", "Application settings"], ["/app/notifications", "activity", "Notifications and activity"],
    ];
    n = 20;
    const slugOrder = plain.map((x) => x[1]);
    for (const [u, slug, title] of plain) {
      await page.goto(u);
      if (slug === "dashboard_builder") await expect(page.getByTestId("kpi-widget").first()).toBeVisible({ timeout: 30_000 });
      if (slug === "evaluation") await expect(page.getByText("Conflict precision")).toBeVisible();
      await shot(page, theme, n + slugOrder.indexOf(slug), slug, title);
    }
    n = 20 + plain.length;

    // TARA metric generator with a real suggestion
    await page.goto("/app/generator");
    await expect(page.getByTestId("gen-dataset").locator("option")).not.toHaveCount(1);
    await page.getByTestId("gen-dataset").selectOption({ label: "sales_transactions" });
    await page.getByTestId("gen-prompt").fill("Number of distinct customers who ordered in the South region");
    await page.getByTestId("gen-submit").click();
    await expect(page.getByTestId("gen-result")).toBeVisible({ timeout: 30_000 });
    await shot(page, theme, n++, "tara_metric_generator", "TARA metric generator (offline deterministic mode, editable suggestion)");

    // Formula Lab with a real execution
    await page.goto("/app/lab");
    await expect(page.getByTestId("lab-dataset").locator("option")).not.toHaveCount(1, { timeout: 20_000 });
    await page.getByTestId("lab-dataset").selectOption({ label: "sales_transactions" });
    await page.getByTestId("lab-formula").fill("[Revenue] - SUM(refund_amount)");
    await expect.poll(async () => (await page.getByTestId("lab-dim").locator("option").allTextContents()).includes("state"), { timeout: 20_000 }).toBe(true);
    await page.getByTestId("lab-dim").selectOption({ label: "state" });
    await page.getByTestId("lab-run").click();
    await expect(page.getByTestId("lab-result")).toBeVisible({ timeout: 30_000 });
    await shot(page, theme, n++, "formula_lab", "Formula Lab: validate and execute (Revenue less refunds by state)");
    await page.getByTestId("lab-formula").fill("SUM(net_sales); DROP TABLE users");
    await page.getByTestId("lab-dim").selectOption({ index: 0 });
    await page.getByTestId("lab-run").click();
    await expect(page.getByTestId("lab-error")).toBeVisible();
    await shot(page, theme, n++, "formula_lab_rejected", "Formula Lab rejecting an injection attempt");

    // Ask TARA conversation
    await page.goto("/app/ask");
    await expect(page.getByTestId("suggestion").first()).toBeVisible();
    await shot(page, theme, n++, "ask_tara_empty", "Ask TARA: suggested Indian questions");
    for (const q of ["What was net revenue by month in the last quarter of this financial year?", "What is the UPI vs COD split by region?", "Compare Diwali-season sales with the previous quarter"]) {
      await page.getByTestId("ask-input").fill(q);
      await page.getByTestId("ask-send").click();
      await expect(page.getByTestId("assistant-msg").last()).toContainText(/₹|COD|Diwali/, { timeout: 30_000 });
      await page.waitForTimeout(1500);
    }
    await shot(page, theme, n++, "ask_tara_conversation", "Ask TARA: answers with chart, table, sources and applied filters");

    // dashboard builder in edit mode
    await page.goto(`/app/dashboards/${salesDash.id}`);
    await expect(page.getByTestId("kpi-widget").first()).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("dash-edit").click();
    await shot(page, theme, n++, "dashboard_builder_edit", "Dashboard builder in edit mode (drag handles)");

    // conflict detail after resolution flow is covered by E2E; metric versions diff tab
    await page.goto(`/app/versions/${revenue.id}`);
    await page.getByRole("tab", { name: "Compare" }).click();
    await shot(page, theme, n++, "version_compare", "Version compare (diff view)");
    await ctx.close();
  }

  // ---------- mobile samples
  for (const theme of ["light", "dark"] as const) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
    await ctx.addInitScript((t) => localStorage.setItem("im-theme", t), theme);
    const page = await ctx.newPage();
    await page.goto("/");
    await shot(page, theme, 90, "mobile_landing", "Mobile: landing page", false);
    await login(page, "admin");
    await shot(page, theme, 91, "mobile_dashboard", "Mobile: dashboard", false);
    await page.goto("/app/ask");
    await shot(page, theme, 92, "mobile_ask_tara", "Mobile: Ask TARA", false);
    await ctx.close();
  }
  fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify(manifest, null, 1));
  expect(manifest.length).toBeGreaterThan(70);
});
