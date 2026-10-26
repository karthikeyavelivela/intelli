# Slide-by-slide outline

The deck `exports/08_Presentation.pptx` contains these slides, with the speaker notes below in the PowerPoint notes pane.


## Slide 1: IntelliMetrics AI

* A governed semantic layer with TARA, an AI assistant for trusted business metrics
* Devi Priya, Priyanka, Akshay and Bhaskar
* KL University | AY 2026-27
* University project (academic capstone). Demonstration data is synthetic.

*Speaker notes:* Introduce yourself, the guide and the project name. Say at once that it is a university project with synthetic data.

## Slide 2: The problem: one word, many numbers

* Sales: Revenue = taxable value of goods sold (excluding GST)
* Finance: Revenue = sales less refunds
* Marketing: Revenue = invoice value including GST
* Nobody notices until two reports disagree; changes are not recorded
* Generic AI chatbots answer confidently even when wrong

*Speaker notes:* Use the Indian GST example because the audience recognises it. Stress that nobody is lying; the same word means different calculations.

## Slide 3: Objectives

* One governed live definition per business metric
* Detect conflicting definitions automatically and measure the detector
* Immutable version history with safe rollback
* Let non-technical users ask questions without risking wrong or unsafe queries
* Localise to India: INR (lakh/crore), April-March FY, GST, festivals, IST

*Speaker notes:* Map each objective to a result later in the talk.

## Slide 4: The solution at a glance

* Datasets in, governed metrics and dashboards out
* Workflow: draft, review, approve, publish (exactly one live per metric)
* Conflict centre: assign, review, approve, resolve
* Formula Lab: safe, parameterised execution
* Ask TARA: plain-English questions answered from approved metrics
* 96 API endpoints | 25 pages | 4 roles | 2 isolated workspaces

*Visual:* `diagrams/14_use_case_roles.png`

*Speaker notes:* Give the one-minute product tour using the use-case diagram: four roles, each with a distinct job.

## Slide 5: Architecture

* React + TypeScript single-page app
* FastAPI back end: RBAC on every route, workspace filter on every query
* PostgreSQL / SQLite for metadata, DuckDB + Parquet for analytics
* Celery + Redis for background ingestion (thread fallback)

*Visual:* `diagrams/01_high_level_architecture.png`

*Speaker notes:* Explain that analytics never touch the transactional database; DuckDB reads Parquet files produced by ingestion.

## Slide 6: Governance: versions that cannot be changed

* Partial unique index: one live definition per metric key
* Version rows immutable: ORM guard + database trigger
* Rollback creates a NEW version; history is never rewritten
* Dashboards follow latest published or pinned versions

*Visual:* `diagrams/08_metric_state_machine.png`

*Speaker notes:* Say that the guarantee is in the database, so a bug in the application cannot break it. Verified on real PostgreSQL 18.

## Slide 7: A formula engine that cannot be injected

* Lexer, recursive-descent parser, typed syntax tree
* Whitelisted functions; columns checked against the schema
* Every value is a bound parameter; division is zero-safe
* Limits: 2,000 characters, depth 40, 10,000 rows, 20 s timeout
* 25 hostile inputs tested: all rejected before execution

*Visual:* `diagrams/06_formula_compile_pipeline.png`

*Speaker notes:* No user text ever becomes SQL text. That is why injection is structurally impossible rather than filtered.

## Slide 8: Automatic conflict detection

* Compares formula, aggregation, filters, unit, time window, dataset
* Severity score, side-by-side diff, recommended resolution
* 27 labelled cases: precision 1.00, recall 1.00
* Plain text comparison baseline: precision 0.55, recall 0.81

*Visual:* `diagrams/07_conflict_detection_flow.png`

*Speaker notes:* Be candid: the cases were written by me, so this shows the rules behave as designed and is not an independent benchmark.

## Slide 9: Ask TARA: the AI never writes numbers

* Question becomes a plan; the plan is validated against approved metrics
* Same safe compiler runs it; the answer text is composed from rows
* Compare ranges, second dimension, share of total, default fallbacks
* Refuses when the data cannot answer

*Visual:* `diagrams/04_ask_tara_request_flow.png`

*Speaker notes:* Walk through the sequence diagram. Mention the offline deterministic mode and that no live AI key was used.

## Slide 10: Built for India

* INR with lakh/crore grouping; compact forms ₹45 L, ₹1.2 Cr
* Financial year 1 April to 31 March; fiscal quarters
* GST: taxable value vs invoice value; slabs 0/5/12/18/28 %
* Festival windows: Diwali, Dussehra, Pongal, Eid, Holi, End-of-Season sale
* DD-MMM-YYYY dates in IST

*Visual:* `diagrams/12_fiscal_calendar_and_planner.png`

*Speaker notes:* Explain that 'last quarter' resolves to the last completed fiscal quarter, and 'this year' to the financial year to date.

## Slide 11: Demonstration

* Reviewer: detect and resolve the Revenue conflict
* Analyst: Formula Lab, including a rejected injection
* Business user: Diwali comparison and UPI vs COD split
* Admin: audit log; other workspace: no cross-company data

*Visual:* `screenshots/light/41_ask_tara_empty.png`

*Speaker notes:* Run the live demo here (8 minutes). The screenshot is a backup if the demo fails.

## Slide 12: Testing

* 325 automated tests, 0 failed
* pytest 136 (+ 136 on PostgreSQL 18), Vitest 40, Playwright 13
* Back-end statement coverage 82.8 %
* Security tests: injection, token forgery, CSRF, isolation, escalation
* Every page screenshotted in light and dark mode

*Visual:* `charts/tests_by_suite.png`

*Speaker notes:* Each row of the test-case table in the report is linked to a measured result, so the table cannot claim a pass that did not happen.

## Slide 13: Measured performance

* Query engine median 6.37 ms, p95 12.77 ms on 62,000 rows
* Ingestion about 86,494 rows per second
* Dashboard load 167.2 ms on average
* Time-saving estimates rely on stated assumptions, not measurements

*Visual:* `charts/query_latency.png`

*Speaker notes:* Single-user numbers from one Windows machine. Say clearly that there was no load test.

## Slide 14: Honest limitations

* Docker Compose tested on GitHub Actions, not on our own machines
* No live AI provider tested; offline planner only
* Synthetic data; no user study; no external security audit
* Chromium only; no load test; per-process rate limiter
* Verified instead: PostgreSQL 18.2, Redis + Celery, MySQL 8.0

*Speaker notes:* Say these before the examiner asks. It builds trust.

## Slide 15: Future scope and conclusion

* Evaluate with a real LLM on a held-out question set
* Redis-backed rate limiting; e-mail delivery; single sign-on
* Column-level security; connectors to real BI sources; user study
* One definition, one history, answers you can trace

*Speaker notes:* Close with the contribution: an integrated, tested, honest implementation.

## Slide 16: Thank you. Questions?

* Devi Priya, Priyanka, Akshay and Bhaskar
* Documents: Project Report, Concept Note, Architecture, Testing Report, User Guide, Deployment Guide, Viva Preparation

*Speaker notes:* Invite questions. The Viva Preparation document lists forty likely ones.
