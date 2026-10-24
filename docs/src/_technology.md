| Technology | Version | Purpose in this project | Why chosen | Alternatives considered |
|---|---|---|---|---|
| **React** | {{ver.react}} | Component-based UI for all pages | Largest ecosystem, hooks, mature testing tools; fits the many interactive widgets (grid, charts, chat) | Vue, Svelte, Angular |
| **TypeScript** | {{ver.typescript}} | Static typing for the front end | Catches API-shape and prop errors at build time (`tsc --noEmit` is part of CI) | Plain JavaScript |
| **Vite** | {{ver.vite}} | Dev server, proxy and production build | Very fast HMR; simple proxy of `/api`; small config | Create React App (deprecated), webpack, Next.js |
| **Tailwind CSS** | {{ver.tailwindcss}} | Styling through design tokens (CSS variables) | Utility classes + variables give a strict black/white brand with one accent and instant light/dark themes | CSS modules, Chakra UI, Material UI |
| **shadcn-style components on Radix UI** | dialog {{ver.radix_ui_react_dialog}}, tabs {{ver.radix_ui_react_tabs}}, dropdown {{ver.radix_ui_react_dropdown_menu}} | Accessible dialog, tabs and menu primitives wrapped in local components (`components/ui`) | Accessibility (focus trap, ARIA, keyboard) without a heavy theme; components are owned in the repo | MUI, Ant Design, Headless UI |
| **Recharts** | {{ver.recharts}} | Line, bar, area, pie, grouped charts | Declarative React charts, themeable with CSS variables | Chart.js, ECharts, D3 directly |
| **React Router** | {{ver.react_router_dom}} | Routing, protected routes, 403/404 | De-facto standard; nested layouts for public vs app shells | TanStack Router |
| **TanStack Query** | {{ver.tanstack_react_query}} | Server-state caching, polling (ingestion progress), mutations | Removes hand-written loading/error state; refetch intervals for job progress | Redux Toolkit Query, SWR |
| **Framer Motion** | {{ver.framer_motion}} | Page transitions, hover lifts, animated counters | Declarative animation with reduced-motion support | CSS only, React Spring |
| **lucide-react** | {{ver.lucide_react}} | Icon set | Consistent, tree-shakeable icons | Font Awesome, Heroicons |
| **react-grid-layout** | {{ver.react_grid_layout}} | Drag and resize dashboard widgets | Purpose-built grid with persisted layouts | Gridstack, custom CSS grid |
| **html-to-image + jsPDF** | {{ver.html_to_image}} / {{ver.jspdf}} | Dashboard export to PNG and PDF in the browser | Works from the rendered DOM without a server | Server-side headless rendering |
| **FastAPI** | {{ver.fastapi}} | REST API, validation, OpenAPI docs at `/docs` | Type-driven validation (Pydantic), dependency injection for RBAC, automatic OpenAPI, async-ready | Flask, Django REST Framework, Node/Express |
| **Uvicorn** | {{ver.uvicorn}} | ASGI server | Standard FastAPI server; multi-worker in Compose | Gunicorn + uvicorn workers, Hypercorn |
| **Pydantic** | {{ver.pydantic}} | Request/response models; validation of AI structured output | Strict schemas turn malformed AI JSON into handled errors | dataclasses, marshmallow |
| **SQLAlchemy** | {{ver.sqlalchemy}} | ORM and query construction (2.0 typed style) | Portable across SQLite and PostgreSQL; unit-of-work; event hooks for immutability | Django ORM, raw SQL, Tortoise |
| **Alembic** | {{ver.alembic}} | Schema migrations for every table | Autogenerate + reviewable revisions; PostgreSQL-specific trigger migration | Flyway, Liquibase |
| **PostgreSQL** | 16 (Compose); 18.2 verified locally | System of record: metadata, versions, audit, conflicts | ACID, partial unique indexes (one live definition per key), triggers, JSON | MySQL, MongoDB |
| **SQLite** | bundled with Python | Zero-setup local development and fast tests | No server needed; same SQLAlchemy models | In-memory mocks |
| **DuckDB** | {{ver.duckdb}} | Execution engine for all metric queries over Parquet | In-process vectorised columnar analytics; read-only views; interruptible for timeouts | Querying PostgreSQL directly, Spark, ClickHouse, SQLite |
| **Polars** | {{ver.polars}} | Synthetic data generation, Parquet writing, chunk conversion | Fast, memory-efficient DataFrames and Parquet I/O | Pandas only |
| **Pandas** | {{ver.pandas}} | Excel reading (via openpyxl) | Best Excel support | Polars + fastexcel |
| **PyArrow** | {{ver.pyarrow}} | Streaming Parquet writer for database imports | Chunked writes without loading a table into memory | fastparquet |
| **Celery** | {{ver.celery}} | Background ingestion jobs | Mature task queue; separate worker scales independently | RQ, Dramatiq, FastAPI BackgroundTasks |
| **Redis** | 7 (Compose); 3.0.504 verified locally | Celery broker/result store | Simple, fast, standard broker | RabbitMQ |
| **OpenAI / Gemini (REST via httpx)** | httpx {{ver.httpx}} | Optional AI for query plans, metric generation and semantic conflict suggestions | Provider chosen by environment variable; key only on the server; JSON-mode outputs | Local open-source LLMs, a single provider |
| **PyJWT + Argon2 (argon2-cffi)** | {{ver.pyjwt}} / {{ver.argon2_cffi}} | httpOnly JWT access and rotating refresh tokens; password hashing | Argon2 is the current recommended password hash; httpOnly cookies keep tokens away from JavaScript | bcrypt, server sessions, localStorage tokens |
| **cryptography (Fernet)** | {{ver.cryptography}} | Encrypts stored database-connection passwords | Authenticated symmetric encryption, simple key handling | Storing secrets in plain text, external vault |
| **openpyxl + ReportLab** | {{ver.openpyxl}} / {{ver.reportlab}} | Excel and PDF report generation | Pure-Python, no external binaries | WeasyPrint, pandas.to_excel only |
| **Docker and Docker Compose** | Compose file v3 syntax | Reproducible multi-service stack (postgres, redis, backend, worker, frontend) with persistent volumes | One-command start; mirrors production topology | Manual installs, Kubernetes |
| **Nginx** | 1.27 (container) | Serves the SPA, reverse-proxies `/api`, keeps SSE unbuffered; TLS terminator on a VPS | Standard, tiny footprint | Caddy, Traefik |
| **Pytest (+ pytest-cov)** | {{ver.pytest}} | Back-end unit, API, security and integration tests; coverage | Fixtures, parametrisation, TestClient | unittest |
| **Vitest + Testing Library** | {{ver.vitest}} / {{ver.testing_library_react}} | Front-end component and library tests | Vite-native, fast; tests user-visible behaviour | Jest |
| **Playwright** | {{ver.playwright_test}} | End-to-end browser tests and documentation screenshots | Reliable auto-waiting, traces, multiple themes and viewports | Cypress, Selenium |
| **GitHub Actions** | n/a | CI: pytest on SQLite and PostgreSQL, Vitest, build, Playwright, Docker build | Native to GitHub; service containers for PostgreSQL | GitLab CI, Jenkins |
| **Mermaid** | {{ver.mermaid}} (docs tooling) | Diagrams in the reports, rendered to PNG/SVG | Diagrams-as-code that live next to the text | draw.io, Graphviz |
