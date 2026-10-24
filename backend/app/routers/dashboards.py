from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require
from ..errors import BadRequest, Conflict, NotFound
from ..models import Dashboard, Dataset, Metric, MetricVersion, User
from ..services.audit import audit
from ..services.dashboards import TEMPLATES, WIDGET_TYPES, dashboard_data, layout_widgets, widget_data
from ..services.metric_query import MetricUnavailable, find_metric

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


class DashIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    widgets: list[dict] = Field(default_factory=list, max_length=40)
    filters: dict = Field(default_factory=dict)
    version_policy: str = Field(default="latest_published", pattern="^(latest_published|pinned)$")


class DashPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    widgets: list[dict] | None = Field(default=None, max_length=40)
    filters: dict | None = None
    version_policy: str | None = Field(default=None, pattern="^(latest_published|pinned)$")


class FromTemplate(BaseModel):
    template: str
    name: str | None = None


class PreviewIn(BaseModel):
    widget: dict
    filters: dict = Field(default_factory=dict)
    version_policy: str = "latest_published"


class DataIn(BaseModel):
    filters: dict = Field(default_factory=dict)


def d_out(d: Dashboard) -> dict:
    return {"id": d.id, "name": d.name, "description": d.description, "widgets": d.widgets or [], "filters": d.filters or {}, "version_policy": d.version_policy,
            "template": d.template, "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat()}


def _get(db: Session, user: User, did: str) -> Dashboard:
    d = db.get(Dashboard, did)
    if not d or d.workspace_id != user.workspace_id:
        raise NotFound("Dashboard")
    return d


def _clean_widgets(db: Session, user: User, widgets: list[dict], policy: str) -> list[dict]:
    out = []
    for w in layout_widgets(widgets):
        if w.get("type") not in WIDGET_TYPES:
            raise BadRequest(f"Widget type must be one of {', '.join(WIDGET_TYPES)}")
        try:
            m = find_metric(db, user.workspace_id, w.get("metric_key", ""))
        except MetricUnavailable as e:
            raise BadRequest(str(e))
        pv = w.get("pinned_version")
        if policy == "pinned":
            if not pv:
                w["pinned_version"] = pv = m.published_version or m.version
            if not db.scalar(select(MetricVersion).where(MetricVersion.metric_id == m.id, MetricVersion.number == pv)):
                raise BadRequest(f"Metric '{m.name}' has no version {pv}")
        w = {k: w.get(k) for k in ("id", "type", "title", "metric_key", "dimension", "grain", "limit", "pinned_version", "x", "y", "w", "h") if w.get(k) is not None}
        w["title"] = w.get("title") or m.name
        out.append(w)
    return out


@router.get("")
def list_dashboards(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Dashboard).where(Dashboard.workspace_id == user.workspace_id).order_by(Dashboard.updated_at.desc())).all()
    return {"items": [{**d_out(d), "widget_count": len(d.widgets or [])} for d in rows]}


@router.get("/templates")
def templates(user: User = Depends(current_user)):
    return {"items": [{"id": k, "name": v["name"], "description": v["description"], "widget_count": len(v["widgets"]), "widgets": layout_widgets(v["widgets"])} for k, v in TEMPLATES.items()]}


@router.post("", status_code=201)
def create(body: DashIn, request: Request, user: User = Depends(require("dashboard.write")), db: Session = Depends(get_db)):
    d = Dashboard(workspace_id=user.workspace_id, name=body.name.strip(), description=body.description, filters=body.filters, version_policy=body.version_policy, created_by=user.id)
    d.widgets = _clean_widgets(db, user, body.widgets, body.version_policy)
    db.add(d)
    db.flush()
    audit(db, user, "dashboard.create", "dashboard", d.id, {"name": d.name}, request)
    db.commit()
    return d_out(d)


@router.post("/from-template", status_code=201)
def from_template(body: FromTemplate, request: Request, user: User = Depends(require("dashboard.write")), db: Session = Depends(get_db)):
    t = TEMPLATES.get(body.template)
    if not t:
        raise NotFound("Template")
    usable, skipped = [], []
    for w in t["widgets"]:
        try:
            find_metric(db, user.workspace_id, w["metric_key"])
            usable.append(w)
        except MetricUnavailable:
            skipped.append(w["metric_key"])
    if not usable:
        raise Conflict("None of this template's metrics exist in your workspace yet. Publish metrics first.", {"missing": sorted(set(skipped))})
    d = Dashboard(workspace_id=user.workspace_id, name=(body.name or t["name"]).strip(), description=t["description"], template=body.template, filters={"range": "last_12_months"}, created_by=user.id)
    d.widgets = _clean_widgets(db, user, usable, "latest_published")
    db.add(d)
    db.flush()
    audit(db, user, "dashboard.create", "dashboard", d.id, {"name": d.name, "template": body.template}, request)
    db.commit()
    return {**d_out(d), "skipped_metrics": sorted(set(skipped))}


@router.post("/widget-data")
def preview_widget(body: PreviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    res = widget_data(db, user.workspace_id, user.id, body.widget, body.filters, body.version_policy)
    db.commit()
    return res


@router.get("/{did}")
def get(did: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return d_out(_get(db, user, did))


@router.patch("/{did}")
def update(did: str, body: DashPatch, request: Request, user: User = Depends(require("dashboard.write")), db: Session = Depends(get_db)):
    d = _get(db, user, did)
    data = body.model_dump(exclude_unset=True)
    policy = data.get("version_policy", d.version_policy)
    if "widgets" in data:
        d.widgets = _clean_widgets(db, user, data["widgets"], policy)
    for k in ("name", "description", "filters", "version_policy"):
        if k in data and data[k] is not None:
            setattr(d, k, data[k])
    if "version_policy" in data and "widgets" not in data:
        d.widgets = _clean_widgets(db, user, d.widgets or [], policy)
    audit(db, user, "dashboard.update", "dashboard", d.id, {"name": d.name, "fields": list(data)}, request)
    db.commit()
    return d_out(d)


@router.delete("/{did}")
def delete(did: str, request: Request, user: User = Depends(require("dashboard.write")), db: Session = Depends(get_db)):
    d = _get(db, user, did)
    audit(db, user, "dashboard.delete", "dashboard", d.id, {"name": d.name}, request)
    db.delete(d)
    db.commit()
    return {"ok": True}


@router.post("/{did}/data")
def data(did: str, body: DataIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, did)
    out = dashboard_data(db, d, user.id, body.filters)
    db.commit()
    return out
