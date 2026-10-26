<div class="titlepage"></div>

# User Guide and How To Run {.unnumbered .title-heading}

*Installing, running and using IntelliMetrics AI, with screenshots of every page*

| | |
|---|---|
| **Project title** | IntelliMetrics AI: A Governed Semantic Layer with TARA, an AI Assistant for Trusted Business Metrics |
| **Document** | User Guide and How To Run |
| **Team members** | Devi Priya, Priyanka, Akshay and Bhaskar |
| **Institution** | KL University |
| **Academic year** | 2026-27 |
| **Date** | 26-Oct-2026 (IST) |
| **Status** | University project: academic capstone with synthetic demonstration data |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

```{=html}
<div style="page-break-after:always"></div>
```



## Table of contents {.unnumbered}

- [1 About this guide](#sec-1)
- [2 What you need](#sec-2)
- [3 Run it without Docker (recommended, tested route)](#sec-3)
  - [3.1 Step 1: back end](#sec-3-1)
  - [3.2 Step 2: front end](#sec-3-2)
  - [3.3 Step 3: reset the demonstration at any time](#sec-3-3)
- [4 Run it with Docker Compose (not executed in development)](#sec-4)
- [5 Configuration](#sec-5)
- [6 Demonstration accounts](#sec-6)
  - [6.1 What each role can do](#sec-6-1)
- [7 Tour of the application](#sec-7)
  - [7.1 Public pages](#sec-7-1)
  - [7.2 Main application](#sec-7-2)
  - [7.3 Phone-sized screens](#sec-7-3)
- [8 A ten-minute walkthrough](#sec-8)
- [9 Understanding Indian conventions in the application](#sec-9)
- [10 Troubleshooting](#sec-10)
- [11 Running the tests](#sec-11)

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

```{=html}
<div style="page-break-after:always"></div>
```



# 1 About this guide {#sec-1}

IntelliMetrics AI is a **university project** (academic capstone) with synthetic demonstration data. This guide explains how to run it on a Windows computer, how to sign in, what each page does, and a ten-minute walkthrough that reproduces the main results. All screenshots were captured from the running application by the automated script `frontend/e2e-docs/screens.spec.ts`.

# 2 What you need {#sec-2}

| Requirement | Version used in development | Needed for |
|---|---|---|
| Python | 3.11 | Back end |
| Node.js and npm | Node 22 | Front end |
| A modern browser | Chrome or Edge | Using the application |
| Docker Desktop | not used on the development machine | Optional: the Compose route (Section 5) |

Everything else (database, analytics engine, background jobs) is installed by the commands below. **No internet connection is needed to run the application**, except to download the packages the first time and to show the stock photographs on the public pages (a gradient is shown instead when they cannot load). **No paid service, account or API key is required.**

# 3 Run it without Docker (recommended, tested route) {#sec-3}

This is the route that was run and tested for this report. It uses SQLite for application data and a background thread for dataset processing, so Redis and PostgreSQL are not needed.

## 3.1 Step 1: back end {#sec-3-1}

Open **PowerShell** in the project folder:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

`python -m app.seed` creates the database and the demonstration data (about 2.7 seconds on the development machine). Leave the window open. The API documentation is at <http://localhost:8000/docs> and the health check at <http://localhost:8000/health>.

## 3.2 Step 2: front end {#sec-3-2}

Open a **second** PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The development server forwards `/api` requests to port 8000.

## 3.3 Step 3: reset the demonstration at any time {#sec-3-3}

```powershell
scripts\reset-demo.ps1      # Windows
./scripts/reset-demo.sh     # Git Bash / Linux / macOS
```

This deletes the local database and uploaded files and seeds again. Stop the back end first, because Windows locks the SQLite file while it is running.

# 4 Run it with Docker Compose (not executed in development) {#sec-4}

```bash
cp .env.example .env     # set SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

Open <http://localhost:3000>. This starts PostgreSQL, Redis, the API, a Celery worker and an Nginx front end. **This path was written but has not been run**, because Docker is not installed on the development machine; the services it starts were each verified separately (see the Testing Report). If a step fails, the Deployment Guide has a troubleshooting table.

# 5 Configuration {#sec-5}

Settings are environment variables, listed in full in the Deployment Guide. The ones a student is likely to touch:

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `none` | `none` = TARA's offline deterministic mode (no key needed). `openai` or `gemini` plus the matching `*_API_KEY` turns on live AI planning |
| `AUTO_SEED` | `true` in `.env.example` | Seeds demo data when the database is empty |
| `USE_CELERY` | `false` | `true` uses Celery and Redis for dataset processing |
| `DATABASE_URL` | local SQLite file | Use a `postgresql://` URL for PostgreSQL |
| `MAX_UPLOAD_MB` | 500 | Upload size limit |

If no AI key is set, every TARA screen says that it is in **offline deterministic mode**. It still answers all the suggested questions below, because the questions are interpreted by a rule-based planner and the numbers always come from the data.

# 6 Demonstration accounts {#sec-6}

All accounts are marked **DEMO**, and the login page has a *Demo accounts* panel that fills the form when clicked.

| Role | Person (fictional) | Email | Password | Company |
|---|---|---|---|---|
| Admin | Aarav Menon | `admin@intellimetrics.demo` | `Admin@12345` | Bharat Retail Pvt Ltd |
| Data Analyst | Diya Reddy | `analyst@intellimetrics.demo` | `Analyst@12345` | Bharat Retail Pvt Ltd |
| Business User | Rohan Sharma | `business@intellimetrics.demo` | `Business@12345` | Bharat Retail Pvt Ltd |
| Reviewer | Meera Iyer | `reviewer@intellimetrics.demo` | `Reviewer@12345` | Bharat Retail Pvt Ltd |
| Admin (isolation demo) | Suresh Naidu | `admin@sagarfoods.demo` | `Admin@12345` | Sagar Foods & Beverages Ltd |
| Analyst (isolation demo) | Kavya Raju | `analyst@sagarfoods.demo` | `Analyst@12345` | Sagar Foods & Beverages Ltd |

The two companies are separate *workspaces*. Sign in as Suresh Naidu to confirm that none of Bharat Retail's metrics, datasets or conversations are visible.

## 6.1 What each role can do {#sec-6-1}

| Capability | Admin | Data Analyst | Business User | Reviewer |
|---|:-:|:-:|:-:|:-:|
| View metrics catalog, datasets, dashboards (`catalog.view`) | Yes | Yes | Yes | Yes |
| Upload datasets / manage connections (`dataset.write`) | Yes | Yes | - | - |
| Delete datasets and connections (`dataset.delete`) | Yes | - | - | - |
| Create and edit metrics (`metric.write`) | Yes | Yes | - | - |
| Approve / reject / publish / deprecate metrics (`metric.review`) | Yes | - | - | Yes |
| Roll back a metric (creates a new version) (`metric.rollback`) | Yes | - | - | Yes |
| Use TARA metric generator (`ai.generate`) | Yes | Yes | - | - |
| Ask TARA (natural-language BI) (`chat.ask`) | Yes | Yes | Yes | Yes |
| View conflicts (`conflict.view`) | Yes | Yes | Yes | Yes |
| Run conflict detection (`conflict.detect`) | Yes | Yes | - | Yes |
| Assign / review / resolve conflicts (`conflict.manage`) | Yes | - | - | Yes |
| Formula Lab: validate and execute (`formula.run`) | Yes | Yes | - | Yes |
| Create / edit dashboards (`dashboard.write`) | Yes | Yes | Yes | - |
| View performance evaluation (`evaluation.view`) | Yes | Yes | - | Yes |
| Run performance evaluation (`evaluation.run`) | Yes | Yes | - | - |
| Export reports (`report.export`) | Yes | Yes | Yes | Yes |
| Manage users and roles (`user.manage`) | Yes | - | - | - |
| Manage workspace and settings (`workspace.manage`) | Yes | - | - | - |
| View audit log (`audit.view`) | Yes | - | - | - |


# 7 Tour of the application {#sec-7}

## 7.1 Public pages {#sec-7-1}

**Landing page**

![Landing page, light mode](screenshots/light/01_landing.png)

![Landing page, dark mode](screenshots/dark/01_landing.png)

**About / product tour**

![About / product tour, light mode](screenshots/light/02_about.png)

![About / product tour, dark mode](screenshots/dark/02_about.png)

**Login with demo accounts panel**

![Login with demo accounts panel, light mode](screenshots/light/03_login.png)

![Login with demo accounts panel, dark mode](screenshots/dark/03_login.png)

**Register**

![Register, light mode](screenshots/light/04_register.png)

![Register, dark mode](screenshots/dark/04_register.png)

**Forgot password**

![Forgot password, light mode](screenshots/light/05_forgot_password.png)

![Forgot password, dark mode](screenshots/dark/05_forgot_password.png)

**Reset password**

![Reset password, light mode](screenshots/light/06_reset_password.png)

![Reset password, dark mode](screenshots/dark/06_reset_password.png)

**403 Forbidden**

![403 Forbidden, light mode](screenshots/light/07_forbidden_403.png)

![403 Forbidden, dark mode](screenshots/dark/07_forbidden_403.png)

**404 Not found**

![404 Not found, light mode](screenshots/light/08_not_found_404.png)

![404 Not found, dark mode](screenshots/dark/08_not_found_404.png)


## 7.2 Main application {#sec-7-2}

Pages are listed in the order of the sidebar. Screenshots are shown in light and dark mode; the sun/moon button in the top bar switches theme (Light, Dark or System) and the choice is remembered.

### 7.2.1 Dashboard {#sec-7-2-1}

The first page after login: four key figures (all computed from real data), recent conflicts and activity, and the dataset status. Amounts are in rupees with lakh/crore grouping (for example ₹12,45,300) and compact forms (₹1.2 Cr). Dates are DD-MMM-YYYY and times are in IST.

![Main dashboard, light mode](screenshots/light/20_dashboard.png)

![Main dashboard, dark mode](screenshots/dark/20_dashboard.png)


### 7.2.2 Metrics catalog and metric detail {#sec-7-2-2}

Search, filter and sort all metrics. A metric has a formula, a unit, a department, a status (Draft, In review, Approved, Published, Deprecated) and an owner. The detail page shows the live SQL preview, dependencies on other metrics, the latest value, conflicts and a link to the version history.

![Metrics catalog, light mode](screenshots/light/21_metrics_catalog.png)

![Metrics catalog, dark mode](screenshots/dark/21_metrics_catalog.png)

![Metric detail (Revenue), light mode](screenshots/light/22_metric_detail.png)

![Metric detail (Revenue), dark mode](screenshots/dark/22_metric_detail.png)


### 7.2.3 Datasets and connections {#sec-7-2-3}

Upload a CSV, TSV, Excel, JSON, JSON-Lines or Parquet file, or connect to a PostgreSQL or MySQL database. Processing runs in the background: *pending*, *processing*, *ready*. The dataset page then shows a preview, the detected schema (with the date column) and a per-column profile (nulls, distinct values, minimum, maximum, mean, most frequent values, duplicates).

![Datasets catalog, light mode](screenshots/light/23_datasets_catalog.png)

![Datasets catalog, dark mode](screenshots/dark/23_datasets_catalog.png)

![Dataset detail (preview), light mode](screenshots/light/24_dataset_detail.png)

![Dataset detail (preview), dark mode](screenshots/dark/24_dataset_detail.png)

![Database connections, light mode](screenshots/light/25_connections.png)

![Database connections, dark mode](screenshots/dark/25_connections.png)


### 7.2.4 TARA metric generator {#sec-7-2-4}

Choose a dataset and describe a metric in English. TARA returns an editable formula, explanation and warnings. **Nothing is saved or published automatically**; the analyst saves a draft or submits for approval.

![TARA metric generator (offline deterministic mode, editable suggestion), light mode](screenshots/light/38_tara_metric_generator.png)

![TARA metric generator (offline deterministic mode, editable suggestion), dark mode](screenshots/dark/38_tara_metric_generator.png)


### 7.2.5 Formula Lab {#sec-7-2-5}

A safe place to try formulas. Metrics are written as `[Revenue]`, columns by name, and the grammar allows only whitelisted functions. The Lab validates syntax, columns and types, shows the generated parameterised SQL, executes it on the real data with a time limit, and reports rows scanned and duration. Hostile input is rejected without running.

![Formula Lab: validate and execute (Revenue less refunds by state), light mode](screenshots/light/39_formula_lab.png)

![Formula Lab: validate and execute (Revenue less refunds by state), dark mode](screenshots/dark/39_formula_lab.png)

![Formula Lab rejecting an injection attempt, light mode](screenshots/light/40_formula_lab_rejected.png)

![Formula Lab rejecting an injection attempt, dark mode](screenshots/dark/40_formula_lab_rejected.png)


### 7.2.6 Conflict detection center {#sec-7-2-6}

*Run conflict detection* compares every pair of definitions of the same business idea, and lists conflicts with a type (formula, aggregation, filter, unit, time window, dataset), a severity and a recommendation. The detail page shows the two definitions side by side with the differences highlighted, then the workflow: **assign, review, approve, resolve**, each step recorded.

![Conflict detection center, light mode](screenshots/light/26_conflict_center.png)

![Conflict detection center, dark mode](screenshots/dark/26_conflict_center.png)

![Conflict detail (side-by-side), light mode](screenshots/light/27_conflict_detail.png)

![Conflict detail (side-by-side), dark mode](screenshots/dark/27_conflict_detail.png)


### 7.2.7 Version control {#sec-7-2-7}

Every change creates an immutable version. The history page lists versions, compares any two (word-level formula diff) and rolls back. Rolling back never rewrites history: it creates a **new** version that copies the old definition.

![Version control (Revenue history), light mode](screenshots/light/28_version_control.png)

![Version control (Revenue history), dark mode](screenshots/dark/28_version_control.png)

![Version compare (diff view), light mode](screenshots/light/44_version_compare.png)

![Version compare (diff view), dark mode](screenshots/dark/44_version_compare.png)


### 7.2.8 Ask TARA {#sec-7-2-8}

Type a question in plain English. TARA turns it into a checked query plan, runs it on approved metrics only, and shows the answer as text, table and chart, with the definition used, the date range and the filters. If the question cannot be answered from the data it says so.

![Ask TARA: suggested Indian questions, light mode](screenshots/light/41_ask_tara_empty.png)

![Ask TARA: suggested Indian questions, dark mode](screenshots/dark/41_ask_tara_empty.png)

![Ask TARA: answers with chart, table, sources and applied filters, light mode](screenshots/light/42_ask_tara_conversation.png)

![Ask TARA: answers with chart, table, sources and applied filters, dark mode](screenshots/dark/42_ask_tara_conversation.png)


### 7.2.9 Dashboards {#sec-7-2-9}

Saved dashboards with KPI, line, bar, pie and table widgets. *Edit layout* enables drag-and-resize. Dashboards can follow the latest published definition of each metric or be pinned to a version. Export as PNG, PDF or CSV.

![Saved dashboards and templates, light mode](screenshots/light/29_dashboards_list.png)

![Saved dashboards and templates, dark mode](screenshots/dark/29_dashboards_list.png)

![Dashboard builder (Sales Overview), light mode](screenshots/light/30_dashboard_builder.png)

![Dashboard builder (Sales Overview), dark mode](screenshots/dark/30_dashboard_builder.png)

![Dashboard builder in edit mode (drag handles), light mode](screenshots/light/43_dashboard_builder_edit.png)

![Dashboard builder in edit mode (drag handles), dark mode](screenshots/dark/43_dashboard_builder_edit.png)


### 7.2.10 Evaluation and reports {#sec-7-2-10}

*Run evaluation* measures processing time, query latency, validation pass rate, query success rate, conflict-detection precision and recall on 27 labelled cases, and the AI suggestion acceptance rate. Reports can be exported in CSV, Excel or PDF with rupee formatting and IST timestamps.

![Performance evaluation, light mode](screenshots/light/31_evaluation.png)

![Performance evaluation, dark mode](screenshots/dark/31_evaluation.png)

![Reports and exports, light mode](screenshots/light/32_reports.png)

![Reports and exports, dark mode](screenshots/dark/32_reports.png)


### 7.2.11 Profile, administration, settings and activity {#sec-7-2-11}

Admins manage users and roles, and read the audit log (who did what, when, from where). Settings show the AI mode, query limits and API usage.

![User profile, light mode](screenshots/light/33_profile.png)

![User profile, dark mode](screenshots/dark/33_profile.png)

![Workspace and user management, light mode](screenshots/light/34_admin_users.png)

![Workspace and user management, dark mode](screenshots/dark/34_admin_users.png)

![Audit log, light mode](screenshots/light/35_audit_log.png)

![Audit log, dark mode](screenshots/dark/35_audit_log.png)

![Application settings, light mode](screenshots/light/36_settings.png)

![Application settings, dark mode](screenshots/dark/36_settings.png)

![Notifications and activity, light mode](screenshots/light/37_activity.png)

![Notifications and activity, dark mode](screenshots/dark/37_activity.png)


## 7.3 Phone-sized screens {#sec-7-3}

The layout adapts to phone widths (390 px was checked).

**Mobile: landing page**

![Mobile: landing page, light mode](screenshots/light/90_mobile_landing.png)

![Mobile: landing page, dark mode](screenshots/dark/90_mobile_landing.png)

**Mobile: dashboard**

![Mobile: dashboard, light mode](screenshots/light/91_mobile_dashboard.png)

![Mobile: dashboard, dark mode](screenshots/dark/91_mobile_dashboard.png)

**Mobile: Ask TARA**

![Mobile: Ask TARA, light mode](screenshots/light/92_mobile_ask_tara.png)

![Mobile: Ask TARA, dark mode](screenshots/dark/92_mobile_ask_tara.png)


# 8 A ten-minute walkthrough {#sec-8}

Use the desktop browser at <http://localhost:5173> (or the port you chose).

| Step | Sign in as | Do this | You should see |
|---|---|---|---|
| 1 | Meera Iyer (Reviewer) | Open *Conflict detection*, click **Run conflict detection** | Conflicts for **Revenue**: the Finance version subtracts refunds; the Marketing version uses the GST-inclusive invoice value |
| 2 | Meera Iyer | Open the Finance conflict; **Assign** to Meera Iyer, **Start review**, **Approve**, then **Resolve** by renaming the variant (for example to *Net Revenue*) and adding a note | The renamed metric becomes version 2, and the "Audit history" lists every step |
| 3 | Diya Reddy (Analyst) | Open *Formula Lab*, choose `sales_transactions`, enter `[Revenue] - SUM(refund_amount)`, group by `state`, **Execute** | A table of rupee values by state, with rows scanned and duration |
| 4 | Diya Reddy | Replace the formula with `SUM(net_sales); DROP TABLE users` | A red error, "Nothing was executed" |
| 5 | Rohan Sharma (Business User) | Open *Ask TARA* and click each suggested question in turn | See below |
| 6 | Rohan Sharma | Ask "What is the weather in Delhi?" | A refusal saying TARA could not match the question to an approved metric; no number is invented |
| 7 | Rohan Sharma | Open *Dashboards*, then *Sales Overview* | KPI cards, trend line and breakdowns in rupees |
| 8 | Aarav Menon (Admin) | Open *Audit log* | Every action above with user, time (IST) and request id |
| 9 | Suresh Naidu (other workspace) | Open *Metrics* and *Datasets* | Only Sagar Foods data; nothing from Bharat Retail |

The suggested questions in step 5 are:

1. *What was net revenue by month in the last quarter of this financial year?* A monthly line or bar of the last completed April–March quarter.
2. *Which 5 states had the highest sales this year?* A ranked table and bar chart; "this year" means the financial year to date from 1 April.
3. *Compare Diwali-season sales with the previous quarter.* Two labelled date ranges, both totals, and a per-day note because the periods differ in length.
4. *What is the UPI vs COD split by region?* A grouped chart with each payment method's share of the region.
5. *Top 10 customers by revenue.* A ranked table.

Every answer lists the metric and version used, the date range in DD-MMM-YYYY, and the filters applied.

# 9 Understanding Indian conventions in the application {#sec-9}

| Topic | How the application behaves |
|---|---|
| Currency | Rupee symbol, lakh/crore digit grouping (12,45,300), compact forms ₹45 L and ₹1.2 Cr |
| Financial year | 1 April to 31 March. Q1 = April–June, Q2 = July–September, Q3 = October–December, Q4 = January–March. "This year" means the financial year to date |
| Dates and time | DD-MMM-YYYY, times in IST (Asia/Kolkata) |
| GST | `net_sales` is the taxable value **excluding** GST; `net_amount` is the invoice value **including** GST. The two Revenue definitions differ by exactly the GST, which is why the GST conflict is detected |
| Festivals | Diwali, Dussehra, Pongal/Sankranti, Eid, Holi and the End-of-Season sale have date windows that TARA understands ("Diwali-season") |
| Payment methods | UPI, card, net banking, wallet and cash on delivery (COD) |

# 10 Troubleshooting {#sec-10}

| Problem | Cause and fix |
|---|---|
| `python -m app.seed` says the database is locked | The back end is still running. Stop it, then seed again |
| Browser shows "Failed to fetch" or a blank page | The back end is not running on port 8000. Start it and reload |
| Page loads but images are grey gradients | Offline, or the photo host is blocked. Harmless; the application is fully usable |
| Dataset stays on *pending* | In the no-Docker route a background thread processes it; check the back-end console for an error. With Celery, make sure a worker and Redis are running |
| Everything works but TARA says "offline deterministic mode" | Expected without an AI key. Set `AI_PROVIDER` and the key in the back-end environment to enable live AI |
| Login fails for a demo account | The database was seeded before the accounts changed. Run `scripts\reset-demo.ps1` |
| Port already in use | Change `--port` for uvicorn (and `VITE_API_PROXY` for the front end), or stop the other program |
| `npm install` is slow | First install downloads about 300 MB of packages; later runs are cached |

# 11 Running the tests {#sec-11}

```powershell
cd backend;  python -m pytest tests -q
cd frontend; npx vitest run
cd frontend; npx playwright install chromium; npx playwright test
```

The Testing Report lists what each suite covers and the measured results.
