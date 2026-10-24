from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, paginate, require
from ..errors import BadRequest, NotFound
from ..models import AIGeneration, Dataset, User
from ..services import metrics as svc
from ..services.ai import ai_status
from ..services.audit import audit
from ..services.tara import generate_metric
from .metrics import m_out

router = APIRouter(prefix="/ai", tags=["ai"])


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=8, max_length=1500)
    dataset_id: str


class SaveIn(BaseModel):
    definition: dict  # user-edited suggestion
    submit: bool = False


@router.get("/status")
def status(user: User = Depends(current_user)):
    return ai_status(user.workspace)


@router.post("/generate-metric")
def generate(body: GenerateIn, request: Request, user: User = Depends(require("ai.generate")), db: Session = Depends(get_db)):
    ds = db.get(Dataset, body.dataset_id)
    if not ds or ds.workspace_id != user.workspace_id:
        raise NotFound("Dataset")
    if ds.status != "ready":
        raise BadRequest("Dataset is not ready yet")
    out = generate_metric(db, user, user.workspace, body.prompt.strip(), ds)
    audit(db, user, "tara.generate", "dataset", ds.id, {"mode": out["mode"], "ok": out["ok"], "prompt": body.prompt[:200]}, request)
    db.commit()
    return out


@router.post("/generations/{gid}/save")
def save(gid: str, body: SaveIn, request: Request, user: User = Depends(require("metric.write")), db: Session = Depends(get_db)):
    """Persist a (possibly user-edited) TARA suggestion as a DRAFT, optionally submitting for approval.
    Re-validated server-side; invalid definitions can be saved as draft but never submitted."""
    g = db.get(AIGeneration, gid)
    if not g or g.workspace_id != user.workspace_id:
        raise NotFound("Generation")
    if g.metric_id:
        raise BadRequest("This suggestion was already saved")
    d = {**g.output, **body.definition, "dataset_id": body.definition.get("dataset_id") or g.dataset_id}
    m = svc.create_metric(db, user, d, source="tara", request=request)
    g.metric_id, g.status, g.accepted = m.id, "saved", True
    if body.submit:
        svc.transition(db, user, m, "submit", f"Submitted from TARA suggestion", False, request)
        g.status = "submitted"
    audit(db, user, "tara.accept", "metric", m.id, {"generation": g.id, "submitted": body.submit, "edited": body.definition != g.output}, request)
    db.commit()
    return m_out(m)


@router.post("/generations/{gid}/discard")
def discard(gid: str, user: User = Depends(require("ai.generate")), db: Session = Depends(get_db)):
    g = db.get(AIGeneration, gid)
    if not g or g.workspace_id != user.workspace_id:
        raise NotFound("Generation")
    g.status = "discarded"
    db.commit()
    return {"ok": True}


@router.get("/generations")
def generations(page: int = 1, page_size: int = 15, user: User = Depends(require("ai.generate")), db: Session = Depends(get_db)):
    page, page_size, off = paginate(page, page_size)
    stmt = select(AIGeneration).where(AIGeneration.workspace_id == user.workspace_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AIGeneration.created_at.desc()).offset(off).limit(page_size)).all()
    return {"items": [
        {"id": g.id, "prompt": g.prompt, "mode": g.mode, "provider": g.provider, "valid": g.valid, "status": g.status, "accepted": g.accepted,
         "latency_ms": g.latency_ms, "metric_id": g.metric_id, "name": (g.output or {}).get("name"), "error": g.error, "created_at": g.created_at.isoformat()}
        for g in rows], "total": total}
