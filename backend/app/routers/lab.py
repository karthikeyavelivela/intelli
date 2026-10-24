"""Formula Lab: /validation and /execution endpoints."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import paginate, require
from ..errors import AppError, BadRequest, NotFound
from ..models import Dataset, Execution, User
from ..services.audit import audit
from ..services.engine import QueryError, QuerySpec, QueryTimeout, dataset_schema, make_resolver, run_query, window_range
from ..services.formula import FormulaError
from ..services.metrics import validate_definition

validation_router = APIRouter(prefix="/validation", tags=["validation"])
execution_router = APIRouter(prefix="/execution", tags=["execution"])


class FormulaIn(BaseModel):
    dataset_id: str
    formula: str = Field(min_length=1, max_length=2000)
    filters: str | None = Field(default=None, max_length=1000)
    date_column: str | None = None
    time_window: str = "all_time"


class RunIn(FormulaIn):
    dimensions: list[dict] = Field(default_factory=list, max_length=3)
    time_range: dict | None = None
    where: list[dict] = Field(default_factory=list, max_length=10)
    order: str = "dim"
    limit: int = Field(default=500, ge=1, le=10000)


def _ds(db: Session, user: User, did: str) -> Dataset:
    d = db.get(Dataset, did)
    if not d or d.workspace_id != user.workspace_id:
        raise NotFound("Dataset")
    return d


@validation_router.post("/formula")
def validate_formula(body: FormulaIn, user: User = Depends(require("formula.run")), db: Session = Depends(get_db)):
    ds = _ds(db, user, body.dataset_id)
    rep = validate_definition(db, user.workspace_id, body.model_dump())
    db.add(Execution(workspace_id=user.workspace_id, user_id=user.id, dataset_id=ds.id, kind="validate", expression=body.formula, ok=rep["ok"],
                     error=None if rep["ok"] else rep["errors"][0]["message"]))
    db.commit()
    schema = dataset_schema(ds)
    return {**rep, "dataset": {"id": ds.id, "name": ds.name, "columns": [{"name": k, "category": v} for k, v in schema.items()]}}


@execution_router.post("/run")
def run(body: RunIn, request: Request, user: User = Depends(require("formula.run")), db: Session = Depends(get_db)):
    ds = _ds(db, user, body.dataset_id)
    tr = body.time_range
    if not tr:
        w = window_range(body.time_window)
        if w:
            tr = {"column": body.date_column, "start": w[0], "end": w[1]}
    spec = QuerySpec(formula=body.formula, filters=body.filters, dimensions=body.dimensions, time_range=tr, where=body.where, order=body.order, limit=body.limit)
    resolver = make_resolver(db, user.workspace_id, ds.id, mode="working")
    try:
        res = run_query(db, ds, spec, user.id, "execute", resolver)
    except FormulaError as e:
        db.commit()
        raise AppError(422, "invalid_formula", e.message, [e.to_dict()])
    except QueryTimeout as e:
        db.commit()
        raise AppError(408, "query_timeout", str(e))
    except QueryError as e:
        db.commit()
        raise AppError(400, "query_failed", str(e))
    audit(db, user, "formula.execute", "dataset", ds.id, {"formula": body.formula[:200], "rows": len(res.rows), "ms": res.duration_ms}, request)
    db.commit()
    return {
        "columns": res.columns, "rows": res.rows, "duration_ms": res.duration_ms, "scanned_rows": res.scanned_rows, "row_count": len(res.rows),
        "truncated": res.truncated, "row_limit": min(body.limit, settings.QUERY_ROW_LIMIT), "timeout_s": settings.QUERY_TIMEOUT_SECONDS,
        "sql": res.sql.replace(f" LIMIT {min(body.limit, settings.QUERY_ROW_LIMIT) + 1}", f" LIMIT {min(body.limit, settings.QUERY_ROW_LIMIT)}"),
        "params": res.params, "metrics_used": res.metrics_used, "columns_used": res.columns_used,
    }


@execution_router.get("/history")
def history(page: int = 1, page_size: int = 20, kind: str | None = None, ok: bool | None = None, user: User = Depends(require("formula.run")), db: Session = Depends(get_db)):
    page, page_size, off = paginate(page, page_size)
    stmt = select(Execution).where(Execution.workspace_id == user.workspace_id, Execution.kind.in_([kind] if kind else ["execute", "validate", "chat", "dashboard"]))
    if ok is not None:
        stmt = stmt.where(Execution.ok.is_(ok))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Execution.created_at.desc()).offset(off).limit(page_size)).all()
    return {
        "items": [{"id": r.id, "kind": r.kind, "expression": r.expression, "ok": r.ok, "duration_ms": r.duration_ms, "scanned_rows": r.scanned_rows,
                   "row_count": r.row_count, "error": r.error, "sql": r.sql_text, "dataset_id": r.dataset_id, "created_at": r.created_at.isoformat()} for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }
