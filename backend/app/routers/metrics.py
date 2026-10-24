from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, paginate, require
from ..errors import BadRequest, Conflict, NotFound
from ..models import Dashboard, Metric, MetricReview, MetricVersion, User
from ..services import metrics as svc
from ..services.audit import audit
from ..services.diffing import diff_snapshots, token_diff
from ..services.engine import TIME_WINDOWS, live_definition

router = APIRouter(tags=["metrics"])


class MetricIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None
    business_definition: str | None = None
    formula: str = Field(min_length=3, max_length=2000)
    filters: str | None = Field(default=None, max_length=1000)
    aggregation: str | None = None
    unit: str | None = Field(default=None, max_length=40)
    time_window: str = "all_time"
    date_column: str | None = None
    dataset_id: str
    department: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=80)
    owner_id: str | None = None
    reason: str | None = None


class MetricPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    business_definition: str | None = None
    formula: str | None = Field(default=None, min_length=3, max_length=2000)
    filters: str | None = None
    aggregation: str | None = None
    unit: str | None = None
    time_window: str | None = None
    date_column: str | None = None
    dataset_id: str | None = None
    department: str | None = None
    category: str | None = None
    reason: str | None = None


class ActionIn(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)
    replace: bool = False


class RollbackIn(BaseModel):
    to_version: int
    reason: str = Field(min_length=3, max_length=500)


def m_out(m: Metric, db: Session | None = None, detail: bool = False) -> dict:
    o = {
        "id": m.id, "key": m.key, "name": m.name, "description": m.description, "business_definition": m.business_definition,
        "formula": m.formula, "filters": m.filters, "aggregation": m.aggregation, "unit": m.unit, "time_window": m.time_window,
        "date_column": m.date_column, "dataset_id": m.dataset_id, "dataset_name": m.dataset.name if m.dataset else None,
        "department": m.department, "category": m.category, "owner_id": m.owner_id, "owner_name": m.owner.name if m.owner else None,
        "status": m.status, "version": m.version, "published_version": m.published_version, "is_live": m.is_live,
        "depends_on": m.depends_on or [], "source": m.source, "created_at": m.created_at.isoformat(), "updated_at": m.updated_at.isoformat(),
        "has_unpublished_changes": bool(m.is_live and m.published_version and m.version != m.published_version),
    }
    return o


def _get(db: Session, user: User, mid: str) -> Metric:
    m = db.get(Metric, mid)
    if not m or m.workspace_id != user.workspace_id:
        raise NotFound("Metric")
    return m


@router.get("/metrics")
def list_metrics(
    q: str | None = None, status: str | None = None, department: str | None = None, category: str | None = None, dataset_id: str | None = None,
    live_only: bool = False, sort: str = "-updated_at", page: int = 1, page_size: int = 24,
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    page, page_size, off = paginate(page, page_size)
    stmt = select(Metric).where(Metric.workspace_id == user.workspace_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Metric.name.ilike(like), Metric.description.ilike(like), Metric.key.ilike(like), Metric.formula.ilike(like)))
    if status:
        stmt = stmt.where(Metric.status.in_(status.split(",")))
    if department:
        stmt = stmt.where(Metric.department == department)
    if category:
        stmt = stmt.where(Metric.category == category)
    if dataset_id:
        stmt = stmt.where(Metric.dataset_id == dataset_id)
    if live_only:
        stmt = stmt.where(Metric.is_live.is_(True))
    col = {"name": Metric.name, "updated_at": Metric.updated_at, "created_at": Metric.created_at, "status": Metric.status, "department": Metric.department}.get(sort.lstrip("-"), Metric.updated_at)
    stmt = stmt.order_by(col.desc() if sort.startswith("-") else col.asc())
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset(off).limit(page_size)).all()
    return {"items": [m_out(m) for m in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/metrics/facets")
def facets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = user.workspace_id
    dept = db.execute(select(Metric.department, func.count()).where(Metric.workspace_id == ws).group_by(Metric.department)).all()
    cat = db.execute(select(Metric.category, func.count()).where(Metric.workspace_id == ws).group_by(Metric.category)).all()
    st = db.execute(select(Metric.status, func.count()).where(Metric.workspace_id == ws).group_by(Metric.status)).all()
    return {
        "departments": [{"value": d, "count": c} for d, c in dept if d],
        "categories": [{"value": d, "count": c} for d, c in cat if d],
        "statuses": [{"value": d, "count": c} for d, c in st],
        "time_windows": TIME_WINDOWS,
    }


@router.get("/metrics/graph")
def graph(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ms = db.scalars(select(Metric).where(Metric.workspace_id == user.workspace_id, Metric.status != "deprecated")).all()
    by_name = {m.name.lower(): m for m in ms if m.is_live} | {m.key: m for m in ms if m.is_live}
    nodes = [{"id": m.id, "key": m.key, "name": m.name, "status": m.status, "department": m.department} for m in ms]
    edges = []
    for m in ms:
        for d in m.depends_on or []:
            t = by_name.get(d.lower()) or by_name.get(svc.slugify(d))
            if t:
                edges.append({"from": m.id, "to": t.id, "label": d})
    return {"nodes": nodes, "edges": edges}


@router.post("/metrics", status_code=201)
def create(body: MetricIn, request: Request, user: User = Depends(require("metric.write")), db: Session = Depends(get_db)):
    m = svc.create_metric(db, user, body.model_dump(), request=request)
    db.commit()
    return m_out(m)


@router.get("/metrics/{mid}")
def detail(mid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _get(db, user, mid)
    deps = svc.dependents_of(db, m.workspace_id, m.key, m.name)
    uses = []
    for key in m.depends_on or []:
        t = db.scalar(select(Metric).where(Metric.workspace_id == m.workspace_id, Metric.is_live.is_(True), or_(Metric.key == svc.slugify(key), func.lower(Metric.name) == key.lower())))
        if t:
            uses.append({"id": t.id, "name": t.name, "key": t.key})
    dash = [{"id": d.id, "name": d.name} for d in db.scalars(select(Dashboard).where(Dashboard.workspace_id == m.workspace_id)).all() if any(w.get("metric_key") == m.key for w in (d.widgets or []))]
    reviews = db.scalars(select(MetricReview).where(MetricReview.metric_id == m.id).order_by(MetricReview.created_at.desc()).limit(30)).all()
    names = {u.id: u.name for u in db.scalars(select(User).where(User.workspace_id == m.workspace_id)).all()}
    siblings = db.scalars(select(Metric).where(Metric.workspace_id == m.workspace_id, Metric.key == m.key, Metric.id != m.id)).all()
    return {
        **m_out(m),
        "depends_on_metrics": uses,
        "dependents": [{"id": x.id, "name": x.name, "key": x.key, "status": x.status} for x in deps],
        "dashboards": dash,
        "reviews": [{"id": r.id, "decision": r.decision, "comment": r.comment, "version": r.version, "user": names.get(r.user_id), "at": r.created_at.isoformat()} for r in reviews],
        "same_key": [{"id": s.id, "name": s.name, "department": s.department, "status": s.status, "is_live": s.is_live} for s in siblings],
    }


@router.patch("/metrics/{mid}")
def update(mid: str, body: MetricPatch, request: Request, user: User = Depends(require("metric.write")), db: Session = Depends(get_db)):
    m = _get(db, user, mid)
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason", None)
    if "dataset_id" in data:
        from ..models import Dataset

        ds = db.get(Dataset, data["dataset_id"])
        if not ds or ds.workspace_id != user.workspace_id:
            raise BadRequest("Unknown dataset")
    svc.update_metric(db, user, m, data, reason, request)
    db.commit()
    return m_out(m)


@router.delete("/metrics/{mid}")
def delete(mid: str, request: Request, user: User = Depends(require("metric.write")), db: Session = Depends(get_db)):
    m = _get(db, user, mid)
    if m.status != "draft" or m.published_version:
        raise Conflict("Only never-published draft metrics can be deleted; deprecate others instead")
    if svc.dependents_of(db, m.workspace_id, m.key, m.name):
        raise Conflict("Other metrics depend on this metric")
    # versions are immutable and kept for audit: soft-delete by deprecation
    m.status, m.is_live = "deprecated", False
    audit(db, user, "metric.delete", "metric", m.id, {"name": m.name}, request)
    db.commit()
    return {"ok": True}


def _action(name: str, cap: str):
    def endpoint(mid: str, body: ActionIn, request: Request, user: User = Depends(require(cap)), db: Session = Depends(get_db)):
        m = _get(db, user, mid)
        svc.transition(db, user, m, name, body.comment, body.replace, request)
        db.commit()
        return m_out(m)

    endpoint.__name__ = f"metric_{name}"
    return endpoint


for _n, _c in (("submit", "metric.write"), ("approve", "metric.review"), ("reject", "metric.review"), ("publish", "metric.review"), ("deprecate", "metric.review")):
    router.add_api_route(f"/metrics/{{mid}}/{_n}", _action(_n, _c), methods=["POST"])


# ----------------------------------------------------------------------------- versions
def v_out(v: MetricVersion, db: Session, names: dict) -> dict:
    return {
        "id": v.id, "metric_id": v.metric_id, "number": v.number, "snapshot": v.snapshot, "change_summary": v.change_summary,
        "reason": v.reason, "author": names.get(v.author_id), "author_id": v.author_id, "rollback_of": v.rollback_of,
        "created_at": v.created_at.isoformat(), "approvals": svc.version_approvals(db, v.metric_id, v.number),
    }


@router.get("/metrics/{mid}/versions")
def versions(mid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _get(db, user, mid)
    names = {u.id: u.name for u in db.scalars(select(User).where(User.workspace_id == user.workspace_id)).all()}
    rows = db.scalars(select(MetricVersion).where(MetricVersion.metric_id == m.id).order_by(MetricVersion.number.desc())).all()
    pubs = {r.version for r in db.scalars(select(MetricReview).where(MetricReview.metric_id == m.id, MetricReview.decision == "publish")).all()}
    return {
        "metric": m_out(m), "published_version": m.published_version,
        "items": [{**v_out(v, db, names), "was_published": v.number in pubs, "is_live": v.number == m.published_version and m.is_live} for v in rows],
    }


@router.get("/metrics/{mid}/diff")
def diff(mid: str, from_version: int, to_version: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _get(db, user, mid)
    vs = {v.number: v for v in db.scalars(select(MetricVersion).where(MetricVersion.metric_id == m.id, MetricVersion.number.in_([from_version, to_version]))).all()}
    if from_version not in vs or to_version not in vs:
        raise NotFound("Version")
    a, b = vs[from_version].snapshot, vs[to_version].snapshot
    return {
        "from": from_version, "to": to_version, "changes": diff_snapshots(a, b),
        "formula_diff": token_diff(a.get("formula"), b.get("formula")), "filters_diff": token_diff(a.get("filters"), b.get("filters")),
        "a": a, "b": b,
    }


@router.post("/metrics/{mid}/rollback")
def rollback(mid: str, body: RollbackIn, request: Request, user: User = Depends(require("metric.rollback")), db: Session = Depends(get_db)):
    m = _get(db, user, mid)
    svc.rollback(db, user, m, body.to_version, body.reason, request)
    db.commit()
    return m_out(m)


@router.get("/versions/recent")
def recent_versions(limit: int = 15, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(MetricVersion, Metric).join(Metric, Metric.id == MetricVersion.metric_id)
        .where(MetricVersion.workspace_id == user.workspace_id).order_by(MetricVersion.created_at.desc()).limit(min(limit, 100))
    ).all()
    names = {u.id: u.name for u in db.scalars(select(User).where(User.workspace_id == user.workspace_id)).all()}
    return {"items": [
        {"metric_id": m.id, "metric_name": m.name, "number": v.number, "change_summary": v.change_summary, "author": names.get(v.author_id), "created_at": v.created_at.isoformat()}
        for v, m in rows
    ]}


@router.get("/metrics/{mid}/audit")
def metric_audit(mid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Audit timeline: audit entries + workflow reviews + versions merged chronologically."""
    from ..models import AuditLog

    m = _get(db, user, mid)
    rows = db.scalars(select(AuditLog).where(AuditLog.workspace_id == user.workspace_id, AuditLog.entity_type == "metric", AuditLog.entity_id == m.id).order_by(AuditLog.created_at.desc()).limit(200)).all()
    return {"items": [{"id": r.id, "action": r.action, "user_email": r.user_email, "details": r.details, "created_at": r.created_at.isoformat()} for r in rows]}
