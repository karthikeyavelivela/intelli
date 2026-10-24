# Requirements and dependency versions

Exact versions used to develop and test IntelliMetrics AI. Install commands are at the end.

## System requirements

| Item | Version used | Needed for |
|---|---|---|
| Python | 3.11 | Back end (3.11 is the tested version) |
| Node.js | 22 or newer (23.5 used) | Front end build and tests |
| npm | 10 or newer (11.10 used) | Front end packages |
| Browser | Chrome or Edge, current | Using the application (Playwright downloads its own Chromium for tests) |
| Disk space | about 3 GB | Packages, browser for tests, demo data |
| Docker Desktop | optional; not run during development | Compose route |
| PostgreSQL / Redis | optional (18.2 and 3.0 used for verification) | Production-style topology |

No paid service, account or API key is needed. An OpenAI or Gemini key is optional (TARA runs offline without one).

## Back end: `backend/requirements.txt`

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.115.6 | REST API |
| uvicorn[standard] | 0.34.0 | ASGI server |
| sqlalchemy | 2.0.36 | ORM |
| alembic | 1.14.0 | Database migrations |
| pydantic / pydantic-settings | 2.10.4 / 2.7.0 | Validation and configuration |
| email-validator | 2.2.0 | E-mail validation |
| argon2-cffi | 23.1.0 | Password hashing |
| pyjwt | 2.10.1 | Login tokens |
| python-multipart | 0.0.20 | File uploads |
| duckdb | 1.1.3 | Analytical query engine |
| polars / pandas / numpy / pyarrow | 1.18.0 / 2.2.3 / 2.2.1 / 18.1.0 | Data generation, ingestion, Parquet |
| openpyxl | 3.1.5 | Excel read and write |
| celery / redis | 5.4.0 / 5.2.1 | Background jobs |
| psycopg[binary] | 3.2.3 | PostgreSQL driver |
| pymysql | 1.1.1 | MySQL import connections |
| cryptography | 44.0.0 | Encryption of stored connection passwords |
| httpx | 0.28.1 | Optional AI provider calls |
| reportlab | 4.2.5 | PDF reports |

Development and testing (`backend/requirements-dev.txt`): pytest 8.3.4, pytest-cov 7.1.0.

## Front end: `frontend/package.json` (exact resolution in `package-lock.json`)

Runtime: react and react-dom 18.3, react-router-dom 6.28, @tanstack/react-query 5.62, recharts 2.15, framer-motion 11.15, react-grid-layout 1.5, lucide-react 0.468, @radix-ui (dialog, dropdown-menu, tabs, tooltip), tailwind-merge 2.5, class-variance-authority 0.7, clsx 2.1, html-to-image 1.11, jspdf 2.5, fontsource Inter and Instrument Serif.

Development: typescript 5.7, vite 6.0, @vitejs/plugin-react 4.3, tailwindcss 3.4, postcss 8.4, autoprefixer 10.4, vitest 2.1 with @vitest/coverage-v8, jsdom 25, Testing Library (react 16.1, jest-dom 6.6, user-event 14.5), @playwright/test 1.49.

## Documentation tooling (only to rebuild the reports): `docs/tools`

Python (`docs/tools/requirements.txt`): pypandoc_binary 1.17, python-docx 1.2.0, python-pptx 1.0.2, matplotlib 3.11.2, pillow 13.0.0, pymupdf 2.0 (optional). Node (`docs/tools/package.json`): mermaid 10.9.3. PDF output uses the Chromium installed by Playwright.

## Install commands

```bash
# back end
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed                # creates the database and the demonstration data

# front end
cd ../frontend
npm ci                            # uses package-lock.json for exact versions
npx playwright install chromium   # only needed for end-to-end tests

# report tooling (optional)
pip install -r docs/tools/requirements.txt
cd docs/tools && npm install
```
