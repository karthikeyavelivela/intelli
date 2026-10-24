<!-- subtitle: Architecture, data design and API reference (generated from the code) -->
{{titlepage}}

{{toc}}

# Overview

IntelliMetrics AI is a three-layer web application with a separate background-job layer. This document describes the architecture with diagrams, the data design (ER diagram and data dictionary) and the API. The API reference, data dictionary, permission matrix and statistics in this document are **generated from the source code** by `docs/tools/gen_reference.py`; they are not hand-written, so they cannot drift from the implementation.

| Fact (generated) | Value |
|---|---|
| API endpoints | {{stats.endpoints}} |
| Routers | {{stats.routers}} |
| Database tables | {{stats.tables}} |
| Role capabilities | {{stats.capabilities}} |
| Back-end source | {{stats.backend_py.0}} Python files, {{stats.backend_py.1}} lines |
| Back-end tests | {{stats.backend_tests.0}} files, {{stats.backend_tests.1}} lines |
| Front-end source | {{stats.frontend_src.0}} TypeScript files, {{stats.frontend_src.1}} lines; {{stats.pages}} page components |
| End-to-end tests | {{stats.e2e.0}} files, {{stats.e2e.1}} lines |

# High-level architecture

{{fig:diagrams/01_high_level_architecture.png|High-level architecture|95}}

The browser talks only to Nginx (production) or the Vite dev proxy (development), so the SPA and API share one origin and the httpOnly cookies are first-party. FastAPI authenticates every request, authorises it by capability, filters every query by workspace, and delegates work to services. Long-running ingestion is placed on a Celery queue (Redis) and executed by a worker. Analytical queries are never sent to PostgreSQL: they run in DuckDB over Parquet files produced by ingestion.

# Component diagram

{{fig:diagrams/02_component_diagram.png|Components of the front end and back end|85}}

Responsibilities are layered so that safety-critical logic exists once: the **formula compiler** is used by the Formula Lab, metric validation, the TARA generator, the Ask TARA pipeline, dashboards and the evaluation module. The **planner** only produces a query plan; the **engine** executes it.

# Deployment diagram

{{fig:diagrams/03_deployment_diagram.png|Docker Compose deployment (and optional VPS TLS terminator)|85}}

Persistent volumes: `pgdata` (PostgreSQL), `redisdata` (Redis append-only file) and `datasets` (raw uploads and Parquet), the last mounted in both the API and the worker so the worker's output is visible to the API. The backend container runs `alembic upgrade head` on every start and seeds the demonstration data when `AUTO_SEED=true` and the database is empty.

# Request flow: Ask TARA

{{fig:diagrams/04_ask_tara_request_flow.png|Sequence of an Ask TARA question|100}}

Key safety properties of this flow:

1. The planner receives only the **authorised catalog** (live or approved metrics of the user's own workspace on ready datasets) and today's date in IST.
2. Its output is a JSON *plan*, validated by Pydantic and then by `validate_plan`, which rejects unknown metrics or columns; a forged plan cannot reach the database.
3. The SQL is produced by the same compiler as in the Formula Lab; every value is a bound parameter.
4. The answer text is composed from the returned rows; the AI does not write the figures.

# Dataset ingestion pipeline

{{fig:diagrams/05_dataset_ingestion_pipeline.png|Ingestion pipeline|75}}

Uploads are streamed to disk in 1 MiB chunks with an extension whitelist, a size limit and a magic-byte check. The job converts to ZSTD-compressed Parquet with DuckDB `COPY` (CSV rejects are recorded in an error report), normalises column names to snake_case, detects the schema and the default date column, and profiles every column in a single scan (null counts, approximate distinct counts, min, max, mean, standard deviation, top values) plus a duplicate-row count. External PostgreSQL/MySQL tables are streamed in 50,000-row chunks through a read-only session into a PyArrow Parquet writer.

# Formula compile pipeline

{{fig:diagrams/06_formula_compile_pipeline.png|Formula lexer, parser, type checker and SQL generator|60}}

## Grammar

```
formula   := expr [ WHERE bool ]
expr      := term (('+' | '-') term)*
term      := unary (('*' | '/' | '%') unary)*
unary     := '-' unary | primary
primary   := NUMBER | STRING | DATE STRING | TRUE | FALSE | NULL
           | '(' expr ')' | call | IDENT | '[' Metric Name ']'
call      := NAME '(' [ '*' | arg (',' arg)* ] ')'     -- whitelisted NAME only
bool      := and (OR and)* ;  and := not (AND not)* ;  not := [NOT] cmp
cmp       := expr (('='|'!='|'<>'|'<'|'<='|'>'|'>=') expr
                  | [NOT] IN '(' expr (',' expr)* ')' | [NOT] BETWEEN expr AND expr
                  | [NOT] LIKE STRING | IS [NOT] NULL) | '(' bool ')'
aggregates: SUM AVG MIN MAX COUNT COUNT_DISTINCT MEDIAN STDDEV SUMIF COUNTIF AVGIF
scalars:    ABS ROUND COALESCE IF NULLIF UPPER LOWER YEAR MONTH LENGTH
```

Limits: 2,000 characters, nesting depth 40, 200 items per `IN` list, 10,000 returned rows, 20-second timeout (all configurable). Semantic rules: columns must exist (a close-match suggestion is offered), `SUM/AVG/MEDIAN/STDDEV` require numeric input, text and date comparisons are type-checked, ISO date strings are coerced to dates, aggregates cannot be nested or mixed with row-level columns, a top-level formula must be a numeric aggregate expression, metric references must be live and defined on the same dataset.

# Conflict detection flow

{{fig:diagrams/07_conflict_detection_flow.png|Conflict detection|80}}

Severity rules: the maximum severity of the differences, raised to *critical* when the reference is live and the variant is already in review/approved/published with a formula, aggregation or dataset difference, or when three or more difference types are present together with a high one.

# State machines

{{fig:diagrams/08_metric_state_machine.png|Metric lifecycle and version policy|75}}

{{fig:diagrams/09_conflict_workflow_state.png|Conflict workflow|75}}

{{fig:diagrams/13_dashboard_version_policy.png|Dashboard version policy: latest published or pinned|70}}

# Security architecture

## Role-based access control

{{fig:diagrams/10_rbac_permission_flow.png|Permission flow for every request|60}}

{{table:permissions}}

Additional rules enforced in code: an author cannot approve their own metric (except an Admin); rejection requires a comment; users cannot demote or deactivate themselves; demo-account passwords cannot be changed; every sensitive action is audit-logged with user, entity, details, IP and request id.

## Workspace isolation

{{fig:diagrams/11_workspace_isolation.png|Workspace isolation|85}}

## Other controls

| Control | Implementation |
|---|---|
| Password storage | Argon2id hashes (argon2-cffi) |
| Sessions | JWT access token (15 min) and rotating refresh token (7 days, stored hashed) in httpOnly, SameSite cookies; `Secure` when `COOKIE_SECURE=true` |
| CSRF | State-changing cookie-authenticated requests must carry `X-Requested-With: IntelliMetrics` |
| Rate limiting | Sliding window per IP on authentication routes (per process) |
| Secrets | Environment variables only; connection passwords encrypted with Fernet; AI keys never reach the browser |
| Input validation | Pydantic v2 on every request; consistent error envelope with request id |
| SQL safety | No raw SQL accepted; restricted grammar; parameters; read-only DuckDB views; timeouts and row limits |
| Upload safety | Extension whitelist, size limit, magic-byte sniffing, binary rejection, stored outside the web root |
| Immutability | ORM guard plus database trigger on `metric_versions` |

# Indian calendar and planner

{{fig:diagrams/12_fiscal_calendar_and_planner.png|Fiscal calendar handling in the planner|60}}

# Data design

## Entity-relationship diagram

{{fig:diagrams/er.png|Entity-relationship diagram (keys and identifying columns; all columns are listed in the data dictionary)|100}}

The diagram is wide; for a legible full-size version open `docs/diagrams/er.svg` (zoomable vector) or `docs/diagrams/er.png`. Notes: every business table references `workspaces` (tenant boundary). `metrics` holds the working copy; `metric_versions` holds immutable snapshots; `metric_reviews` is the append-only approval log; `conflicts` references the reference metric and the variant; `dashboards.widgets` is a JSON layout whose entries reference metric keys and optional pinned version numbers; `ingestion_jobs` and `executions` are the telemetry that the evaluation module analyses.

## Data dictionary

{{table:datadict}}

# API reference summary

All endpoints are under `/api` (health at `/health`); interactive OpenAPI documentation is served at `/docs` and the schema at `/openapi.json`. Errors use one envelope: `{"error": {"code", "message", "details", "request_id"}}`. The *Roles allowed* column is derived from the `require(capability)` dependency on each route and the permission matrix.

{{table:endpoints}}

# Use cases by role

{{fig:diagrams/14_use_case_roles.png|Use cases by role|55}}
