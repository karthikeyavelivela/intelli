from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, paginate, require
from ..errors import BadRequest, Conflict as ConflictErr, NotFound
from ..models import AuditLog, Conflict, Metric, User
from ..services.audit import audit, notify
from ..services.conflicts import apply_resolution, detect_conflicts
from ..services.diffing import token_diff
from .metrics import m_out

router = APIRouter(prefix="/conflicts", tags=["conflicts"])
TERMINAL = ("resolved", "dismissed")
SEV_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class AssignIn(BaseModel):
    assignee_id: str
    note: str | None = None


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ResolveIn(BaseModel):
    action: str
    note: str = Field(min_length=3, max_length=1000)
    new_name: str | None = None


def c_out(c: Conflict, db: Session, names: dict | None = None, mm: dict | None = None) -> dict:
    mm = mm or {m.id: m for m in db.scalars(select(Metric).where(Metric.id.in_([c.metric_a_id, c.metric_b_id]))).all()}
    a, b = mm.get(c.metric_a_id), mm.get(c.metric_b_id)
    names = names or {}
    return {
        "id": c.id, "metric_key": c.metric_key, "conflict_type": c.conflict_type, "severity": c.severity, "status": c.status,
        "explanation": c.explanation, "recommendation": c.recommendation, "recommended_action": c.recommended_action,
        "differences": c.differences, "affected": c.affected, "assignee_id": c.assignee_id, "assignee_name": names.get(c.assignee_id),
        "resolution_action": c.resolution_action, "resolution_note": c.resolution_note,
        "detected_at": c.detected_at.isoformat(), "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        "metric_a": {"id": a.id, "name": a.name, "department": a.department, "status": a.status, "formula": a.formula, "is_live": a.is_live} if a else None,
        "metric_b": {"id": b.id, "name": b.name, "department": b.department, "status": b.status, "formula": b.formula, "is_live": b.is_live} if b else None,
        "has_tara_suggestion": any(d.get("source") == "tara" for d in (c.differences or [])),
    }


def _get(db: Session, user: User, cid: str) -> Conflict:
    c = db.get(Conflict, cid)
    if not c or c.workspace_id != user.workspace_id:
        raise NotFound("Conflict")
    return c


def _names(db: Session, user: User) -> dict:
    return {u.id: u.name for u in db.scalars(select(User).where(User.workspace_id == user.workspace_id)).all()}


@router.get("")
def list_conflicts(
    status: str | None = None, severity: str | None = None, q: str | None = None, assignee_id: str | None = None,
    page: int = 1, page_size: int = 30, user: User = Depends(require("conflict.view")), db: Session = Depends(get_db),
):
    page, page_size, off = paginate(page, page_size)
    stmt = select(Conflict).where(Conflict.workspace_id == user.workspace_id)
    if status == "active":
        stmt = stmt.where(Conflict.status.notin_(TERMINAL))
    elif status:
        stmt = stmt.where(Conflict.status == status)
    if severity:
        stmt = stmt.where(Conflict.severity == severity)
    if assignee_id:
        stmt = stmt.where(Conflict.assignee_id == (user.id if assignee_id == "me" else assignee_id))
    if q:
        stmt = stmt.where(Conflict.metric_key.ilike(f"%{q}%") | Conflict.explanation.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Conflict.detected_at.desc()).offset(off).limit(page_size)).all()
    rows = sorted(rows, key=lambda c: (c.status in TERMINAL, -SEV_ORDER[c.severity]))
    mids = {i for c in rows for i in (c.metric_a_id, c.metric_b_id)}
    mm = {m.id: m for m in db.scalars(select(Metric).where(Metric.id.in_(mids))).all()} if mids else {}
    names = _names(db, user)
    all_c = db.execute(select(Conflict.status, Conflict.severity, func.count()).where(Conflict.workspace_id == user.workspace_id).group_by(Conflict.status, Conflict.severity)).all()
    summary = {"active": 0, "resolved": 0, "by_severity": {}}
    for st, sev, n in all_c:
        if st in TERMINAL:
            summary["resolved"] += n
        else:
            summary["active"] += n
            summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + n
    return {"items": [c_out(c, db, names, mm) for c in rows], "total": total, "page": page, "page_size": page_size, "summary": summary}


@router.post("/detect")
def detect(request: Request, user: User = Depends(require("conflict.detect")), db: Session = Depends(get_db)):
    out = detect_conflicts(db, user, user.workspace, request)
    audit(db, user, "conflict.detect_run", "workspace", user.workspace_id, {k: v for k, v in out.items() if k != "tara"}, request)
    db.commit()
    return out


@router.get("/{cid}")
def detail(cid: str, user: User = Depends(require("conflict.view")), db: Session = Depends(get_db)):
    c = _get(db, user, cid)
    names = _names(db, user)
    out = c_out(c, db, names)
    a, b = out["metric_a"], out["metric_b"]
    ma, mb = db.get(Metric, c.metric_a_id), db.get(Metric, c.metric_b_id)
    out["formula_diff"] = token_diff(ma.formula, mb.formula)
    out["filters_diff"] = token_diff(ma.filters, mb.filters)
    out["a_full"], out["b_full"] = m_out(ma), m_out(mb)
    return out


@router.get("/{cid}/events")
def events(cid: str, user: User = Depends(require("conflict.view")), db: Session = Depends(get_db)):
    c = _get(db, user, cid)
    rows = db.scalars(select(AuditLog).where(AuditLog.workspace_id == user.workspace_id, AuditLog.entity_type == "conflict", AuditLog.entity_id == c.id).order_by(AuditLog.created_at)).all()
    return {"items": [{"id": r.id, "action": r.action, "user_email": r.user_email, "details": r.details, "created_at": r.created_at.isoformat()} for r in rows]}


def _step(c: Conflict, allowed: tuple, target: str, what: str):
    if c.status not in allowed:
        raise ConflictErr(f"Cannot {what}: conflict is '{c.status}' (expected {' or '.join(allowed)})")
    c.status = target


@router.post("/{cid}/assign")
def assign(cid: str, body: AssignIn, request: Request, user: User = Depends(require("conflict.manage")), db: Session = Depends(get_db)):
    c = _get(db, user, cid)
    who = db.get(User, body.assignee_id)
    if not who or who.workspace_id != user.workspace_id or not who.is_active:
        raise BadRequest("Assignee must be an active member of this workspace")
    _step(c, ("open", "assigned"), "assigned", "assign")
    c.assignee_id = who.id
    audit(db, user, "conflict.assign", "conflict", c.id, {"assignee": who.email, "note": body.note}, request)
    notify(db, c.workspace_id, f"Conflict assigned to you: {c.metric_key}", body.note, "warning", f"/app/conflicts/{c.id}", user_id=who.id)
    db.commit()
    return c_out(c, db, _names(db, user))


@router.post("/{cid}/review")
def start_review(cid: str, body: NoteIn, request: Request, user: User = Depends(require("conflict.manage")), db: Session = Depends(get_db)):
    c = _get(db, user, cid)
    _step(c, ("assigned",), "in_review", "start review")
    audit(db, user, "conflict.review", "conflict", c.id, {"note": body.note}, request)
    db.commit()
    return c_out(c, db, _names(db, user))


@router.post("/{cid}/approve")
def approve(cid: str, body: NoteIn, request: Request, user: User = Depends(require("conflict.manage")), db: Session = Depends(get_db)):
    c = _get(db, user, cid)
    _step(c, ("in_review",), "approved", "approve")
    audit(db, user, "conflict.approve", "conflict", c.id, {"note": body.note}, request)
    db.commit()
    return c_out(c, db, _names(db, user))


@router.post("/{cid}/resolve")
def resolve(cid: str, body: ResolveIn, request: Request, user: User = Depends(require("conflict.manage")), db: Session = Depends(get_db)):
    from ..models import utcnow

    c = _get(db, user, cid)
    _step(c, ("approved",), "resolved", "resolve (approve the resolution first)")
    apply_resolution(db, user, c, body.action, body.note, body.new_name, request)
    c.resolution_action, c.resolution_note, c.resolved_at = body.action, body.note, utcnow()
    audit(db, user, "conflict.resolve", "conflict", c.id, {"action": body.action, "note": body.note}, request)
    notify(db, c.workspace_id, f"Conflict resolved: {c.metric_key}", f"Resolution: {body.action}. {body.note}", "success", f"/app/conflicts/{c.id}")
    db.commit()
    return c_out(c, db, _names(db, user))


@router.post("/{cid}/dismiss")
def dismiss(cid: str, body: NoteIn, request: Request, user: User = Depends(require("conflict.manage")), db: Session = Depends(get_db)):
    from ..models import utcnow

    c = _get(db, user, cid)
    if c.status in TERMINAL:
        raise ConflictErr("Conflict is already closed")
    if not (body.note or "").strip():
        raise BadRequest("A note is required to dismiss a conflict")
    c.status, c.resolution_note, c.resolved_at = "dismissed", body.note, utcnow()
    audit(db, user, "conflict.dismiss", "conflict", c.id, {"note": body.note}, request)
    db.commit()
    return c_out(c, db, _names(db, user))


@router.post("/{cid}/reopen")
def reopen(cid: str, body: NoteIn, request: Request, user: User = Depends(require("conflict.manage")), db: Session = Depends(get_db)):
    c = _get(db, user, cid)
    if c.status not in TERMINAL:
        raise ConflictErr("Conflict is not closed")
    c.status, c.resolved_at = "open", None
    audit(db, user, "conflict.reopen", "conflict", c.id, {"note": body.note}, request)
    db.commit()
    return c_out(c, db, _names(db, user))
