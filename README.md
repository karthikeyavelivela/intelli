# IntelliMetrics AI

**A governed semantic layer with TARA, an AI assistant for trusted business metrics.**

> **University project.** IntelliMetrics AI is an academic capstone by **Devi Priya, Priyanka, Akshay and Bhaskar**, KL University, academic year 2026-27. It is not a commercial product. All business data in the demonstration is **synthetic**.

Companies often use one word for several calculations: Sales counts goods sold excluding GST, Finance subtracts refunds, Marketing quotes the invoice including GST, and all three call it *Revenue*. IntelliMetrics AI keeps **one governed definition per metric**, detects conflicting definitions automatically, stores every change as an immutable version, and lets anyone ask questions in plain English. TARA, the assistant, **never produces a number itself**: it builds a plan that is checked against approved metrics and executed by a restricted, parameterised formula engine on the real data.

The demonstration is set in India: a fictional retailer, **Bharat Retail Pvt Ltd**, with 62,000 synthetic sales lines in rupees (lakh/crore formatting), GST, an April–March financial year, festival seasons (Diwali and others), UPI/COD payments, DD-MMM-YYYY dates and IST times. A second fictional company, **Sagar Foods & Beverages Ltd**, demonstrates workspace isolation.

## Documentation

All reports are in [`docs/`](docs) as Markdown, with Word and PDF exports in [`docs/exports`](docs/exports).

| # | Document | Markdown | Word | PDF |
|---|---|---|---|---|
| 1 | Project Report | [md](docs/01_Project_Report.md) | [docx](docs/exports/01_Project_Report.docx) | [pdf](docs/exports/01_Project_Report.pdf) |
| 2 | Concept Note | [md](docs/02_Concept_Note.md) | [docx](docs/exports/02_Concept_Note.docx) | [pdf](docs/exports/02_Concept_Note.pdf) |
| 3 | System Architecture | [md](docs/03_System_Architecture.md) | [docx](docs/exports/03_System_Architecture.docx) | [pdf](docs/exports/03_System_Architecture.pdf) |
| 4 | Testing Report | [md](docs/04_Testing_Report.md) | [docx](docs/exports/04_Testing_Report.docx) | [pdf](docs/exports/04_Testing_Report.pdf) |
| 5 | User Guide and How To Run | [md](docs/05_User_Guide_and_How_To_Run.md) | [docx](docs/exports/05_User_Guide_and_How_To_Run.docx) | [pdf](docs/exports/05_User_Guide_and_How_To_Run.pdf) |
| 6 | Deployment Guide | [md](docs/06_Deployment_Guide.md) | [docx](docs/exports/06_Deployment_Guide.docx) | [pdf](docs/exports/06_Deployment_Guide.pdf) |
| 7 | Viva Preparation | [md](docs/07_Viva_Preparation.md) | [docx](docs/exports/07_Viva_Preparation.docx) | [pdf](docs/exports/07_Viva_Preparation.pdf) |
| 8 | Presentation Outline | [md](docs/08_Presentation_Outline.md) | [docx](docs/exports/08_Presentation_Outline.docx) | [pdf](docs/exports/08_Presentation_Outline.pdf) · [pptx](docs/exports/08_Presentation.pptx) |

Also: [`docs/diagrams`](docs/diagrams) (Mermaid sources, PNG and SVG), [`docs/screenshots`](docs/screenshots) (every page, light and dark, plus mobile), [`DEPLOYMENT.md`](DEPLOYMENT.md) (short deployment reference), [`REQUIREMENTS.md`](REQUIREMENTS.md) (system requirements and exact dependency versions).

## What it does

| Area | Summary |
|---|---|
| Semantic layer | Metric workflow draft → review → approve → publish; a database index guarantees exactly one live definition per metric |
| Datasets | Upload CSV, Excel, JSON, Parquet or import from PostgreSQL/MySQL; background processing to Parquet with column profiling |
| TARA generator | Describe a metric in English; get an editable, validated draft (never auto-published) |
| Formula Lab | Own lexer, parser and compiler to parameterised DuckDB SQL; raw SQL is never executed |
| Conflict centre | Automatic comparison of formula, aggregation, filters, unit, time window and dataset; severity, diff, assign → review → approve → resolve |
| Version control | Immutable versions (ORM guard plus database trigger); rollback creates a new version |
| Ask TARA | Natural-language questions answered from approved metrics, with the definition, date range and filters shown; refuses when it cannot answer |
| Dashboards and reports | KPI, line, bar, pie and table widgets; Sales, Finance and Operations templates; CSV, Excel and PDF exports in INR and IST |
| Evaluation | Measures processing time, query latency, validation pass rate, conflict-detection precision and recall |
| Security | Four roles, workspace isolation, Argon2 passwords, httpOnly tokens, CSRF header, rate limiting, audit log |

## How to run (step by step)

Two ways to run it. **Option A needs no Docker and is the tested one. Start there.**

### Before you start

Install these once:

| Tool | Version | Check with |
|---|---|---|
| Python | 3.11 | `python --version` |
| Node.js (includes npm) | 22 or newer | `node --version` |
| Git | any | `git --version` |

Nothing else is needed: no database server, no Redis, no paid account, no AI key.

### Option A: run on your own computer (no Docker)

**Step 1. Get the code**

```bash
git clone https://github.com/karthikeyavelivela/intelli.git
cd intelli
```

**Step 2. Start the back end** (open a terminal in the project folder)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed                # creates the database and the demo data (about 3 seconds)
uvicorn app.main:app --reload --port 8000
```

Leave this terminal open. Check it works: open <http://localhost:8000/health>. You should see `"status":"ok"`. API documentation is at <http://localhost:8000/docs>.

**Step 3. Start the front end** (open a second terminal in the project folder)

```powershell
cd frontend
npm install
npm run dev
```

**Step 4. Open the application**: <http://localhost:5173>. Click a button in the *Demo accounts* box on the login page (for example **Reviewer**) and sign in. The accounts are listed below.

**Step 5. Try it** (about 5 minutes)

1. Sign in as **Reviewer**, open *Conflict detection*, click **Run conflict detection**, and open a Revenue conflict.
2. Sign in as **Business User**, open *Ask TARA*, and click a suggested question such as *Compare Diwali-season sales with the previous quarter*.
3. Sign in as **Analyst**, open *Formula Lab*, and run `[Revenue] - SUM(refund_amount)`.

To start again with fresh demo data: stop the back end (Ctrl+C), run `scripts\reset-demo.ps1` (Mac/Linux: `./scripts/reset-demo.sh`), then start it again.

### Settings and AI keys (the `.env` file)

The application works with **no settings at all**. Settings are only needed to turn on optional features. To change them:

```bash
cp .env.example .env          # Windows: copy .env.example .env
```

Then edit `.env`. The back end reads it automatically from the project folder (or from `backend/`). **Never commit `.env`**; it is already in `.gitignore`.

| What you want | Setting in `.env` |
|---|---|
| Use a real AI model (OpenAI) | `AI_PROVIDER=openai` and `OPENAI_API_KEY=your-key` |
| Use a real AI model (Gemini) | `AI_PROVIDER=gemini` and `GEMINI_API_KEY=your-key` |
| No AI key (default) | `AI_PROVIDER=none`. TARA still works in a clearly labelled *offline mode* |
| Safer login secret (do this for any shared server) | `SECRET_KEY=` a long random text of 32 or more characters |
| Use PostgreSQL instead of the built-in SQLite file | `DATABASE_URL=postgresql://user:password@localhost:5432/dbname` |
| Process uploads with Celery and Redis | `USE_CELERY=true` and `REDIS_URL=redis://localhost:6379/0` |
| Password-reset links in local use | `FRONTEND_URL=http://localhost:5173` |

AI keys stay on the server. They are never sent to the browser. After changing `.env`, stop and start the back end. To check that your key works, run `python scripts/verify_ai_key.py`: it sends one tiny request and prints PASS, or the reason it failed (wrong key, no credit on the account, no internet). To make a good `SECRET_KEY`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. The full list of settings is in [DEPLOYMENT.md](DEPLOYMENT.md).

### Option B: Docker Compose (database, Redis, worker and web server together)

Install Docker Desktop first, then:

```bash
cp .env.example .env          # edit SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

Open <http://localhost:3000>. The first start creates the database and the demo data. Stop with Ctrl+C, then `docker compose down`. This option is tested automatically on GitHub: every push builds the images, starts the whole stack and checks health, login through Nginx, an Ask TARA answer and a CSV upload processed by the Celery worker ([latest run](https://github.com/karthikeyavelivela/intelli/actions/runs/40277615858)). It was not run on the authors' own computers (Docker is not installed there). See the [Deployment Guide](docs/06_Deployment_Guide.md).

### Run the tests

```bash
cd backend  && python -m pytest tests -q                 # back end
cd frontend && npx vitest run                            # front end unit tests
cd frontend && npx playwright install chromium && npx playwright test    # browser tests
```

### If something goes wrong

| Problem | Fix |
|---|---|
| `python` or `node` not found | Install it, then open a new terminal |
| Page is blank or says "Failed to fetch" | The back end is not running. Start Step 2 again |
| `database is locked` when resetting (Windows) | Stop the back end first, then reset |
| Port 8000 or 5173 already in use | Close the other program, or use another port (`--port 8001`) |
| Photos are grey boxes | You are offline. Harmless; the app still works |
| TARA says "offline mode" | Normal without an AI key. Add one in `.env` to change it |
| Login fails for a demo account | Reset the demo data (see Step 5) |

More: [User Guide](docs/05_User_Guide_and_How_To_Run.md) (with screenshots of every page) and [Deployment Guide](docs/06_Deployment_Guide.md) (server, HTTPS and free hosting).

## Demonstration accounts

All are marked **DEMO** and the login page can fill them in for you.

| Role | Person (fictional) | Email | Password | Company |
|---|---|---|---|---|
| Admin | Aarav Menon | `admin@intellimetrics.demo` | `Admin@12345` | Bharat Retail Pvt Ltd |
| Data Analyst | Diya Reddy | `analyst@intellimetrics.demo` | `Analyst@12345` | Bharat Retail Pvt Ltd |
| Business User | Rohan Sharma | `business@intellimetrics.demo` | `Business@12345` | Bharat Retail Pvt Ltd |
| Reviewer | Meera Iyer | `reviewer@intellimetrics.demo` | `Reviewer@12345` | Bharat Retail Pvt Ltd |
| Admin (second company) | Suresh Naidu | `admin@sagarfoods.demo` | `Admin@12345` | Sagar Foods & Beverages Ltd |
| Analyst (second company) | Kavya Raju | `analyst@sagarfoods.demo` | `Analyst@12345` | Sagar Foods & Beverages Ltd |

The permission matrix is in the [System Architecture](docs/03_System_Architecture.md) document and in the application under *Users & workspace*. These passwords are public: never place real data in an installation that still has the demo accounts.

## Suggested questions for Ask TARA

* What was net revenue by month in the last quarter of this financial year?
* Which 5 states had the highest sales this year?
* Compare Diwali-season sales with the previous quarter
* What is the UPI vs COD split by region?
* Top 10 customers by revenue

The latest measured test results (counts, coverage, benchmarks) are in the [Testing Report](docs/04_Testing_Report.md).

## Limitations, stated plainly

* Docker Compose was **not run on the authors' computers** (Docker is not installed there). It is tested on GitHub's Linux runners instead; locally each service was verified separately (PostgreSQL 18.2, Redis + Celery, MySQL 8.0).
* **No live AI provider was used**; the offline planner is what was tested end to end, and the AI provider code was tested with mocked responses.
* VPS and free-cloud deployment are documented but nothing was deployed to a real server.
* No load test, no external security assessment, no user study; browser tests used Chromium only.
* Time-saving figures in the evaluation use stated assumptions for manual effort.

## Project layout

```
backend/   app/{routers,services,models.py,permissions.py,seed.py,seed_data.py,worker.py}  alembic/  tests/  requirements.txt  requirements-dev.txt
frontend/  src/{pages,components,layouts,lib,config/images.ts}  e2e/  e2e-docs/  vite.config.ts
docker/    backend.Dockerfile  frontend.Dockerfile  nginx.conf  backend-entrypoint.sh
docs/      src/ (report sources)  tools/ (build scripts)  data/ (measured results)  diagrams/  screenshots/  exports/
scripts/   reset-demo.sh  reset-demo.ps1  benchmark.py  check_no_pricing.py  verify_celery.py  verify_connections.py
docker-compose.yml  .env.example  DEPLOYMENT.md  REQUIREMENTS.md  README.md  .github/workflows/ci.yml
```

To rebuild the report pack: `backend\.venv\Scripts\python docs\tools\build_docs.py` (requires Node for Mermaid and Chromium PDF output; see `docs/tools`).

## Attributions

Photographs are hot-linked from public sources, rendered with a black-and-white treatment, and replaced by a gradient if they cannot load. Every URL is listed with a source comment in [`frontend/src/config/images.ts`](frontend/src/config/images.ts); all 37 image URLs (36 distinct photographs) returned HTTP 200 when checked on 24-Oct-2026. Photos are provided by their photographers under the [Unsplash License](https://unsplash.com/license) and the [Pexels License](https://www.pexels.com/license/); individual credit is on each photo's page.

* **Pexels** (`images.pexels.com/photos/<id>`): 11321242, 11800909, 1181676, 12310724, 12419503, 12903045, 13339844, 13369323, 13612713, 14094276, 14845309 (Mumbai skyline), 15126949, 160087, 16952108 (India Gate), 265087, 29820147, 31112232, 3183150, 31968829, 669615.
* **Unsplash** (`images.unsplash.com/<id>`): photo-1432888498266-38ffec3eaf0a, photo-1451187580459-43490279c0fa, photo-1494438639946-1ebd1d20bf85, photo-1512758017271-d7b84c2113f1, photo-1518770660439-4636190af475, photo-1526374965328-7f61d4dc18c5, photo-1526628953301-3e589a6a8b74, photo-1531297484001-80022131f5a1, photo-1535378917042-10a22c95931a, photo-1550751827-4bd374c3f58b, photo-1551288049-bebda4e38f71, photo-1553877522-43269d4ea984, photo-1554224155-6726b3ff858f, photo-1558494949-ef010cbdcc31, photo-1558591710-4b4a1ae0f04d, photo-1639322537228-f710d846310a.
* Fonts: Inter Variable and Instrument Serif via Fontsource (SIL Open Font License). Diagrams: Mermaid (MIT). Icons: lucide (ISC).
