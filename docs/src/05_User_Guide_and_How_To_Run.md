<!-- subtitle: Installing, running and using IntelliMetrics AI, with screenshots of every page -->
{{titlepage}}

{{toc}}

# About this guide

IntelliMetrics AI is a **university project** (academic capstone) with synthetic demonstration data. This guide explains how to run it on a Windows computer, how to sign in, what each page does, and a ten-minute walkthrough that reproduces the main results. All screenshots were captured from the running application by the automated script `frontend/e2e-docs/screens.spec.ts`.

# What you need

| Requirement | Version used in development | Needed for |
|---|---|---|
| Python | {{ver.python}} | Back end |
| Node.js and npm | Node {{ver.node}} | Front end |
| A modern browser | Chrome or Edge | Using the application |
| Docker Desktop | not used on the development machine | Optional: the Compose route (Section 5) |

Everything else (database, analytics engine, background jobs) is installed by the commands below. **No internet connection is needed to run the application**, except to download the packages the first time and to show the stock photographs on the public pages (a gradient is shown instead when they cannot load). **No paid service, account or API key is required.**

# Run it without Docker (recommended, tested route)

This is the route that was run and tested for this report. It uses SQLite for application data and a background thread for dataset processing, so Redis and PostgreSQL are not needed.

## Step 1: back end

Open **PowerShell** in the project folder:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

`python -m app.seed` creates the database and the demonstration data (about {{bench.seed_seconds}} seconds on the development machine). Leave the window open. The API documentation is at <http://localhost:8000/docs> and the health check at <http://localhost:8000/health>.

## Step 2: front end

Open a **second** PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The development server forwards `/api` requests to port 8000.

## Step 3: reset the demonstration at any time

```powershell
scripts\reset-demo.ps1      # Windows
./scripts/reset-demo.sh     # Git Bash / Linux / macOS
```

This deletes the local database and uploaded files and seeds again. Stop the back end first, because Windows locks the SQLite file while it is running.

# Run it with Docker Compose (not executed in development)

```bash
cp .env.example .env     # set SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

Open <http://localhost:3000>. This starts PostgreSQL, Redis, the API, a Celery worker and an Nginx front end. **This path was written but has not been run**, because Docker is not installed on the development machine; the services it starts were each verified separately (see the Testing Report). If a step fails, the Deployment Guide has a troubleshooting table.

# Configuration

Settings are environment variables, listed in full in the Deployment Guide. The ones a student is likely to touch:

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `none` | `none` = TARA's offline deterministic mode (no key needed). `openai` or `gemini` plus the matching `*_API_KEY` turns on live AI planning |
| `AUTO_SEED` | `true` in `.env.example` | Seeds demo data when the database is empty |
| `USE_CELERY` | `false` | `true` uses Celery and Redis for dataset processing |
| `DATABASE_URL` | local SQLite file | Use a `postgresql://` URL for PostgreSQL |
| `MAX_UPLOAD_MB` | 500 | Upload size limit |

If no AI key is set, every TARA screen says that it is in **offline deterministic mode**. It still answers all the suggested questions below, because the questions are interpreted by a rule-based planner and the numbers always come from the data.

# Demonstration accounts

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

## What each role can do

{{table:permissions}}

# Tour of the application

## Public pages

{{gallery:public}}

## Main application

Pages are listed in the order of the sidebar. Screenshots are shown in light and dark mode; the sun/moon button in the top bar switches theme (Light, Dark or System) and the choice is remembered.

### Dashboard

The first page after login: four key figures (all computed from real data), recent conflicts and activity, and the dataset status. Amounts are in rupees with lakh/crore grouping (for example ₹12,45,300) and compact forms (₹1.2 Cr). Dates are DD-MMM-YYYY and times are in IST.

{{shots:dashboard}}

### Metrics catalog and metric detail

Search, filter and sort all metrics. A metric has a formula, a unit, a department, a status (Draft, In review, Approved, Published, Deprecated) and an owner. The detail page shows the live SQL preview, dependencies on other metrics, the latest value, conflicts and a link to the version history.

{{shots:metrics_catalog,metric_detail}}

### Datasets and connections

Upload a CSV, TSV, Excel, JSON, JSON-Lines or Parquet file, or connect to a PostgreSQL or MySQL database. Processing runs in the background: *pending*, *processing*, *ready*. The dataset page then shows a preview, the detected schema (with the date column) and a per-column profile (nulls, distinct values, minimum, maximum, mean, most frequent values, duplicates).

{{shots:datasets_catalog,dataset_detail,connections}}

### TARA metric generator

Choose a dataset and describe a metric in English. TARA returns an editable formula, explanation and warnings. **Nothing is saved or published automatically**; the analyst saves a draft or submits for approval.

{{shots:tara_metric_generator}}

### Formula Lab

A safe place to try formulas. Metrics are written as `[Revenue]`, columns by name, and the grammar allows only whitelisted functions. The Lab validates syntax, columns and types, shows the generated parameterised SQL, executes it on the real data with a time limit, and reports rows scanned and duration. Hostile input is rejected without running.

{{shots:formula_lab,formula_lab_rejected}}

### Conflict detection center

*Run conflict detection* compares every pair of definitions of the same business idea, and lists conflicts with a type (formula, aggregation, filter, unit, time window, dataset), a severity and a recommendation. The detail page shows the two definitions side by side with the differences highlighted, then the workflow: **assign, review, approve, resolve**, each step recorded.

{{shots:conflict_center,conflict_detail}}

### Version control

Every change creates an immutable version. The history page lists versions, compares any two (word-level formula diff) and rolls back. Rolling back never rewrites history: it creates a **new** version that copies the old definition.

{{shots:version_control,version_compare}}

### Ask TARA

Type a question in plain English. TARA turns it into a checked query plan, runs it on approved metrics only, and shows the answer as text, table and chart, with the definition used, the date range and the filters. If the question cannot be answered from the data it says so.

{{shots:ask_tara_empty,ask_tara_conversation}}

### Dashboards

Saved dashboards with KPI, line, bar, pie and table widgets. *Edit layout* enables drag-and-resize. Dashboards can follow the latest published definition of each metric or be pinned to a version. Export as PNG, PDF or CSV.

{{shots:dashboards_list,dashboard_builder,dashboard_builder_edit}}

### Evaluation and reports

*Run evaluation* measures processing time, query latency, validation pass rate, query success rate, conflict-detection precision and recall on 27 labelled cases, and the AI suggestion acceptance rate. Reports can be exported in CSV, Excel or PDF with rupee formatting and IST timestamps.

{{shots:evaluation,reports}}

### Profile, administration, settings and activity

Admins manage users and roles, and read the audit log (who did what, when, from where). Settings show the AI mode, query limits and API usage.

{{shots:profile,admin_users,audit_log,settings,activity}}

## Phone-sized screens

The layout adapts to phone widths (390 px was checked).

{{gallery:mobile}}

# A ten-minute walkthrough

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

# Understanding Indian conventions in the application

| Topic | How the application behaves |
|---|---|
| Currency | Rupee symbol, lakh/crore digit grouping (12,45,300), compact forms ₹45 L and ₹1.2 Cr |
| Financial year | 1 April to 31 March. Q1 = April–June, Q2 = July–September, Q3 = October–December, Q4 = January–March. "This year" means the financial year to date |
| Dates and time | DD-MMM-YYYY, times in IST (Asia/Kolkata) |
| GST | `net_sales` is the taxable value **excluding** GST; `net_amount` is the invoice value **including** GST. The two Revenue definitions differ by exactly the GST, which is why the GST conflict is detected |
| Festivals | Diwali, Dussehra, Pongal/Sankranti, Eid, Holi and the End-of-Season sale have date windows that TARA understands ("Diwali-season") |
| Payment methods | UPI, card, net banking, wallet and cash on delivery (COD) |

# Troubleshooting

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

# Running the tests

```powershell
cd backend;  python -m pytest tests -q
cd frontend; npx vitest run
cd frontend; npx playwright install chromium; npx playwright test
```

The Testing Report lists what each suite covers and the measured results.
