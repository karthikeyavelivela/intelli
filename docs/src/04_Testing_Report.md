<!-- subtitle: Test strategy, test cases, results, performance measurements and limitations -->
{{titlepage}}

{{toc}}

# Introduction

This report describes how IntelliMetrics AI was tested and what the tests showed. Every figure in it is **substituted automatically from the files produced by the test runs** (JUnit XML, coverage JSON, Playwright JSON, and the benchmark script's JSON output stored in `docs/data`). None of the numbers was typed in by hand, so the report cannot disagree with the evidence. The final section states plainly what was **not** tested.

| Headline | Result |
|---|---|
| Automated tests executed | {{tests.total}} |
| Passed / failed | {{tests.passed}} / {{tests.failed}} |
| Back-end tests (SQLite) | {{tests.pytest.total}} run, {{tests.pytest.passed}} passed |
| Same back-end suite on real PostgreSQL 18 | {{tests.pytest_pg.total}} run, {{tests.pytest_pg.passed}} passed |
| Front-end unit/component tests (Vitest) | {{tests.vitest.total}} run, {{tests.vitest.passed}} passed |
| Browser end-to-end tests (Playwright, Chromium) | {{tests.playwright.total}} run, {{tests.playwright.passed}} passed |
| Back-end statement coverage | {{cov.backend.pct}} % of {{cov.backend.statements}} statements |
| Test machine | {{env.os}}, Python {{env.python}}, {{env.cpus}} logical CPUs |

# Test strategy

Testing follows the usual pyramid, with extra emphasis on the places where a wrong result would damage trust: the formula compiler (security), the planner (correctness of AI-assisted answers), conflict detection (the central feature) and workspace isolation (privacy).

| Level | Tooling | What it proves |
|---|---|---|
| Unit | pytest | Formula lexer/parser/compiler, formatters, fiscal-calendar logic, planner rules, severity scoring, canonical forms |
| Integration / API | pytest with FastAPI `TestClient` | Every router, with a real database, real DuckDB queries over real Parquet files, background ingestion, SSE streaming |
| Security | pytest | Injection, token tampering, CSRF, rate limiting, secret leakage, path traversal, mass assignment, role escalation |
| Database portability | pytest against PostgreSQL 18 | The same tests pass on the production-grade database, using schema built by Alembic migrations |
| Component | Vitest + Testing Library | Accessible UI primitives, route guard, formatters, API client (refresh, CSRF, SSE) |
| End-to-end | Playwright (Chromium) | Real browser against real front end and real back end: login, upload, metric creation, conflict workflow, Formula Lab, Ask TARA, dashboards, registration |
| Performance | `scripts/benchmark.py` | Ingestion throughput, query and dashboard latency, Ask TARA latency, conflict-detection time |
| Evaluation | in-app Evaluation module | Precision/recall of conflict detection on {{bench.evaluation.conflict_detection.cases}} labelled cases |
| Data quality | pytest on the seeded dataset | Indian formats, GST reconciliation, festival seasonality |
| Visual | Playwright screenshot sweep | Every page in light and dark mode, desktop and mobile, with console-error, 5xx and overflow checks |

**Determinism.** The default AI mode is an offline rule-based planner, so every test is repeatable without network access or API keys. The AI-provider code paths (timeouts, malformed JSON, hallucinated columns) are tested with a mocked provider; no real OpenAI or Gemini call was made (see Limitations).

# Test environment

| Item | Value |
|---|---|
| Operating system | {{env.os}} |
| Python | {{env.python}} (back end), Node.js {{ver.node}} (front end) |
| Databases used for tests | SQLite (default) and PostgreSQL 18.2 started as an isolated throw-away server on its own port |
| Analytics engine | DuckDB {{bench.environment.duckdb}}, Polars {{bench.environment.polars}} |
| Browser | Playwright Chromium |
| Dataset | `sales_transactions`: {{bench.dataset.rows}} rows, {{bench.dataset.columns}} columns, Parquet {{bench.dataset.parquet_bytes}} bytes |
| Seeding time | {{bench.seed_seconds}} s for the complete demo (users, 62,000 sales rows, metrics, dashboards) |

# Results by suite

{{table:suites}}

{{fig:charts/tests_by_suite.png|Automated tests by suite|70}}

# Coverage

{{table:coverage}}

{{fig:charts/backend_coverage.png|Back-end statement coverage for the lowest-covered service and router files|80}}

Coverage is reported honestly: files with lower coverage are mostly code paths that need external systems (live AI providers, external MySQL/PostgreSQL, Celery with Redis). Those paths were verified separately by scripts (section 11) rather than by unit tests, and the lines they execute are therefore counted as *missed* here.

# Functional test cases

Each row below is linked to automated test results by a pattern match on the test name. The *Actual result* column shows how many underlying test cases matched and passed; a row is marked **FAIL** or **Not run** if no matching passing result exists, so the table cannot claim a pass that did not happen.

{{table:testcases}}

# Security testing

| Threat | Test | Result |
|---|---|---|
| SQL injection via formulas | 25 hostile formulas (`; DROP TABLE`, comments, `read_csv`, `UNION`, backticks, nested aggregates, unknown columns) | all rejected before execution; literals are bound parameters |
| SQL injection via query strings | `' OR 1=1 --`, `'; DROP TABLE metrics; --`, `UNION SELECT password_hash ...` on three list endpoints | inert; the tables remain intact |
| Forged AI plan | Mocked planner returns a forbidden dimension and an unknown metric | rejected by `validate_plan`; nothing executed |
| Token forgery | wrong signature, expired token, refresh token used as access token, `alg=none` | every variant returns 401 |
| CSRF | cookie-authenticated POST without the custom header | 403 |
| Brute force | repeated logins from one address | 429 after the configured limit |
| Cross-tenant access | user of workspace B requests workspace A's dataset, metric, versions, execution | 404 everywhere |
| Privilege escalation | Business User changes own role; Analyst creates an Admin | 403 / role unchanged |
| Secret leakage | search API responses for password hashes, Fernet ciphertext, secret key, API-key names | none present; connection passwords shown only as `********` |
| Path traversal in uploads | file name `../../../evil name.csv` | stored inside the data directory under a generated name |
| Malicious files | `.exe`, empty file, fake Parquet, binary CSV | rejected before processing |
| Information disclosure in errors | malformed login, unknown ids | uniform error envelope with a request id; no stack traces |

These checks are automated (`backend/tests/test_security.py`, `test_auth_rbac.py`, `test_formula.py`, `test_governance.py`). They are an application-level assessment; **no external penetration test or dependency-vulnerability scan was performed**.

# Performance measurements

All values were measured on the machine described in section 3, on the {{bench.dataset.rows}}-row dataset, with the offline AI mode, SQLite for application data and the in-process job runner. A production deployment on PostgreSQL with Celery will have different absolute numbers; the relative picture (DuckDB over Parquet is fast, ingestion is the heavy step) is what matters.

## Dataset ingestion

{{table:ingestion}}

{{fig:charts/ingestion_time.png|Dataset ingestion time by format|75}}

## Metric query latency

{{table:latency}}

{{fig:charts/query_latency.png|Engine and HTTP latency per workload|85}}

## Dashboard load

{{table:dashboards}}

{{fig:charts/dashboard_load.png|Dashboard load time|70}}

## Ask TARA

{{table:ask}}

{{fig:charts/ask_tara_latency.png|Ask TARA latency by question|80}}

The latency of Ask TARA here is that of the **offline** planner. A live AI provider adds one network round-trip for planning (typically a few hundred milliseconds to several seconds); that was not measured.

## Conflict detection

Detection over the seeded workspace created {{bench.conflict_detection_result.created}} conflicts and took a mean of {{bench.conflict_detection_ms.mean}} ms (p95 {{bench.conflict_detection_ms.p95}} ms over {{bench.conflict_detection_ms.n}} runs).

# Evaluation results (the project's research questions)

{{table:eval}}

{{fig:charts/conflict_detection_quality.png|Conflict-detection quality: automated detector versus a naive text comparison|75}}

{{fig:charts/evaluation_rates.png|Evaluation rates|75}}

## Labelled ground truth for conflict detection

The detector was tested against {{bench.evaluation.conflict_detection.cases}} cases with known correct answers, including identical definitions that differ only in case or spacing (which must *not* be flagged), single differences of each type, combinations, and the GST-inclusive versus ex-GST revenue case.

{{table:evalcases}}

## Honest reading of these results

* The perfect precision and recall of the automated detector hold for these labelled cases, **which were written by the author of the detector**. They show that the rules behave as designed; they are not an independent benchmark and should not be read as a general accuracy claim.
* The *manual text-diff* baseline is a simple string comparison used as a stand-in for a person eyeballing two formulas. It is not a human study.
* The **time-saving figures for metric creation and conflict review depend on assumed manual durations** ({{bench.evaluation.assumptions.manual_metric_creation_seconds}} s per metric and {{bench.evaluation.assumptions.manual_pair_review_seconds}} s per pair). They are labelled as assumptions in the application and here. Only the machine times (milliseconds) are measured.
* The AI acceptance rate is from a **scripted offline session** of {{bench.tara_generator_session.prompts}} prompts, two of them deliberately unanswerable; it is not a user study.

# Defects found and fixed during testing

{{table:defects}}

# Verification of external services

Because Docker was not available on the development machine, the services that Docker Compose would provide were verified **individually, as isolated throw-away servers on spare ports**, without touching any service the user already had running.

| Service | What was run | Result |
|---|---|---|
| PostgreSQL 18.2 | Alembic migrations from an empty database, then the complete pytest suite ({{tests.pytest_pg.total}} tests) | passed |
| PostgreSQL 18.2 as an import source | Create a connection, store the password encrypted, list tables, stream a table into Parquet, attempt a write | {{conns.postgres.rows_imported}} rows imported in {{conns.postgres.import_job_ms}} ms; password encrypted at rest; a write was rejected by the read-only session |
| Redis + Celery | Real Celery worker (`--pool=solo`) consuming from a real Redis broker; a {{celery.rows}}-row CSV upload processed by the worker, application data in PostgreSQL | status `{{celery.status}}`, runner `{{celery.runner}}`, job {{celery.job_ms}} ms, upload to ready {{celery.upload_to_ready_ms}} ms; progress states pending, processing, ready all observed |
| MySQL 8.0.40 as an import source | The same connection test against MySQL | {{conns.mysql.rows_imported}} rows imported in {{conns.mysql.import_job_ms}} ms; password encrypted at rest; a write was rejected by the read-only session |
| Demonstration walkthrough | `scripts/verify_walkthrough.py` against the running back end after a full reset and re-seed: six logins, role restrictions, conflict workflow, Formula Lab with an injection attempt, eight Ask TARA questions, dashboard widgets, audit log and cross-workspace isolation | {{walk.passed}} of {{walk.total}} checks passed |
| Screenshot sweep | `frontend/e2e/shots.mjs`: every page in light and dark, desktop and 390 px phone, checking console errors, HTTP 5xx and horizontal overflow | The sweep found one real overflow bug (defect 16), fixed; the final run reported no problems |
| Image URLs | HTTP request for each of the {{img.total}} stock-image URLs used by the site | {{img.ok}} returned HTTP 200 |
| Commercial-language check | `scripts/check_no_pricing.py` over all source, configuration and documentation files | {{langcheck.unexplained}} unexplained hits; {{langcheck.allow_listed}} allow-listed hits that use an unrelated sense of a word (a TARA "plan", the Alembic `upgrade` command, a product unit price in the sales data, or a test that asserts pricing is absent) |

# Visual and accessibility checks

A Playwright sweep (`frontend/e2e/shots.mjs`) visited every page in light and dark mode at desktop and phone widths and checked for console errors, HTTP 5xx responses and horizontal overflow. The pages are shown in the User Guide and listed in `docs/screenshots`. Accessibility is supported by semantic HTML, labelled form controls, visible focus rings, `aria-live` regions for toasts, keyboard-operable tables and tabs, and a Vitest suite that asserts these attributes. **No formal WCAG audit or screen-reader test was performed.**

# Test data

The demonstration data is synthetic and generated by `backend/app/seed_data.py` with a fixed random seed, so every run produces the same rows. It models an Indian omnichannel retailer: 62,000 order lines across 27 cities in 18 states across five regions, GST slabs of 0/5/12/18/28 %, payment methods (UPI, cards, net banking, wallets, cash on delivery), festive-season demand peaks (Diwali, Dussehra, Pongal/Sankranti, Eid, Holi, End-of-Season sale) and a higher return rate for cash on delivery. Customer names, phone numbers (`+91 90000 ...`) and e-mails (`example.com`) are fictional. No real person's data is used anywhere.

# Reproducing the tests

```bash
# back end (SQLite)
cd backend && python -m pytest tests -q --cov=app

# back end against PostgreSQL (after creating an empty database and running alembic upgrade head)
TEST_DATABASE_URL=postgresql://user:pass@host:5432/db TEST_SKIP_CREATE_ALL=1 python -m pytest tests -q

# front end
cd frontend && npx vitest run --coverage.enabled
npx playwright test            # starts its own back end and front end on ports 8100 and 5273

# performance benchmark
python scripts/benchmark.py
```

# Limitations: what was not tested

An honest list, so that nobody reads more into this report than it supports.

1. **Docker was not run on the authors' computers** (it is not installed there). The container images, the Compose stack and a scripted smoke test (`scripts/compose_smoke.sh`) run on GitHub's Linux runner instead and pass; locally each service was verified individually (PostgreSQL, Redis + Celery, MySQL). Behaviour beyond the smoke test (restarts, volume backups, version updates) was not exercised.
2. **No live AI provider was used.** There was no OpenAI or Gemini key. The provider adapters were tested with mocked responses only; real-model behaviour, cost and latency are unmeasured. The offline deterministic mode is what was exercised end to end.
3. **No load or concurrency testing** beyond single-user latency measurements. Behaviour with many simultaneous users is unmeasured. The rate limiter is per-process, so it would need Redis-backed storage to be correct with several API workers.
4. **No external security assessment.** Only the application-level tests above.
5. **Only Chromium was used** for browser tests; Firefox and Safari were not tested. Layout was checked at desktop and 390 px phone widths only.
6. **No usability study with real users**; the manual-effort comparisons use stated assumptions.
7. **The Windows development machine only.** Linux and macOS were not used, although the code uses portable paths and the Compose files target Linux containers.
8. **External MySQL/PostgreSQL import** was verified against isolated local servers, not against a managed cloud database.
9. **Backups, restore and zero-downtime updates** are documented in the Deployment Guide but were not exercised.
10. **The GitHub Actions workflow** (`.github/workflows/ci.yml`) runs on every push. Its first run exposed one date-dependent test (a Diwali-season expectation that changed when the 2026 season started); it was fixed by freezing "today" in the test, and all five jobs now pass.
