"""Builds the report pack.

  docs/src/*.md   source with {{placeholders}}  ->  docs/*.md (final Markdown)  ->  docs/exports/*.docx and *.pdf

Every number in the reports is substituted from MEASURED data files in docs/data (benchmark.json, JUnit XML, coverage JSON,
Playwright JSON, verification JSON) or from generated code facts in docs/generated. Nothing is typed in by hand.

Placeholders:  {{a.b.c}} data value | {{table:name}} computed table | {{include:file.md}} generated fragment
               {{toc}} contents | {{titlepage}} title block | {{fig:path|caption}} figure | {{gallery:name}} screenshots | {{today}}
Usage:  backend/.venv/Scripts/python.exe docs/tools/build_docs.py [--no-export]"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SRC, DATA, GEN, SHOTS, DIAG, CHARTS, EXPORTS, BUILD = (DOCS / "src", DOCS / "data", DOCS / "generated", DOCS / "screenshots", DOCS / "diagrams", DOCS / "charts", DOCS / "exports", DOCS / "_build")
for d in (EXPORTS, BUILD, BUILD / "img"):
    d.mkdir(parents=True, exist_ok=True)

META = {"student": "Devi Priya, Priyanka, Akshay and Bhaskar", "guide": "Dr. Asesh Kumar Tripathy", "university": "KL University", "year": "2026-27", "project": "IntelliMetrics AI: A Governed Semantic Layer with TARA, an AI Assistant for Trusted Business Metrics"}
TODAY = dt.datetime.now(ZoneInfo("Asia/Kolkata"))

COMPACT = {"02_Concept_Note", "07_Viva_Preparation", "08_Presentation_Outline"}
DOCS_LIST = [
    ("01_Project_Report", "Project Report"), ("02_Concept_Note", "Concept Note"), ("03_System_Architecture", "System Architecture and Design"),
    ("04_Testing_Report", "Testing Report"), ("05_User_Guide_and_How_To_Run", "User Guide and How To Run"), ("06_Deployment_Guide", "Deployment Guide"),
    ("07_Viva_Preparation", "Viva Preparation"), ("08_Presentation_Outline", "Presentation Outline"),
]


# ============================================================================= data
def jload(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else (default if default is not None else {})


def junit(path: Path):
    if not path.exists():
        return {"cases": [], "total": 0, "passed": 0, "failed": 0, "skipped": 0, "time": 0.0}
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    cases = []
    for ts in suites:
        for tc in ts.iter("testcase"):
            fail = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            skipped = tc.find("skipped") is not None
            cases.append({"cls": tc.get("classname", ""), "name": tc.get("name", ""), "time": float(tc.get("time", 0) or 0), "status": "failed" if fail is not None else ("skipped" if skipped else "passed"), "msg": (fail.get("message") or fail.text or "")[:200] if fail is not None else ""})
    tot = len(cases)
    f = sum(c["status"] == "failed" for c in cases)
    s = sum(c["status"] == "skipped" for c in cases)
    return {"cases": cases, "total": tot, "passed": tot - f - s, "failed": f, "skipped": s, "time": round(sum(c["time"] for c in cases), 1)}


def playwright(path: Path):
    j = jload(path)
    cases = []

    def walk(suite):
        for sp in suite.get("specs", []):
            for t in sp.get("tests", []):
                res = t.get("results", [{}])
                last = res[-1] if res else {}
                cases.append({"cls": "playwright", "name": sp["title"], "time": last.get("duration", 0) / 1000, "status": "passed" if last.get("status") == "passed" else "failed", "msg": ""})
        for s in suite.get("suites", []):
            walk(s)

    for s in j.get("suites", []):
        walk(s)
    tot = len(cases)
    f = sum(c["status"] == "failed" for c in cases)
    return {"cases": cases, "total": tot, "passed": tot - f, "failed": f, "skipped": 0, "time": round(sum(c["time"] for c in cases), 1)}


def coverage():
    be = jload(DATA / "backend_coverage.json")
    fe = jload(DATA / "frontend_coverage" / "coverage-summary.json")
    out = {"backend": {}, "frontend": {}}
    if be:
        t = be["totals"]
        out["backend"] = {"pct": round(t["percent_covered"], 1), "statements": t["num_statements"], "missing": t["missing_lines"], "files": len(be["files"])}
    if fe:
        t = fe["total"]
        out["frontend"] = {"pct": round(t["statements"]["pct"], 1), "lines": round(t["lines"]["pct"], 1), "branches": round(t["branches"]["pct"], 1), "funcs": round(t["functions"]["pct"], 1)}
    return out


def versions():
    req = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    out = {}
    for l in req.splitlines():
        if "==" in l:
            n, v = l.split("==")
            out[n.split("[")[0].lower().replace("-", "_")] = v.strip()
    pkg = jload(ROOT / "frontend" / "package.json")
    for n, v in {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}.items():
        out[n.lstrip("@").replace("/", "_").replace("-", "_").lower()] = v.lstrip("^~")
    for n, v in jload(DOCS / "tools" / "package.json").get("devDependencies", {}).items():
        out[n.lstrip("@").replace("/", "_").replace("-", "_").lower()] = v.lstrip("^~")
    out["python"] = "3.11"
    out["node"] = "22"
    return out


def build_data():
    bench = jload(DATA / "benchmark.json")
    t = {"pytest": junit(DATA / "backend_junit.xml"), "pytest_pg": junit(DATA / "backend_postgres_junit.xml"), "vitest": junit(DATA / "frontend_junit.xml"), "playwright": playwright(DATA / "playwright_results.json")}
    t["total"] = sum(v["total"] for v in t.values() if isinstance(v, dict))
    t["passed"] = sum(v["passed"] for v in t.values() if isinstance(v, dict))
    t["failed"] = sum(v["failed"] for v in t.values() if isinstance(v, dict))
    img = jload(DATA / "image_check.json", [])
    pr = jload(DATA / "language_check.json")
    d = {
        "bench": bench, "stats": jload(GEN / "stats.json"), "tests": t, "cov": coverage(), "celery": jload(DATA / "celery_verification.json"),
        "conns": {c["kind"]: c for c in jload(DATA / "connections_verification.json", [])}, "img": {"total": len(img), "ok": sum(1 for i in img if i.get("ok"))},
        "langcheck": {"allow_listed": pr.get("allow_listed", 0), "unexplained": len(pr.get("unexplained", []))}, "meta": META,
        "env": {"os": bench.get("environment", {}).get("platform", ""), "python": bench.get("environment", {}).get("python", ""), "cpus": bench.get("environment", {}).get("cpu_count", "")},
        "walk": {k: jload(DATA / "walkthrough_verification.json").get(k, 0) for k in ("passed", "total")},
        "today": TODAY.strftime("%d-%b-%Y"), "now": TODAY.strftime("%d-%b-%Y %H:%M IST"),
    }
    d["ver"] = versions()
    return d


D = build_data()


def lookup(path: str):
    cur = D
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


def fmt(v):
    if isinstance(v, float):
        return f"{v:,.1f}" if abs(v) < 1000 else f"{v:,.0f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


# ============================================================================= tables
def md_table(headers, rows, align=None):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(":-:" if (align and align[i] == "c") else "---" for i in range(len(headers))) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |")
    return "\n".join(out)


# curated catalogue: (id, module, description, input, expected, kind, matcher)
TC = [
    ("TC-AUTH-01", "Auth", "Wrong password is rejected with the standard error envelope", "POST /auth/login with a wrong password", "401, code invalid_credentials, request_id present", "py", r"test_login_wrong_password"),
    ("TC-AUTH-02", "Auth", "Protected endpoints require authentication", "GET /metrics, /datasets, /overview ... without cookie", "401 on every protected route", "py", r"test_requires_auth"),
    ("TC-AUTH-03", "Auth", "Cookies are httpOnly; refresh tokens rotate; logout revokes", "login, refresh twice with the old token, logout", "httpOnly flags; old refresh token 401; /me 401 after logout", "py", r"test_cookie_flags_and_refresh_rotation"),
    ("TC-AUTH-04", "Auth", "CSRF header required for cookie-authenticated mutations", "POST /conflicts/detect without X-Requested-With", "403 code csrf", "py", r"test_csrf_header"),
    ("TC-AUTH-05", "Auth", "Registration creates an isolated workspace; duplicate and weak passwords rejected", "register new user; register again; register '12345678'", "201 admin of an empty workspace; 409; 400", "py", r"test_register_creates_isolated_workspace"),
    ("TC-AUTH-06", "Auth", "Forgot / reset password is token based and single use", "forgot -> reset with link -> reuse the token", "dev link returned only in development; second use 400; unknown email gives the same 200", "py", r"test_forgot_and_reset_password_flow"),
    ("TC-RBAC-01", "RBAC", "Role x endpoint permission matrix", "16 role/endpoint combinations (business, analyst, reviewer, admin)", "403 for roles lacking the capability, 200 otherwise", "py", r"test_rbac_matrix"),
    ("TC-RBAC-02", "RBAC", "Reviewer cannot write; analyst cannot approve; reject needs a comment", "PATCH as reviewer; approve as analyst; reject without comment", "403, 403, 400; with comment status returns to draft", "py", r"test_reviewer_cannot_write_but_can_approve"),
    ("TC-ISO-01", "Isolation", "A user in workspace B can never read workspace A data", "GET/POST on A's dataset, metric, versions, execution, delete from B", "404 everywhere; lists contain only own data; TARA cannot see A's metrics", "py", r"test_workspace_isolation"),
    ("TC-ISO-02", "Isolation", "Admins cannot demote themselves or touch another workspace's users", "PATCH self role; PATCH foreign user", "403; 404", "py", r"test_cannot_deactivate_self"),
    ("TC-FOR-01", "Formula", "Formula compiles to parameterised SQL; division is zero-safe", "SUM(...) - SUM(...) WHERE region = 'EU' ..., SUMIF, COUNTIF, ROUND", "literals only as bound ? parameters; NULLIF(x, 0) for division", "py", r"test_basic_compile_and_parameterization|test_division_is_zero_safe"),
    ("TC-FOR-02", "Formula", "25 injection and invalid inputs are rejected", "'; DROP TABLE', comments, read_csv(), UNION, backticks, nested aggregates, unknown columns ...", "FormulaError with a clear message; nothing executed", "py", r"test_injection_and_invalid_inputs_rejected"),
    ("TC-FOR-03", "Formula", "String literals are never inlined into SQL", "region = 'x'' OR ''1''=''1'", "value travels as a parameter; SQL text contains no payload", "py", r"test_string_literals_are_never_inlined"),
    ("TC-FOR-04", "Formula", "Depth and length limits", "100 nested parentheses; 2000+ characters", "FormulaError (too deep / too long)", "py", r"test_deep_nesting_and_length_limits"),
    ("TC-FOR-05", "Formula", "Metric references inline with their filters; cycles detected", "[EuRev] / COUNT(*); [A] <-> [B]", "FILTER (WHERE ...) clause with parameter; Circular metric reference error", "py", r"test_metric_reference_inlines|test_circular_reference"),
    ("TC-FOR-06", "Formula", "Dimension, grain, filter and limit builders reject hostile input", "column 'region; DROP', grain \"month'); --\", operator '=; DROP'", "FormulaError; row limit clamped to 10,000", "py", r"test_build_sql_dimensions_filters_and_limits"),
    ("TC-FOR-07", "Formula", "Execution endpoint rejects injection and records failures", "POST /execution/run with SELECT * FROM data and DROP TABLE", "422 invalid_formula; failed runs appear in history", "py", r"test_execute_endpoint_rejects_injection"),
    ("TC-FOR-08", "Formula", "Canonical form ignores case and operand order", "sum(Net_Sales)+SUM(x) vs SUM(x)+SUM(net_sales)", "equal canonical strings; a/b differs from b/a", "py", r"test_canonical_equivalence"),
    ("TC-CON-01", "Conflicts", "Deterministic differences are classified", "pairs differing in formula, aggregation, filter, unit, window, dataset", "exactly the expected type per pair; no false positives for case/whitespace", "py", r"test_conflict_types_deterministic"),
    ("TC-CON-02", "Conflicts", "Precision and recall on labelled ground truth", "27 labelled cases", "automated precision = recall = 1.0; naive text diff precision < 0.8", "py", r"test_ground_truth_precision_recall"),
    ("TC-CON-03", "Conflicts", "Detection is idempotent; TARA suggestions are labelled/skipped without AI", "run detect twice", "created = 0 the second time; tara.enabled false with a note", "py", r"test_conflict_detection_is_idempotent"),
    ("TC-CON-04", "Conflicts", "Headline scenario: Finance Revenue vs official Revenue end to end", "detect, assign, review, approve, resolve (rename), re-detect", "ordered workflow enforced; new version created; audit trail complete; GST variant still open", "py", r"test_revenue_conflict_end_to_end"),
    ("TC-CON-05", "Conflicts", "GST-inclusive Revenue (Marketing) conflicts with ex-GST Revenue", "detect", "formula conflict on SUM(net_amount) vs SUM(net_sales)", "py", r"test_gst_conflict_is_detected"),
    ("TC-VER-01", "Versioning", "Version rows are immutable", "UPDATE / DELETE a metric_versions row through the ORM", "ValueError: rows are immutable", "py", r"test_versions_are_immutable"),
    ("TC-VER-02", "Versioning", "Edits create versions; rollback creates a NEW version; history unchanged", "edit, publish, edit, rollback, diff", "versions 4,3,2,1 retained; v4 rollback_of 1; diff lists the formula change", "py", r"test_edit_creates_version_rollback"),
    ("TC-VER-03", "Versioning", "Exactly one published definition per governed metric", "publish a second 'Revenue'", "409 already the published definition", "py", r"test_one_published_definition_per_key"),
    ("TC-VER-04", "Versioning", "Invalid formulas cannot be submitted", "submit SUM(nope_col)", "422 invalid_formula", "py", r"test_invalid_formula_cannot_be_submitted"),
    ("TC-ING-01", "Ingestion", "CSV upload is processed in the background and profiled", "upload 2,001-row CSV with spaces in headers", "202; status polling to ready; snake_case schema; date column detected; nulls and duplicates profiled", "py", r"test_csv_upload_processed"),
    ("TC-ING-02", "Ingestion", "Invalid uploads are rejected", ".exe, empty file, fake parquet, binary csv, business user", "400 / 403 before any processing", "py", r"test_upload_validation_errors"),
    ("TC-ING-03", "Ingestion", "A failing file ends in 'failed' with an error report", "header-only CSV", "dataset failed; job error_report.fatal set", "py", r"test_header_only_csv"),
    ("TC-ING-04", "Ingestion", "JSON and Parquet formats", "upload .json and .parquet", "rows detected correctly", "py", r"test_json_and_parquet_upload"),
    ("TC-ING-05", "Ingestion", "Connection credentials are encrypted and never returned", "create a connection; read the DB column and the API", "ciphertext in DB; API shows ********; import with a malicious table name 400", "py", r"test_connection_credentials_encrypted"),
    ("TC-AI-01", "TARA", "Offline generator is labelled and grounded in the schema", "'Total quantity of units sold in the South region'", "mode offline label; formula uses real columns; nothing auto-saved; unanswerable prompt reports an error", "py", r"test_tara_generator_offline"),
    ("TC-AI-02", "TARA", "AI timeout, malformed JSON, hallucinated column and repair", "mocked provider", "fallback labelled; one repair round; invalid output can be saved as draft but not submitted", "py", r"test_tara_generator_with_mocked_ai"),
    ("TC-AI-03", "TARA", "Forged or hallucinated query plans are rejected", "mocked planner returning dimension 'ssn' or metric 'payroll_secret'", "unsupported with an explanation; no query run", "py", r"test_planner_rejects_forged_ai_plans"),
    ("TC-AI-04", "TARA", "Conversation history, SSE streaming and privacy", "ask twice; stream; read as another user", "4 messages with payload; status/result/text/done events; 404 for other users", "py", r"test_chat_history_and_streaming"),
    ("TC-IN-01", "Indian context", "Lakh/crore digit grouping", "1245300, 123456789 ...", "12,45,300 and 12,34,56,789", "py", r"test_lakh_crore_grouping"),
    ("TC-IN-02", "Indian context", "INR formatting and compact forms", "inr(1245300), compact(1.2 Cr, 45 L)", "\u20b912,45,300; \u20b91.2 Cr; \u20b945 L", "py", r"test_inr_and_compact_formats"),
    ("TC-IN-03", "Indian context", "April-March fiscal quarters", "fq_bounds for Q1-Q4; fq_of dates around 31-Mar/01-Apr", "Q1 Apr-Jun ... Q4 Jan-Mar", "py", r"test_fiscal_quarters|test_metric_window_ytd"),
    ("TC-IN-04", "Indian context", "14 natural-language time expressions", "last quarter, this FY, FY 2025-26, FY26, Q3 FY26, first quarter of last financial year ...", "exact ISO start/end dates on the fiscal calendar", "py", r"test_fiscal_time_ranges"),
    ("TC-IN-05", "Indian context", "Fallbacks and previous-period logic", "last quarter of this FY when no quarter has completed; previous quarter of Diwali", "Q4 of previous FY; Q2 FY 2025-26", "py", r"test_last_quarter_when|test_previous_period"),
    ("TC-IN-06", "Indian context", "Dates as DD-MMM-YYYY in IST", "fmt_date, UTC to IST conversion", "05-Mar-2026; 20:00 UTC -> 01-Jan-2026 01:30 IST", "py", r"test_date_display_and_ist"),
    ("TC-IN-07", "Indian context", "Synthetic dataset is Indian, large and well formed", "profile of sales_transactions; customers preview", "62,000 rows; five regions, channels, payment methods; valid 6-digit PINs; +91 90000 numbers; example.com e-mails", "py", r"test_dataset_is_indian_and_large|test_customers_have_valid_indian_formats"),
    ("TC-IN-08", "Indian context", "GST amounts reconcile and slabs are official", "net_amount - net_sales - gst_amount; distinct gst_rate", "difference < \u20b95; slabs within {0, 5, 12, 18, 28}", "py", r"test_gst_slabs"),
    ("TC-IN-09", "Indian context", "Festive seasonality and COD returns are present in the data", "Diwali 2025 daily revenue vs previous quarter; return rate COD vs UPI", "festival run-rate > 1.3x; COD return rate > 1.5x UPI", "py", r"test_festive_seasonality|test_cod_has_higher"),
    ("TC-IN-10", "Indian context", "The five suggested Indian questions return real, data-backed answers", "five questions via /chat/ask", "kind answer, rows present, rupee symbol, no dollar amounts; API suggests them", "py", r"test_each_suggested_question|test_suggested_questions_come|test_net_revenue_by_month|test_top_states"),
    ("TC-IN-11", "Indian context", "Diwali-season vs previous-quarter comparison", "Compare Diwali-season sales with the previous quarter", "two ranges labelled; per-day note for unequal lengths", "py", r"test_diwali_comparison|test_compare_text_flags"),
    ("TC-IN-12", "Indian context", "Exports use INR and IST", "dashboard CSV; metrics CSV", "rupee symbol, lakh grouping, DD-MMM-YYYY HH:MM IST", "py", r"test_exports_use_inr"),
    ("TC-DASH-01", "Dashboards", "All three templates render real data", "create Operations template; load widget data", "every widget ok; KPI has a value", "py", r"test_dashboard_templates_render"),
    ("TC-REP-01", "Reports", "Evaluation run and exports in CSV, XLSX and PDF", "POST /evaluation/run; export metrics, conflicts, evaluation, dashboard", "precision/recall >= 0.9; files have correct magic bytes", "py", r"test_evaluation_and_reports"),
    ("TC-FE-01", "Frontend", "Theme toggle persists and applies the dark class", "click Dark, Light, System", "class + localStorage updated", "vt", r"ThemeToggle"),
    ("TC-FE-02", "Frontend", "Images: alt text, lazy loading, B/W filter, gradient fallback; all config entries valid", "SafeImage load / error; images.ts audit", "fallback rendered on error; every entry has URL, alt and source", "vt", r"SafeImage|image config"),
    ("TC-FE-03", "Frontend", "Tables, pager, diff, validation panel, route guard", "DataTable sort/keyboard; Pager; FormulaDiff; RequireCap", "behaviour and accessibility attributes as specified", "vt", r"DataTable|Pager|FormulaDiff|ValidationPanel|RequireCap|StatusBadge"),
    ("TC-FE-04", "Frontend", "INR/lakh/crore and IST formatters", "formatValue, compactIN, axisFormat, fmtDate/fmtDateTime/fmtDay", "\u20b912,45,300; \u20b91.2 Cr; 01-Jan-2026 01:30 IST", "vt", r"formatters"),
    ("TC-FE-05", "Frontend", "API client: CSRF header, error envelope, 401 refresh-and-retry, SSE parser", "mocked fetch", "single refresh then retry; sign-out when refresh fails; stream events parsed", "vt", r"api client"),
    ("TC-FE-06", "Frontend", "UI primitives are accessible", "forms, buttons, dialogs, tabs, toasts, progress, empty/error states", "roles, labels, aria-live regions present", "vt", r"form controls|Button|Modal|Tabs|toasts|shared page pieces"),
    ("TC-FE-07", "Frontend", "Landing page has no pricing and shows the University Project badge", "render landing", "no pricing/plan/billing text; academic CTAs; rupee figure", "vt", r"public landing page"),
    ("TC-E2E-01", "E2E", "Login with the demo panel, bad password, logout, route protection", "browser", "dashboard after login; login page after logout", "pw", r"login: demo panel"),
    ("TC-E2E-02", "E2E", "All demo roles sign in and see role-appropriate navigation", "4 roles", "nav items shown/hidden per role", "pw", r"every demo account"),
    ("TC-E2E-03", "E2E", "403 and 404 pages", "business user opens /app/lab; unknown URL", "Forbidden and Not found pages", "pw", r"forbidden routes"),
    ("TC-E2E-04", "E2E", "Theme toggle light/dark/system with no flash", "toggle, reload, init script", "class and localStorage persist; pre-paint script applies theme", "pw", r"theme toggle"),
    ("TC-E2E-05", "E2E", "Upload a dataset and see profiling", "upload 3,000-row CSV", "ready; row count; profile and schema tabs", "pw", r"upload dataset"),
    ("TC-E2E-06", "E2E", "Create a metric with live validation and submit it", "invalid then valid formula", "validation messages; draft saved; in review", "pw", r"create metric"),
    ("TC-E2E-07", "E2E", "Detect conflict, assign, review, approve, resolve", "Reviewer in the UI", "Finance and Marketing Revenue conflicts; new version v2 for the renamed metric", "pw", r"detect conflict"),
    ("TC-E2E-08", "E2E", "Formula Lab executes and rejects injection", "SUM(net_sales); injection attempt; group by region", "rupee-grouped value; rows scanned; error 'Nothing was executed'", "pw", r"formula lab"),
    ("TC-E2E-09", "E2E", "Ask TARA: Indian fiscal answers in INR with chart and sources", "suggested questions, UPI vs COD, Diwali comparison, weather question", "tables, line / grouped charts, per-day note, refusal for the weather question", "pw", r"ask TARA"),
    ("TC-E2E-10", "E2E", "Landing page has no pricing; University Project badge; About page", "browser", "no banned words; badge and footer note visible", "pw", r"landing page"),
    ("TC-E2E-11", "E2E", "Indian formatting on the dashboard and audit log", "Sales Overview KPI; audit log dates", "\u20b9 with lakh/crore grouping; DD-MMM-YYYY HH:MM IST", "pw", r"Indian formatting"),
    ("TC-E2E-12", "E2E", "Build a dashboard from a template, edit layout, add widget, save, export menu", "Operations template", "widget count persists after reload; export options visible", "pw", r"build dashboard"),
    ("TC-E2E-13", "E2E", "Register a workspace and reset the password via the dev banner link", "register, forgot, reset, login", "dev banner shown; new password works", "pw", r"register a new workspace"),
]


def tc_status(kind, rx):
    key = {"py": "pytest", "vt": "vitest", "pw": "playwright"}[kind]
    cases = [c for c in D["tests"][key]["cases"] if re.search(rx, c["cls"] + "::" + c["name"])]
    if not cases:
        return "Not run", "no matching test result found", 0
    failed = [c for c in cases if c["status"] != "passed"]
    n = len(cases)
    if failed:
        return "FAIL", failed[0]["msg"] or "failed", n
    pg = ""
    if kind == "py":
        pgc = [c for c in D["tests"]["pytest_pg"]["cases"] if re.search(rx, c["cls"] + "::" + c["name"])]
        if pgc and all(c["status"] == "passed" for c in pgc):
            pg = f"; also {len(pgc)}/{len(pgc)} on PostgreSQL 18"
    return "Pass", f"{n}/{n} case{'s' if n != 1 else ''} passed as expected{pg}", n


def table_testcases(groups=None):
    rows = []
    for tid, mod, desc, inp, exp, kind, rx in TC:
        st, act, _n = tc_status(kind, rx)
        rows.append([tid, mod, desc, inp, exp, act, st])
    return md_table(["ID", "Module", "Test case", "Input / steps", "Expected result", "Actual result", "Status"], rows)


def table_suites():
    t = D["tests"]
    rows = [
        ["pytest, SQLite (API, services, security)", t["pytest"]["total"], t["pytest"]["passed"], t["pytest"]["failed"], f"{t['pytest']['time']} s"],
        ["pytest, real PostgreSQL 18.2 (same suite, Alembic-built schema)", t["pytest_pg"]["total"], t["pytest_pg"]["passed"], t["pytest_pg"]["failed"], f"{t['pytest_pg']['time']} s"],
        ["Vitest + Testing Library (components, lib)", t["vitest"]["total"], t["vitest"]["passed"], t["vitest"]["failed"], f"{t['vitest']['time']} s"],
        ["Playwright E2E (Chromium)", t["playwright"]["total"], t["playwright"]["passed"], t["playwright"]["failed"], f"{t['playwright']['time']} s"],
        ["**Total**", t["total"], t["passed"], t["failed"], ""],
    ]
    return md_table(["Suite", "Tests", "Passed", "Failed", "Duration"], rows, "lccrr")


def table_coverage():
    be = jload(DATA / "backend_coverage.json")
    rows = []
    for p, v in sorted(be.get("files", {}).items(), key=lambda kv: kv[1]["summary"]["percent_covered"]):
        s = v["summary"]
        if s["num_statements"] and any(x in p.replace("\\", "/") for x in ("services/", "routers/")):
            rows.append([f"`{p.replace(chr(92), '/')}`", s["num_statements"], s["missing_lines"], f"{s['percent_covered']:.0f}%"])
    c = D["cov"]
    head = f"Backend (pytest-cov): **{c['backend'].get('pct', '-')}%** of {c['backend'].get('statements', '-'):,} statements. Frontend unit coverage (Vitest v8) over `src/lib`, `src/components` and `src/layouts`: statements **{c['frontend'].get('pct', '-')}%**, branches {c['frontend'].get('branches', '-')}%, functions {c['frontend'].get('funcs', '-')}%; the 25 page components are exercised by the Playwright suite rather than by unit tests.\n\n"
    return head + md_table(["File (services and routers)", "Statements", "Missed", "Coverage"], rows, "lccr")


def table_ingestion():
    rows = []
    for i in D["bench"].get("ingestion", []):
        jm = i["job_ms"]
        rows.append([i["format"], f"{i['rows']:,}", i["file_mb"], i["runs"], f"{jm['mean']:,.0f}", f"{jm.get('p95', jm['mean']):,.0f}" if "p95" in jm else "n/a (1 run)", f"{i['upload_to_ready_ms']['mean']:,.0f}", f"{i['rows_per_second']:,}"])
    return md_table(["Format", "Rows", "File (MB)", "Runs", "Job time mean (ms)", "Job p95 (ms)", "Upload to ready (ms)", "Rows / second"], rows, "lrrrrrrr")


def table_latency():
    rows = []
    for w in D["bench"]["query_latency"]["per_workload"]:
        rows.append([w["workload"], w["engine_p50_ms"], w["engine_p95_ms"], w["http_p50_ms"], w["http_p95_ms"]])
    q = D["bench"]["query_latency"]
    s = q["engine_ms"]
    h = q["http_roundtrip_ms"]
    rows.append([f"**All {q['workloads']} workloads ({q['samples']} samples)**", f"**{s['p50']}**", f"**{s['p95']}**", f"**{h['p50']}**", f"**{h['p95']}**"])
    return md_table(["Workload (30 runs each)", "Engine p50 (ms)", "Engine p95 (ms)", "HTTP round-trip p50 (ms)", "HTTP p95 (ms)"], rows, "lrrrr")


def table_dashboards():
    rows = [[d["template"].title(), d["widgets"], d["server_load_ms"]["p50"], d["server_load_ms"]["p95"], d["http_ms"]["p50"], d["failed_widgets"]] for d in D["bench"]["dashboards"]]
    return md_table(["Dashboard", "Widgets", "Server load p50 (ms)", "p95 (ms)", "HTTP p50 (ms)", "Failed widgets (all loads)"], rows, "lrrrrr")


def table_ask():
    rows = [[a["question"], a["result"], a["http_ms"]["p50"], a["http_ms"]["p95"]] for a in D["bench"]["ask_tara"]]
    return md_table(["Question (10 runs each, offline planner)", "Outcome", "p50 (ms)", "p95 (ms)"], rows, "llrr")


def table_eval():
    e = D["bench"]["evaluation"]
    ca = e["conflict_detection"]
    cc, dc = e["creation_comparison"], e["detection_comparison"]
    g = D["bench"]["tara_generator_session"]
    rows = [
        ["Dataset processing (avg job time)", f"{e['dataset_processing']['avg_ms']:.0f} ms", f"{e['dataset_processing']['jobs']} successful jobs; {e['dataset_processing']['rows_per_second']:,} rows/s"],
        ["Query latency (benchmark of every live metric)", f"avg {e['query_latency']['benchmark_avg_ms']} ms, p95 {e['query_latency']['benchmark_p95_ms']} ms", f"{e['query_latency']['benchmark_queries']} metrics, full {D['bench']['dataset']['rows']:,}-row dataset"],
        ["Validation pass rate", f"{e['validation']['pass_rate']:.0%}", f"{e['validation']['metrics_passing']}/{e['validation']['metrics_checked']} metric definitions re-validated"],
        ["Query success rate", f"{e['query_success']['success_rate']:.1%}", f"{e['query_success']['ok']}/{e['query_success']['total']} executions in the run history"],
        ["Conflict detection precision / recall (automated)", f"{ca['automated']['precision']:.2f} / {ca['automated']['recall']:.2f}", f"{ca['cases']} labelled cases; TP {ca['automated']['tp']}, FP {ca['automated']['fp']}, FN {ca['automated']['fn']}"],
        ["Conflict detection precision / recall (manual text diff baseline)", f"{ca['naive_manual']['precision']:.2f} / {ca['naive_manual']['recall']:.2f}", f"TP {ca['naive_manual']['tp']}, FP {ca['naive_manual']['fp']}, FN {ca['naive_manual']['fn']}"],
        ["AI suggestion acceptance rate (scripted offline session)", f"{e['ai_acceptance']['acceptance_rate']:.0%}" if e["ai_acceptance"]["acceptance_rate"] is not None else "n/a", f"{e['ai_acceptance']['accepted']} accepted of {e['ai_acceptance']['generations']} generations; {e['ai_acceptance']['validity_rate']:.0%} of outputs valid" if e["ai_acceptance"]["validity_rate"] is not None else ""],
        ["Dashboard load time (avg of 5 stored dashboards)", f"{e['dashboard_load']['avg_ms']} ms", f"p95 {e['dashboard_load']['p95_ms']} ms; {e['dashboard_load']['dashboards']} dashboards"],
        ["Metric creation: manual vs AI-assisted", f"{cc['manual_seconds_per_metric_assumed']} s (assumed) vs {cc['ai_assisted_total_seconds_est']} s", f"TARA generation measured at {cc['ai_generation_avg_seconds_measured']} s on average + {cc['review_edit_seconds_assumed']} s assumed human review; estimated saving {cc['time_saved_pct']}%"],
        ["Conflict detection: manual vs automated", f"{dc['manual_seconds_assumed']} s (assumed) vs {dc['automated_ms_measured']} ms", f"{dc['candidate_pairs']} candidate pairs; manual review assumed at {e['assumptions']['manual_pair_review_seconds']} s per pair"],
    ]
    return md_table(["Measure", "Result", "Detail"], rows)


def table_eval_cases():
    ca = D["bench"]["evaluation"]["conflict_detection"]
    rows = [[r["id"], r["description"], ", ".join(r["expected"]) or "none", ", ".join(r["automated"]) or "none", "yes" if r["automated_correct"] else "NO", ", ".join(r["naive"]) or "none", "yes" if r["naive_correct"] else "NO"] for r in ca["rows"]]
    return md_table(["Case", "Scenario", "Expected", "Automated", "Correct", "Manual text diff", "Correct"], rows)


def table_versions():
    req = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    py = {l.split("==")[0].split("[")[0].lower(): l.split("==")[1] for l in req.splitlines() if "==" in l}
    pkg = jload(ROOT / "frontend" / "package.json")
    js = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    return py, js


def table_defects():
    return (SRC / "_defects.md").read_text(encoding="utf-8") if (SRC / "_defects.md").exists() else ""


def table_endpoints():
    return (GEN / "api_reference.md").read_text(encoding="utf-8")


TABLES = {
    "testcases": table_testcases, "suites": table_suites, "coverage": table_coverage, "ingestion": table_ingestion, "latency": table_latency, "dashboards": table_dashboards,
    "ask": table_ask, "eval": table_eval, "evalcases": table_eval_cases, "defects": table_defects, "endpoints": table_endpoints,
    "datadict": lambda: (GEN / "data_dictionary.md").read_text(encoding="utf-8"), "permissions": lambda: (GEN / "permissions.md").read_text(encoding="utf-8"),
}


# ============================================================================= figures / gallery
def img_rel(path: str) -> str:
    return path.replace("\\", "/")


def fig(path: str, caption: str, width: int | None = None) -> str:
    w = f"{{width={width}%}}" if width else ""
    return f"![{caption}]({img_rel(path)}){w}\n"


def gallery(group: str) -> str:
    man = jload(SHOTS / "manifest.json", [])
    if not man:
        return "_Screenshots not generated yet._"
    by = {}
    for m in man:
        by.setdefault(m["file"], {})[m["theme"]] = m
    sel = {"public": lambda f: int(f[:2]) < 20, "app": lambda f: 20 <= int(f[:2]) < 90, "mobile": lambda f: int(f[:2]) >= 90}[group]
    out = []
    for f in sorted(by):
        if not sel(f):
            continue
        title = next(iter(by[f].values()))["title"]
        out.append(f"**{title}**\n")
        for th in ("light", "dark"):
            if th in by[f]:
                out.append(fig(f"screenshots/{th}/{f}", f"{title}, {th} mode", None))
    return "\n".join(out)


MODULE_SHOTS = {
    "dashboard": "Main dashboard", "metrics_catalog": "Metrics catalog", "metric_detail": "Metric detail", "datasets_catalog": "Datasets catalog", "dataset_detail": "Dataset detail",
}


def module_shots(*slugs):
    man = jload(SHOTS / "manifest.json", [])
    out = []
    for slug in slugs:
        for th in ("light", "dark"):
            m = next((x for x in man if x["theme"] == th and x["file"].split("_", 1)[1][:-4] == slug), None)
            if m:
                out.append(fig(f"screenshots/{th}/{m['file']}", f"{m['title']}, {th} mode"))
    return "\n".join(out)


# ============================================================================= placeholder expansion
def titlepage(title: str, subtitle: str) -> str:
    m = META
    rows = [("Project title", m["project"]), ("Document", title), ("Team members", m["student"]), ("Guide", m["guide"]), ("Institution", m["university"]), ("Academic year", m["year"]), ("Date", D["today"] + " (IST)"), ("Status", "University project: academic capstone with synthetic demonstration data")]
    t = "| | |\n|---|---|\n" + "\n".join(f"| **{k}** | {v} |" for k, v in rows)
    return f'<div class="titlepage"></div>\n\n# {title} {{.unnumbered .title-heading}}\n\n*{subtitle}*\n\n{t}\n\n' + PAGEBREAK


PAGEBREAK = '```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```\n\n```{=html}\n<div style="page-break-after:always"></div>\n```\n\n'


def expand(text: str, meta: dict) -> str:
    def inc(m):
        f = GEN / m.group(1)
        return (f if f.exists() else SRC / m.group(1)).read_text(encoding="utf-8")

    text = re.sub(r"\{\{include:([^}]+)\}\}", inc, text)
    text = re.sub(r"\{\{table:(\w+)\}\}", lambda m: TABLES[m.group(1)](), text)
    text = re.sub(r"\{\{gallery:(\w+)\}\}", lambda m: gallery(m.group(1)), text)
    text = re.sub(r"\{\{shots:([\w,]+)\}\}", lambda m: module_shots(*m.group(1).split(",")), text)
    text = re.sub(r"\{\{fig:([^|}]+)\|([^|}]+)(?:\|(\d+))?\}\}", lambda m: fig(m.group(1), m.group(2), int(m.group(3)) if m.group(3) else None), text)
    text = text.replace("{{pagebreak}}", PAGEBREAK)

    def val(m):
        key = m.group(1).strip()
        if key in ("toc", "titlepage"):
            return m.group(0)
        try:
            return fmt(lookup(key))
        except KeyError:
            raise SystemExit(f"unknown placeholder {{{{{key}}}}} in {meta['file']}")

    return re.sub(r"\{\{([a-zA-Z_][\w\.]*)\}\}", val, text)


def number_and_toc(text: str, meta: dict) -> str:
    lines = text.split("\n")
    out, toc, n1, n2, n3, in_code = [], [], 0, 0, 0, False
    for ln in lines:
        if ln.startswith("```"):
            in_code = not in_code
        m = re.match(r"^(#{1,3}) (.+?)(\s*\{[^}]*\})?$", ln)
        if m and not in_code and "unnumbered" not in (m.group(3) or ""):
            lvl, title = len(m.group(1)), m.group(2).strip()
            if lvl == 1:
                n1 += 1; n2 = n3 = 0; num = f"{n1}"
            elif lvl == 2:
                n2 += 1; n3 = 0; num = f"{n1}.{n2}"
            else:
                n3 += 1; num = f"{n1}.{n2}.{n3}"
            sid = f"sec-{num.replace('.', '-')}"
            out.append(f"{m.group(1)} {num} {title} {{#{sid}}}")
            if lvl <= 2:
                toc.append(("  " * (lvl - 1)) + f"- [{num} {title}](#{sid})")
        else:
            out.append(ln)
    body = "\n".join(out)
    toc_md = "## Table of contents {.unnumbered}\n\n" + "\n".join(toc) + "\n\n" + PAGEBREAK
    return body.replace("{{toc}}", toc_md)


def build_md(name: str, title: str) -> Path:
    src = (SRC / f"{name}.md").read_text(encoding="utf-8")
    m = re.match(r"<!--\s*subtitle:\s*(.*?)\s*-->\n", src)
    subtitle = m.group(1) if m else ""
    src = src[m.end():] if m else src
    meta = {"file": name}
    src = src.replace("{{titlepage}}", titlepage(title, subtitle))
    src = expand(src, meta)
    src = number_and_toc(src, meta)
    final = DOCS / f"{name}.md"
    final.write_text(src, encoding="utf-8")
    return final


# ============================================================================= export (DOCX via pandoc, PDF via Chromium)
def prepare_images(md_text: str) -> str:
    """Resized copies for export + sensible figure widths (tall screenshots must not overflow a page)."""
    from PIL import Image

    def repl(m):
        alt, path, attr = m.group(1), m.group(2), m.group(3) or ""
        src = DOCS / path
        if not src.exists():
            return m.group(0)
        rel = path.replace("/", "_")
        dst = BUILD / "img" / (Path(rel).stem + ".png")
        try:
            im = Image.open(src)
            w, h = im.size
            maxw = 1500 if "diagrams" in path or "charts" in path else 1280
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                im2 = im.convert("RGB") if im.mode in ("RGBA", "P") else im
                if w > maxw:
                    im2 = im2.resize((maxw, int(h * maxw / w)))
                im2.save(dst, optimize=True)
            ratio = w / h
            pct = 92 if ratio >= 1.35 else int(max(30, min(92, 8.4 / 6.3 * ratio * 100 * 0.92)))
            if "{width" not in attr:
                attr = f"{{width={pct}%}}"
            return f"![{alt}](_build/img/{dst.name}){attr}"
        except Exception:  # noqa: BLE001
            return m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)(\{[^}]*\})?", repl, md_text)


def export(name: str, title: str):
    import pypandoc

    final = DOCS / f"{name}.md"
    text = prepare_images(final.read_text(encoding="utf-8"))
    exp_md = BUILD / f"{name}.export.md"
    exp_md.write_text(text, encoding="utf-8")
    meta_args = ["--metadata", f"title={title}", "--metadata", f"author={META['student']}", "--metadata", f"lang=en-IN"]
    docx = EXPORTS / f"{name}.docx"
    pypandoc.convert_file(str(exp_md), "docx", outputfile=str(docx), format="markdown+pipe_tables+raw_attribute+implicit_figures+header_attributes", extra_args=[f"--resource-path={DOCS}", "--wrap=none"] + meta_args)
    postprocess_docx(docx, title)
    htmlf = BUILD / f"{name}.html"
    html_args = [f"--resource-path={DOCS}", "--standalone", "--embed-resources", "--wrap=none", "--metadata", f"pagetitle={title}", "--metadata", "lang=en-IN", "--css", str(DOCS / "tools" / "report.css")]
    if name in COMPACT:  # short documents: do not start every chapter on a new page
        html_args += ["--css", str(DOCS / "tools" / "report_compact.css")]
    pypandoc.convert_file(str(exp_md), "html5", outputfile=str(htmlf), format="markdown+pipe_tables+raw_attribute+implicit_figures+header_attributes", extra_args=html_args)
    pdf = EXPORTS / f"{name}.pdf"
    subprocess.run(["node", str(DOCS / "tools" / "html_to_pdf.mjs"), str(htmlf), str(pdf), f"{META['student']} | {title}"], check=True)
    return docx, pdf


def postprocess_docx(path: Path, title: str):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document(str(path))
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.0)
        s.top_margin = s.bottom_margin = Cm(2.0)
        # footer with page number
        p = s.footer.paragraphs[0] if s.footer.paragraphs else s.footer.add_paragraph()
        p.text = f"{META['student']} | {title} | Page "
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        for t, txt in (("begin", None), (None, "PAGE"), ("end", None)):
            if t:
                el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), t); run._r.append(el)
            else:
                it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = txt; run._r.append(it)
        for r in p.runs:
            r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    styles = doc.styles
    for nm, size in (("Normal", 10.5), ("Body Text", 10.5), ("First Paragraph", 10.5), ("Compact", 9.5)):
        if nm in [s.name for s in styles]:
            styles[nm].font.name = "Calibri"; styles[nm].font.size = Pt(size)
    for nm, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12), ("Title", 24)):
        if nm in [s.name for s in styles]:
            styles[nm].font.name = "Calibri"; styles[nm].font.size = Pt(size); styles[nm].font.color.rgb = RGBColor(0x11, 0x11, 0x11); styles[nm].font.bold = True
    for tbl in doc.tables:
        tbl.style = doc.styles["Table Grid"] if "Table Grid" in [s.name for s in doc.styles] else tbl.style
        tbl.autofit = True
        tblPr = tbl._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            b = OxmlElement(f"w:{edge}"); b.set(qn("w:val"), "single"); b.set(qn("w:sz"), "4"); b.set(qn("w:color"), "BBBBBB"); borders.append(b)
        tblPr.append(borders)
        for ri, row in enumerate(tbl.rows):
            for cell in row.cells:
                for para in cell.paragraphs:
                    for r in para.runs:
                        r.font.size = Pt(8.5)
                if ri == 0:
                    tcPr = cell._tc.get_or_add_tcPr()
                    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "E8E8E8"); tcPr.append(shd)
                    for para in cell.paragraphs:
                        for r in para.runs:
                            r.font.bold = True
    for p in doc.paragraphs:
        if p.text.startswith("<code") or "```" in p.text:
            continue
    doc.core_properties.author = META["student"]
    doc.core_properties.title = title
    doc.save(str(path))


def main():
    only_md = "--no-export" in sys.argv
    sel = [a for a in sys.argv[1:] if not a.startswith("--")]
    for name, title in DOCS_LIST:
        if sel and not any(s in name for s in sel):
            continue
        if not (SRC / f"{name}.md").exists():
            print("missing source", name)
            continue
        build_md(name, title)
        print("built", name + ".md")
        if not only_md:
            d, p = export(name, title)
            print("  exported", d.name, f"{d.stat().st_size // 1024} KB;", p.name, f"{p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
