# Deployment reference

Short reference for running IntelliMetrics AI (a university project with synthetic Indian demonstration data). The full guide, with diagrams, the complete environment-variable table and troubleshooting, is [docs/06_Deployment_Guide.md](docs/06_Deployment_Guide.md) (Word and PDF in [docs/exports](docs/exports)).

## What was verified and what was not

| Path | Status |
|---|---|
| Local run without Docker (SQLite, in-process worker) | **Run and tested** by all automated suites |
| PostgreSQL 18.2 as application database (Alembic migrations, full back-end test suite) | **Verified** |
| Redis + a real Celery worker processing an upload | **Verified** (worker pool `solo` on Windows) |
| PostgreSQL 18.2 and MySQL 8.0.40 as import sources | **Verified** against isolated local servers |
| `vite build` of the front end | **Run** |
| Docker images and `docker compose up` | **Written, not run** (Docker is not installed on the development machine) |
| VPS with Nginx and Let's Encrypt; free cloud hosting | **Documented only**; nothing was deployed |
| GitHub Actions workflow | **Written, not executed** |

## 1. Local, no Docker

```bash
cd backend && python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed                      # creates the database and the 62,000-row Indian demonstration data
uvicorn app.main:app --reload --port 8000
cd ../frontend && npm install && npm run dev                     # http://localhost:5173
```

Production-style locally: set `DATABASE_URL=postgresql://...`, `REDIS_URL=redis://...`, `USE_CELERY=true`, run `alembic upgrade head`, `python -m app.seed`, start `uvicorn`, and start a worker with `celery -A app.worker.celery_app worker --pool=solo` (`--pool=solo` on Windows).

## 2. Docker Compose (not run)

```bash
cp .env.example .env        # set SECRET_KEY (>= 32 random characters) and POSTGRES_PASSWORD
docker compose up --build -d
docker compose logs -f backend
curl -fsS localhost:8000/health
```

Application <http://localhost:3000>, API docs <http://localhost:8000/docs>. Services: PostgreSQL 16, Redis 7, API (runs `alembic upgrade head`, then seeds when `AUTO_SEED=true` and the database is empty), Celery worker, Nginx front end. Volumes: `pgdata`, `redisdata`, `datasets` (shared by API and worker). Reset the demonstration with `./scripts/reset-demo.sh` or `scripts\reset-demo.ps1` (destructive). Note that the verification used PostgreSQL 18.2, whereas Compose pins PostgreSQL 16.

## 3. Small VPS with HTTPS (documented only)

1. Ubuntu 22.04+, install Docker, allow only SSH, 80 and 443 in the firewall, point an A record at the server.
2. In `.env` set `ENV=production`, strong `SECRET_KEY`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `COOKIE_SECURE=true`, `FRONTEND_URL`, `CORS_ORIGINS` and, for real data, `AUTO_SEED=false`.
3. Publish the front end only on loopback (`127.0.0.1:3000:80`) and no back-end port, via `docker-compose.override.yml`.
4. `docker compose up --build -d`.
5. Install host Nginx and Certbot; proxy `/` to `127.0.0.1:3000` with `proxy_buffering off`, `proxy_read_timeout 300s` and `client_max_body_size 600m`; run `certbot --nginx -d app.example.com --redirect`.
6. Update with `git pull && docker compose up --build -d` (migrations run on start).

## 4. Free cloud hosting (documented only)

Static front end on Vercel or Netlify (`npm ci && npm run build`, publish `frontend/dist`, rewrite `/api/*` to the API and `/*` to `/index.html`); API as a Docker web service on Render or Railway using `docker/backend.Dockerfile` with `USE_CELERY=false` and a managed PostgreSQL `DATABASE_URL`. Free hosting sleeps when idle and has limited storage; the API and any worker must share the dataset directory, which is why ingestion runs inside the API process on these platforms. Set `COOKIE_SECURE=true`, and `COOKIE_SAMESITE=none` if front end and API are on different sites.

## 5. Key environment variables

| Variable | Meaning |
|---|---|
| `ENV` | `development`, `production` or `test` (only `development` returns reset links in responses) |
| `DATABASE_URL`, `REDIS_URL`, `USE_CELERY` | Database, Celery broker, and whether to use Celery (default: SQLite and an in-process thread) |
| `SECRET_KEY`, `ENCRYPTION_KEY` | Token signing key (change the default); Fernet key for stored connection passwords |
| `COOKIE_SECURE`, `COOKIE_SAMESITE`, `CORS_ORIGINS`, `FRONTEND_URL` | Cookie and origin settings |
| `AI_PROVIDER` + `OPENAI_API_KEY` / `GEMINI_API_KEY` | `none` (offline TARA), `openai` or `gemini`; keys stay on the server |
| `AUTO_SEED` | Seed the demonstration data when the database is empty |
| `DATA_DIR`, `MAX_UPLOAD_MB`, `QUERY_TIMEOUT_SECONDS`, `QUERY_ROW_LIMIT` | Storage and safety limits |

The complete table is in the Deployment Guide.

## 6. Migrations, backups, logs

`alembic upgrade head` (also run at back-end start), `alembic current`. `0001` creates all tables including the partial unique index (one live definition per metric); `0002` installs the immutability trigger on `metric_versions`. Back up PostgreSQL with `pg_dump -Fc` and copy the `datasets` volume (not exercised in this project). Logs are structured JSON with a `request_id` that also appears in error responses and the audit log.

## 7. Security checklist (public demonstration)

* Unique `SECRET_KEY` (>= 32 characters), `ENCRYPTION_KEY` set and backed up, `COOKIE_SECURE=true`, HTTPS only.
* PostgreSQL and Redis not reachable from the internet; `CORS_ORIGINS` lists only real origins.
* The demo passwords are published in the documentation: never put real data into an installation that still has the demo accounts.
* The built-in rate limiter is per process; add Nginx `limit_req` on `/api/auth/` if several API workers run.
* AI keys only in the back-end environment.

## 8. Common problems

| Symptom | Fix |
|---|---|
| Login works, next request returns 401 | Use HTTPS with `COOKIE_SECURE=true`, or proxy `/api` through the same origin |
| Dataset stays *pending* | Start a worker and check `REDIS_URL`, or set `USE_CELERY=false` |
| Dataset fails with "file not found" | API and worker must share `DATA_DIR` |
| `database is locked` while re-seeding (Windows, SQLite) | Stop the API first |
| TARA says "offline deterministic mode" | Expected without an AI key |
| Streamed answers appear all at once | `proxy_buffering off` in the reverse proxy |
