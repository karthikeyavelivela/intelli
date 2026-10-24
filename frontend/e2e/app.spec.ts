import { expect, test } from "@playwright/test";
import { login, pick, USERS } from "./helpers";

test.describe.configure({ mode: "serial" });

test("login: demo panel fills the form, bad password is rejected, logout works", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("region", { name: "Demo accounts" })).toBeVisible();
  await page.getByTestId("login-email").fill(USERS.admin[0]);
  await page.getByTestId("login-password").fill("wrong-password1");
  await page.getByTestId("login-submit").click();
  await expect(page.getByRole("alert")).toContainText("Invalid email or password");

  await page.getByTestId("demo-data-analyst").click();
  await expect(page.getByTestId("login-email")).toHaveValue(USERS.analyst[0]);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/app\/dashboard/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Diya");
  await expect(page.getByText("Total metrics")).toBeVisible();

  await page.getByTestId("user-menu").click();
  await page.getByTestId("logout").click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/app/metrics");
  await expect(page).toHaveURL(/\/login/); // route is protected again
});

test("every demo account can sign in and sees role-appropriate navigation", async ({ page }) => {
  for (const [who, nav, hidden] of [
    ["admin", "Users & workspace", null],
    ["analyst", "Metric generator", "Users & workspace"],
    ["business", "Ask TARA", "Formula Lab"],
    ["reviewer", "Conflict center", "Connections"],
  ] as const) {
    await login(page, who);
    await expect(page.getByRole("navigation", { name: "Primary" }).getByText(nav, { exact: true })).toBeVisible();
    if (hidden) await expect(page.getByRole("navigation", { name: "Primary" }).getByText(hidden, { exact: true })).toHaveCount(0);
    await page.getByTestId("user-menu").click();
    await page.getByTestId("logout").click();
    await expect(page).toHaveURL(/\/login/);
  }
});

test("forbidden routes show the 403 page", async ({ page }) => {
  await login(page, "business");
  await page.goto("/app/lab");
  await expect(page.getByRole("heading", { name: "You don't have access" })).toBeVisible();
  await page.goto("/app/definitely-missing");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});

test("theme toggle: light / dark / system persist with no flash", async ({ page }) => {
  await page.goto("/");
  const html = page.locator("html");
  await page.getByRole("radio", { name: "Dark theme" }).first().click();
  await expect(html).toHaveClass(/dark/);
  expect(await page.evaluate(() => localStorage.getItem("im-theme"))).toBe("dark");
  await page.reload();
  await expect(html).toHaveClass(/dark/);
  await page.getByRole("radio", { name: "Light theme" }).first().click();
  await expect(html).not.toHaveClass(/dark/);
  await page.reload();
  await expect(html).not.toHaveClass(/dark/);
  await page.getByRole("radio", { name: "System theme" }).first().click();
  expect(await page.evaluate(() => localStorage.getItem("im-theme"))).toBe("system");
  // pre-paint script applies the stored choice before React mounts
  await page.addInitScript(() => localStorage.setItem("im-theme", "dark"));
  await page.goto("/login");
  expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
});

test("upload dataset: background processing with progress, then profiling", async ({ page }) => {
  await login(page, "analyst");
  await page.goto("/app/datasets");
  await page.getByTestId("upload-open").click();
  const rows = ["order_id,order_date,region,amount"];
  for (let i = 1; i <= 3000; i++) rows.push(`${i},2025-0${(i % 9) + 1}-1${i % 9},${["EU", "US", "APAC"][i % 3]},${(i * 1.25).toFixed(2)}`);
  await page.getByTestId("upload-input").setInputFiles({ name: "e2e_orders.csv", mimeType: "text/csv", buffer: Buffer.from(rows.join("\n")) });
  await page.getByTestId("upload-name").fill("E2E Orders");
  await page.getByTestId("upload-submit").click();
  await expect(page).toHaveURL(/\/app\/datasets\/[0-9a-f]{32}/);
  await expect(page.getByText("Ready").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("3,000").first()).toBeVisible();
  await page.getByRole("tab", { name: "Profiling" }).click();
  await expect(page.getByRole("cell", { name: "order_date" })).toBeVisible();
  await page.getByRole("tab", { name: "Schema" }).click();
  await expect(page.getByText("default date column")).toBeVisible();
});

test("create metric: live validation, save draft, submit for approval", async ({ page }) => {
  await login(page, "analyst");
  await page.goto("/app/metrics");
  await page.getByTestId("new-metric").click();
  await page.getByTestId("mf-name").fill("E2E Units");
  await pick(page.getByTestId("mf-dataset"), "sales_transactions");
  await page.getByTestId("mf-formula").fill("SUM(nonexistent)");
  await expect(page.getByTestId("validation-panel")).toContainText("Unknown column", { timeout: 15_000 });
  await page.getByTestId("mf-formula").fill("SUM(quantity)");
  await expect(page.getByTestId("validation-panel")).toHaveAttribute("data-ok", "true", { timeout: 15_000 });
  await page.getByTestId("mf-unit").fill("units");
  await page.getByTestId("mf-save").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("E2E Units");
  await page.getByTestId("submit-review").click();
  await page.getByTestId("dialog-confirm").click();
  await expect(page.getByText("In review").first()).toBeVisible();
});

test("detect conflict -> assign -> review -> approve -> resolve creates a new version", async ({ page }) => {
  await login(page, "reviewer");
  await page.goto("/app/conflicts");
  await page.getByTestId("detect").click();
  const row = page.getByRole("row", { name: /vs Finance/ }).first();
  await expect(row).toBeVisible({ timeout: 20_000 });
  await expect(row).toContainText("formula");
  await expect(page.getByRole("row", { name: /vs Marketing/ }).first()).toBeVisible(); // the GST-inclusive Revenue conflict
  await row.click();
  await expect(page).toHaveURL(/\/app\/conflicts\/[0-9a-f]{32}/);
  await expect(page.getByRole("heading", { name: "Formula diff" })).toBeVisible();
  await expect(page.getByText("deterministic check").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recommended resolution" })).toBeVisible();

  await page.getByTestId("assign").click();
  await pick(page.getByTestId("assignee"), "Meera Iyer");
  await page.getByTestId("assign-confirm").click();
  await page.getByTestId("start-review").click();
  await page.getByTestId("approve-conflict").click();
  await page.getByTestId("resolve").click();
  await page.getByTestId("new-name").fill("Net Revenue (E2E)");
  await page.getByTestId("resolve-note").fill("Finance reports net of refunds");
  await page.getByTestId("resolve-confirm").click();
  await expect(page.getByRole("heading", { name: "Audit history" })).toBeVisible();
  await expect(page.getByRole("list").getByText("resolve", { exact: true }).first()).toBeVisible();

  await page.goto("/app/metrics");
  await page.getByTestId("metric-search").fill("Net Revenue (E2E)");
  await expect(page.getByRole("row", { name: /Net Revenue \(E2E\)/ })).toContainText("v2");
});

test("formula lab: executes safely and rejects injection", async ({ page }) => {
  await login(page, "analyst");
  await page.goto("/app/lab");
  await pick(page.getByTestId("lab-dataset"), "sales_transactions");
  await page.getByTestId("lab-formula").fill("SUM(net_sales)");
  await page.getByTestId("lab-run").click();
  await expect(page.getByTestId("lab-result")).toContainText("Rows scanned");
  await expect(page.getByTestId("lab-value")).toHaveText(/^[\d,]+\.\d{2}$/);
  await expect(page.getByTestId("lab-result")).toContainText("62,000");

  await page.getByTestId("lab-formula").fill("SUM(net_sales); DROP TABLE users");
  await page.getByTestId("lab-run").click();
  await expect(page.getByTestId("lab-error")).toContainText("Unexpected character");
  await expect(page.getByTestId("lab-error")).toContainText("Nothing was executed");

  await page.getByTestId("lab-formula").fill("SUM(net_sales)");
  await pick(page.getByTestId("lab-dim"), "region");
  await page.getByTestId("lab-run").click();
  await expect(page.getByTestId("lab-result").getByRole("cell", { name: "South", exact: true })).toBeVisible();
});

test("ask TARA: Indian fiscal-calendar answers in INR with table, chart and sources", async ({ page }) => {
  await login(page, "business");
  await page.goto("/app/ask");
  await expect(page.getByTestId("suggestion")).toHaveCount(8);
  await page.getByTestId("suggestion").filter({ hasText: "last quarter of this financial year" }).click();
  const msg = page.getByTestId("assistant-msg").last();
  await expect(msg).toContainText("Revenue by month", { timeout: 30_000 });
  await expect(msg).toContainText("Q2 FY");
  await expect(msg).toContainText("₹");
  await expect(msg.getByRole("table")).toBeVisible();
  await expect(msg.locator("tbody tr")).toHaveCount(3);
  await expect(msg.getByRole("img", { name: /line chart/i })).toBeVisible();
  await expect(msg).toContainText("Source:");

  await page.getByTestId("ask-input").fill("Which 5 states had the highest sales this year?");
  await page.getByTestId("ask-send").click();
  await expect(page.getByTestId("assistant-msg").last().locator("tbody tr")).toHaveCount(5, { timeout: 30_000 });
  await expect(page.getByTestId("assistant-msg").last()).toContainText("Maharashtra");

  await page.getByTestId("ask-input").fill("What is the UPI vs COD split by region?");
  await page.getByTestId("ask-send").click();
  const split = page.getByTestId("assistant-msg").last();
  await expect(split.getByRole("img", { name: /grouped bar chart/i })).toBeVisible({ timeout: 30_000 });
  await expect(split).toContainText("share of region");

  await page.getByTestId("ask-input").fill("Compare Diwali-season sales with the previous quarter");
  await page.getByTestId("ask-send").click();
  await expect(page.getByTestId("assistant-msg").last()).toContainText("Diwali season", { timeout: 30_000 });
  await expect(page.getByTestId("assistant-msg").last()).toContainText("per day");

  await page.getByTestId("ask-input").fill("What is the weather in Paris?");
  await page.getByTestId("ask-send").click();
  await expect(page.getByTestId("assistant-msg").last()).toContainText("couldn't match", { timeout: 20_000 });
  await page.getByTestId("ask-input").fill("How many orders did we have last month?");
  await page.getByTestId("ask-send").click();
  await expect(page.getByTestId("kpi-value").last()).toBeVisible({ timeout: 20_000 });
});

test("landing page: no pricing anywhere, University Project badge, rupee figures", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("university-badge")).toBeVisible();
  await expect(page.getByTestId("university-note")).toContainText("synthetic");
  const text = (await page.locator("body").innerText()).toLowerCase();
  for (const banned of ["pricing", "per month", "free trial", "upgrade", "contact sales", "billing", "subscription"]) expect(text).not.toContain(banned);
  await expect(page.getByRole("link", { name: /pricing/i })).toHaveCount(0);
  expect(text).toContain("₹");
  await page.getByRole("link", { name: "About this project" }).first().click();
  await expect(page.getByTestId("about-project")).toContainText("Devi Priya");
});

test("Indian formatting on the dashboard: rupee, lakh/crore grouping and DD-MMM-YYYY", async ({ page }) => {
  await login(page, "admin");
  await expect(page.getByText("Bharat Retail Pvt Ltd").first()).toBeVisible();
  await expect(page.getByText("Demonstration data (synthetic)").first()).toBeVisible();
  await page.goto("/app/dashboards");
  await page.getByTestId("dashboard-card").filter({ hasText: "Sales Overview" }).click();
  const kpi = page.getByTestId("kpi-widget").first();
  await expect(kpi).toHaveText(/^₹\d{1,2}(,\d{2})*,\d{3}$/, { timeout: 30_000 }); // e.g. Rs 20,41,06,264 (lakh/crore grouping)
  await page.goto("/app/admin/audit");
  await expect(page.getByRole("cell", { name: /^\d{2}-[A-Z][a-z]{2}-\d{4} \d{2}:\d{2} IST$/ }).first()).toBeVisible();
});

test("build dashboard: template, edit layout, add widget, save, export menu", async ({ page }) => {
  await login(page, "analyst");
  await page.goto("/app/dashboards");
  await page.getByTestId("use-template-operations").click();
  await expect(page).toHaveURL(/\/app\/dashboards\/[0-9a-f]{32}/);
  await expect(page.getByTestId("kpi-widget").first()).toBeVisible({ timeout: 30_000 });
  const before = await page.getByTestId("widget").count();
  await page.getByTestId("dash-edit").click();
  await page.getByTestId("add-widget").click();
  await page.getByTestId("wtype-bar").click();
  await pick(page.getByTestId("widget-metric"), "Refunds");
  await page.getByTestId("widget-save").click();
  await expect(page.getByTestId("widget")).toHaveCount(before + 1);
  await page.getByTestId("dash-range").selectOption("last_90_days");
  await page.getByTestId("dash-save").click();
  await expect(page.getByText("unsaved changes")).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("widget")).toHaveCount(before + 1);
  await page.getByRole("button", { name: "Export" }).click();
  await expect(page.getByRole("menuitem", { name: "CSV data" })).toBeVisible();
});

test("register a new workspace and reset password link flow", async ({ page }) => {
  const email = `e2e${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByTestId("reg-name").fill("E2E Person");
  await page.getByTestId("reg-email").fill(email);
  await page.getByTestId("reg-workspace").fill("E2E Workspace");
  await page.getByTestId("reg-password").fill("Passw0rd!x1");
  await page.getByTestId("reg-submit").click();
  await expect(page).toHaveURL(/\/app\/dashboard/);
  await expect(page.getByText("E2E Workspace").first()).toBeVisible();
  await page.getByTestId("user-menu").click();
  await page.getByTestId("logout").click();
  await page.goto("/forgot-password");
  await page.getByTestId("forgot-email").fill(email);
  await page.getByTestId("forgot-submit").click();
  await expect(page.getByTestId("dev-reset-banner")).toBeVisible();
  await page.getByTestId("dev-reset-link").click();
  await page.getByTestId("reset-password").fill("N3wPassw0rd!");
  await page.getByTestId("reset-password2").fill("N3wPassw0rd!");
  await page.getByTestId("reset-submit").click();
  await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  await page.getByTestId("login-email").fill(email);
  await page.getByTestId("login-password").fill("N3wPassw0rd!");
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/app\/dashboard/);
});
