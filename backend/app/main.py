import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .db import Base, SessionLocal, engine
from .errors import install_error_handlers
from .logging_setup import install_request_context, setup_logging
from .routers import ai, auth, chat, conflicts, dashboards, datasets, evaluation, lab, metrics, notifications, overview, reports, users, workspaces

setup_logging()
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    if settings.DATABASE_URL.startswith("sqlite"):
        # single-process dev/test convenience: create tables directly. Postgres uses Alembic (`alembic upgrade head`).
        Base.metadata.create_all(engine)
    if settings.AUTO_SEED:
        from .seed import seed_if_empty

        seed_if_empty()
    log.info("IntelliMetrics API started env=%s db=%s celery=%s", settings.ENV, engine.dialect.name, settings.USE_CELERY)
    yield


app = FastAPI(
    title="IntelliMetrics AI API",
    version="1.0.0",
    description="Governed semantic layer, safe formula execution, conflict detection and TARA, the AI assistant.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With", "X-Request-ID", "Authorization"],
    expose_headers=["X-Request-ID", "Content-Disposition", "X-Row-Count"],
)
install_request_context(app)
install_error_handlers(app)

api = APIRouter(prefix="/api")
for r in (
    auth.router, workspaces.router, users.router, datasets.router, metrics.router, ai.router, conflicts.router,
    lab.validation_router, lab.execution_router, chat.router, dashboards.router, evaluation.router, reports.router,
    notifications.router, overview.router,
):
    api.include_router(r)
app.include_router(api)


@app.get("/health", tags=["health"])
@app.get("/api/health", tags=["health"], include_in_schema=False)
def health():
    db_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "up" if db_ok else "down", "env": settings.ENV, "version": app.version}
