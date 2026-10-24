"""Metric lifecycle: create/update/workflow/rollback with immutable versioning."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..errors import AppError, BadRequest, Conflict, Forbidden
from ..models import Dataset, Metric, MetricReview, MetricVersion, User
from .audit import audit, notify
from .diffing import TRACKED, diff_snapshots
from .engine import dataset_schema, make_resolver, metric_snapshot, slugify
from .formula import Compiler, FormulaError, extract_aggregations, extract_refs, parse_condition, parse_formula

STATUSES = ["draft", "in_review", "approved", "published", "deprecated"]
EDITABLE = {
    "name", "description", "business_definition", "formula", "filters", "aggregation", "unit", "time_window",
    "date_column", "dataset_id", "department", "category",
}


def validate_definition(db: Session, workspace_id: str, data: dict, exclude_metric_id: str | None = None) -> dict:
    """Full validation report used by Formula Lab, TARA generator and the metric form."""
    errors: list[dict] = []
    warnings: list[str] = []
    info = {"columns": [], "aggregations": [], "metrics": [], "result_type": None}
    ds = db.get(Dataset, data.get("dataset_id")) if data.get("dataset_id") else None
    if ds is None or ds.workspace_id != workspace_id:
        return {"ok": False, "errors": [{"message": "Choose a dataset for this metric", "position": 0}], "warnings": [], **info}
    if ds.status != "ready":
        errors.append({"message": f"Dataset '{ds.name}' is not ready ({ds.status})", "position": 0})
        return {"ok": False, "errors": errors, "warnings": warnings, **info}
    schema = dataset_schema(ds)
    try:
        parsed = parse_formula(data.get("formula") or "")
        extra = [parse_condition(data["filters"])] if (data.get("filters") or "").strip() else []
        resolver = make_resolver(db, workspace_id, ds.id, mode="working")
        comp = Compiler(schema, resolver)
        res = comp.compile_formula(parsed, extra)
        info = {
            "columns": sorted(res.columns),
            "aggregations": sorted(res.aggregations),
            "metrics": res.metrics,
            "result_type": res.type,
        }
        for ref in extract_refs(parsed):
            if ref not in res.metrics:
                warnings.append(f"Metric reference [{ref}] was not resolved")
        dc = data.get("date_column")
        if dc and (dc.lower() not in {c.lower() for c in schema} or schema.get(next((c for c in schema if c.lower() == dc.lower()), ""), "") != "date"):
            errors.append({"message": f"date_column '{dc}' is not a date column in {ds.name}", "position": 0})
        if data.get("time_window", "all_time") != "all_time" and not (dc or ds.date_column):
            warnings.append("A time window is set but the dataset has no date column to apply it to")
    except FormulaError as e:
        errors.append(e.to_dict())
    return {"ok": not errors, "errors": errors, "warnings": warnings, **info}


def _refs_for(formula: str, filters: str | None) -> list[str]:
    try:
        return extract_refs(parse_formula(formula))
    except FormulaError:
        return []


def _auto_aggregation(formula: str) -> str | None:
    try:
        aggs = extract_aggregations(parse_formula(formula))
    except FormulaError:
        return None
    return aggs[0].lower() if len(aggs) == 1 else ("derived" if aggs else None)


def add_version(db: Session, m: Metric, user: User | None, summary: str, reason: str | None = None, rollback_of: int | None = None) -> MetricVersion:
    v = MetricVersion(
        workspace_id=m.workspace_id, metric_id=m.id, number=m.version, snapshot=metric_snapshot(m),
        change_summary=summary[:500], reason=reason, author_id=user.id if user else None, rollback_of=rollback_of,
    )
    db.add(v)
    return v


LIMITS = {"name": 200, "key": 120, "unit": 40, "aggregation": 40, "time_window": 40, "date_column": 160, "department": 80, "category": 80}


def _check_lengths(data: dict) -> None:
    for f, n in LIMITS.items():
        v = data.get(f)
        if isinstance(v, str) and len(v) > n:
            raise BadRequest(f"'{f}' is too long (max {n} characters)")


def create_metric(db: Session, user: User, data: dict, source: str = "manual", request=None) -> Metric:
    _check_lengths(data)
    ws = user.workspace_id
    name = (data.get("name") or "").strip()
    if not name:
        raise BadRequest("Metric name is required")
    ds = db.get(Dataset, data.get("dataset_id")) if data.get("dataset_id") else None
    if data.get("dataset_id") and (ds is None or ds.workspace_id != ws):
        raise BadRequest("Unknown dataset")
    key = data.get("key") or slugify(name)
    m = Metric(
        workspace_id=ws, key=key, name=name, owner_id=data.get("owner_id") or user.id, status="draft", version=1,
        source=source,
        **{f: (data.get(f) if data.get(f) not in ("",) else None) for f in EDITABLE if f != "name"},
    )
    m.time_window = data.get("time_window") or "all_time"
    m.formula = (data.get("formula") or "").strip()
    if not m.formula:
        raise BadRequest("Formula is required")
    m.aggregation = m.aggregation or _auto_aggregation(m.formula)
    m.depends_on = _refs_for(m.formula, m.filters)
    db.add(m)
    db.flush()
    add_version(db, m, user, "Initial definition" + (" (generated by TARA)" if source == "tara" else ""), data.get("reason"))
    audit(db, user, "metric.create", "metric", m.id, {"name": m.name, "key": m.key, "source": source}, request)
    return m


def update_metric(db: Session, user: User, m: Metric, data: dict, reason: str | None, request=None) -> Metric:
    if m.status == "deprecated":
        raise Conflict("Deprecated metrics cannot be edited")
    _check_lengths(data)
    before = metric_snapshot(m)
    for f in EDITABLE:
        if f in data:
            v = data[f]
            setattr(m, f, None if v == "" else v)
    if "name" in data and data["name"] and "key" not in data:
        pass  # key is the governed identity and never changes on rename; rename via conflict resolution
    if not m.formula or not m.formula.strip():
        raise BadRequest("Formula is required")
    m.formula = m.formula.strip()
    if "aggregation" not in data:
        m.aggregation = _auto_aggregation(m.formula) or m.aggregation
    after = metric_snapshot(m)
    changes = diff_snapshots(before, after)
    if not changes:
        return m
    m.depends_on = _refs_for(m.formula, m.filters)
    m.version += 1
    if m.status in ("approved", "in_review", "published"):
        m.status = "draft"  # edits always need a fresh review; a published version stays live until a new one is published
    summary = "Changed " + ", ".join(c["field"] for c in changes)
    add_version(db, m, user, summary, reason)
    audit(db, user, "metric.update", "metric", m.id, {"changes": changes, "version": m.version}, request)
    return m


def _review(db: Session, m: Metric, user: User, decision: str, comment: str | None):
    db.add(MetricReview(workspace_id=m.workspace_id, metric_id=m.id, version=m.version, user_id=user.id, decision=decision, comment=comment))


def transition(db: Session, user: User, m: Metric, action: str, comment: str | None = None, replace: bool = False, request=None) -> Metric:
    ws = m.workspace_id
    if action == "submit":
        if m.status != "draft":
            raise Conflict(f"Only draft metrics can be submitted (status is {m.status})")
        rep = validate_definition(db, ws, metric_snapshot(m))
        if not rep["ok"]:
            raise AppError(422, "invalid_formula", "Metric formula failed validation; fix it before submitting", rep["errors"])
        m.status = "in_review"
        _review(db, m, user, "submit", comment)
        notify(db, ws, f"Metric submitted for review: {m.name}", f"{user.name} submitted '{m.name}' v{m.version}", "review", f"/app/metrics/{m.id}")
    elif action in ("approve", "reject"):
        if m.status != "in_review":
            raise Conflict("Metric is not awaiting review")
        if action == "reject" and not (comment or "").strip():
            raise BadRequest("A comment is required when rejecting")
        if action == "approve" and m.owner_id == user.id and user.role != "admin":
            raise Forbidden("You cannot approve your own metric")
        m.status = "approved" if action == "approve" else "draft"
        _review(db, m, user, action, comment)
        notify(db, ws, f"Metric {action}d: {m.name}", comment, "success" if action == "approve" else "warning", f"/app/metrics/{m.id}", user_id=m.owner_id)
    elif action == "publish":
        if m.status != "approved":
            raise Conflict("Only approved metrics can be published")
        other = db.scalar(select(Metric).where(Metric.workspace_id == ws, Metric.key == m.key, Metric.is_live.is_(True), Metric.id != m.id))
        if other:
            if not replace:
                raise Conflict(
                    f"'{other.name}' ({other.department or 'no department'}) is already the published definition for '{m.key}'. "
                    "Deprecate it, resolve the conflict, or publish with replace=true.",
                    {"existing_metric_id": other.id},
                )
            other.status, other.is_live = "deprecated", False
            db.flush()
            audit(db, user, "metric.deprecate", "metric", other.id, {"reason": f"replaced by {m.id}"}, request)
        m.status, m.published_version, m.is_live = "published", m.version, True
        _review(db, m, user, "publish", comment)
        notify(db, ws, f"Metric published: {m.name}", f"v{m.version} is now the governed definition for '{m.key}'", "success", f"/app/metrics/{m.id}")
    elif action == "deprecate":
        if m.status == "deprecated":
            raise Conflict("Already deprecated")
        m.status, m.is_live = "deprecated", False
        _review(db, m, user, "deprecate", comment)
    else:
        raise BadRequest("Unknown action")
    audit(db, user, f"metric.{action}", "metric", m.id, {"comment": comment, "version": m.version, "status": m.status}, request)
    return m


def rollback(db: Session, user: User, m: Metric, to_number: int, reason: str, request=None) -> Metric:
    target = db.scalar(select(MetricVersion).where(MetricVersion.metric_id == m.id, MetricVersion.number == to_number))
    if not target:
        raise BadRequest("Version not found")
    if m.status == "deprecated":
        raise Conflict("Deprecated metrics cannot be rolled back")
    snap = target.snapshot
    for f in EDITABLE:
        if f in snap:
            setattr(m, f, snap[f])
    m.depends_on = _refs_for(m.formula, m.filters)
    m.version += 1
    add_version(db, m, user, f"Rollback to v{to_number}", reason, rollback_of=to_number)
    was_live = m.is_live
    if was_live:
        # rollback by an approver of a live metric becomes the new live definition immediately (audited)
        m.status, m.published_version = "published", m.version
        _review(db, m, user, "publish", f"Rollback to v{to_number}: {reason}")
    else:
        m.status = "draft"
    audit(db, user, "metric.rollback", "metric", m.id, {"to": to_number, "new_version": m.version, "reason": reason}, request)
    return m


def dependents_of(db: Session, workspace_id: str, key: str, name: str | None = None) -> list[Metric]:
    rows = db.scalars(select(Metric).where(Metric.workspace_id == workspace_id, Metric.status != "deprecated")).all()
    names = {key.lower()} | ({name.lower()} if name else set())
    return [m for m in rows if any(slugify(d) == key or d.lower() in names for d in (m.depends_on or []))]


def version_approvals(db: Session, metric_id: str, number: int) -> list[dict]:
    rows = db.scalars(
        select(MetricReview).where(MetricReview.metric_id == metric_id, MetricReview.version == number).order_by(MetricReview.created_at)
    ).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([r.user_id for r in rows if r.user_id]))).all()} if rows else {}
    return [
        {"decision": r.decision, "comment": r.comment, "at": r.created_at.isoformat(), "user": users[r.user_id].name if r.user_id in users else None}
        for r in rows
    ]
