from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings as env
from ..db import get_db
from ..deps import current_user, paginate, require
from ..models import ApiUsage, AuditLog, Dataset, Metric, User, Workspace
from ..permissions import matrix
from ..services.ai import ai_status
from ..services.audit import audit

router = APIRouter(tags=["workspaces"])

DEFAULT_SETTINGS = {"ai_provider": None, "default_theme": "system", "data_retention_days": 365, "require_review_for_publish": True}


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class SettingsIn(BaseModel):
    ai_provider: str | None = Field(default=None, pattern="^(openai|gemini|none)$")
    default_theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    data_retention_days: int | None = Field(default=None, ge=7, le=3650)


def ws_out(ws: Workspace, db: Session) -> dict:
    return {
        "id": ws.id, "name": ws.name, "slug": ws.slug, "is_demo": ws.is_demo, "created_at": ws.created_at.isoformat(),
        "settings": {**DEFAULT_SETTINGS, **(ws.settings or {})},
        "stats": {
            "users": db.scalar(select(func.count()).select_from(User).where(User.workspace_id == ws.id)),
            "datasets": db.scalar(select(func.count()).select_from(Dataset).where(Dataset.workspace_id == ws.id)),
            "metrics": db.scalar(select(func.count()).select_from(Metric).where(Metric.workspace_id == ws.id)),
        },
    }


@router.get("/workspaces/current")
def get_workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ws_out(user.workspace, db)


@router.patch("/workspaces/current")
def rename_workspace(body: WorkspaceIn, request: Request, user: User = Depends(require("workspace.manage")), db: Session = Depends(get_db)):
    user.workspace.name = body.name.strip()
    audit(db, user, "workspace.rename", "workspace", user.workspace_id, {"name": body.name}, request)
    db.commit()
    return ws_out(user.workspace, db)


@router.get("/workspaces/current/settings")
def get_settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = user.workspace
    return {"settings": {**DEFAULT_SETTINGS, **(ws.settings or {})}, "ai": ai_status(ws), "env": {"env": env.ENV, "query_timeout_s": env.QUERY_TIMEOUT_SECONDS, "query_row_limit": env.QUERY_ROW_LIMIT, "max_upload_mb": env.MAX_UPLOAD_MB, "celery": env.USE_CELERY}}


@router.put("/workspaces/current/settings")
def put_settings(body: SettingsIn, request: Request, user: User = Depends(require("workspace.manage")), db: Session = Depends(get_db)):
    ws = user.workspace
    cur = dict(ws.settings or {})
    cur.update({k: v for k, v in body.model_dump(exclude_unset=True).items()})
    if cur.get("ai_provider") == "none":
        cur["ai_provider"] = "none"
    ws.settings = cur
    audit(db, user, "workspace.settings", "workspace", ws.id, body.model_dump(exclude_unset=True), request)
    db.commit()
    return {"settings": {**DEFAULT_SETTINGS, **cur}, "ai": ai_status(ws)}


@router.get("/permissions/matrix")
def permissions_matrix(user: User = Depends(current_user)):
    return {"matrix": matrix()}


@router.get("/admin/audit-logs")
def audit_logs(
    page: int = 1, page_size: int = 50, action: str | None = None, entity_type: str | None = None, entity_id: str | None = None,
    q: str | None = None, user: User = Depends(require("audit.view")), db: Session = Depends(get_db),
):
    page, page_size, off = paginate(page, page_size)
    stmt = select(AuditLog).where(AuditLog.workspace_id == user.workspace_id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if q:
        stmt = stmt.where(AuditLog.action.ilike(f"%{q}%") | AuditLog.user_email.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset(off).limit(page_size)).all()
    return {
        "items": [
            {"id": r.id, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "user_email": r.user_email,
             "details": r.details, "ip": r.ip, "request_id": r.request_id, "created_at": r.created_at.isoformat()}
            for r in rows
        ],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/admin/api-usage")
def api_usage(user: User = Depends(require("workspace.manage")), db: Session = Depends(get_db)):
    base = ApiUsage.workspace_id == user.workspace_id
    total = db.scalar(select(func.count()).select_from(ApiUsage).where(base)) or 0
    ok = db.scalar(select(func.count()).select_from(ApiUsage).where(base, ApiUsage.ok.is_(True))) or 0
    tokens = db.scalar(select(func.coalesce(func.sum(ApiUsage.tokens_est), 0)).where(base)) or 0
    lat = db.scalar(select(func.avg(ApiUsage.latency_ms)).where(base))
    by_kind = db.execute(select(ApiUsage.kind, func.count()).where(base).group_by(ApiUsage.kind)).all()
    recent = db.scalars(select(ApiUsage).where(base).order_by(ApiUsage.created_at.desc()).limit(20)).all()
    return {
        "total_calls": total, "success": ok, "failed": total - ok, "est_input_tokens": int(tokens),
        "avg_latency_ms": round(lat, 1) if lat else None, "by_kind": [{"kind": k, "calls": c} for k, c in by_kind],
        "recent": [{"kind": r.kind, "provider": r.provider, "ok": r.ok, "latency_ms": r.latency_ms, "at": r.created_at.isoformat()} for r in recent],
        "provider": ai_status(user.workspace),
    }
