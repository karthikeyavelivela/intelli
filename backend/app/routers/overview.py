from fastapi import APIRouter, Depends
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Conflict, Dashboard, Dataset, Execution, Metric, MetricVersion, Notification, User
from ..services.ai import ai_status
from ..services.metric_query import MetricUnavailable, find_metric, run_metric

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("")
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = user.workspace_id
    cnt = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    total_metrics = cnt(select(func.count()).select_from(Metric).where(Metric.workspace_id == ws, Metric.status != "deprecated"))
    published = cnt(select(func.count()).select_from(Metric).where(Metric.workspace_id == ws, Metric.is_live.is_(True)))
    in_review = cnt(select(func.count()).select_from(Metric).where(Metric.workspace_id == ws, Metric.status == "in_review"))
    datasets = cnt(select(func.count()).select_from(Dataset).where(Dataset.workspace_id == ws, Dataset.status == "ready"))
    processing = cnt(select(func.count()).select_from(Dataset).where(Dataset.workspace_id == ws, Dataset.status.in_(["pending", "processing"])))
    conflicts_active = cnt(select(func.count()).select_from(Conflict).where(Conflict.workspace_id == ws, Conflict.status.notin_(["resolved", "dismissed"])))
    conflicts_resolved = cnt(select(func.count()).select_from(Conflict).where(Conflict.workspace_id == ws, Conflict.status == "resolved"))
    val = db.execute(select(func.count(), func.sum(cast(Execution.ok, Integer))).where(Execution.workspace_id == ws, Execution.kind == "validate")).one()
    val_total, val_ok = val[0] or 0, int(val[1] or 0)
    ex = db.execute(select(func.count(), func.sum(cast(Execution.ok, Integer)), func.avg(Execution.duration_ms)).where(Execution.workspace_id == ws, Execution.kind.in_(["execute", "chat", "dashboard"]))).one()

    # validation pass rate: every non-deprecated metric definition re-validated against its dataset right now
    from ..services.engine import metric_snapshot
    from ..services.metrics import validate_definition

    defs = db.scalars(select(Metric).where(Metric.workspace_id == ws, Metric.status != "deprecated")).all()
    defs_ok = sum(1 for m in defs if validate_definition(db, ws, metric_snapshot(m))["ok"])

    recent_uploads = db.scalars(select(Dataset).where(Dataset.workspace_id == ws).order_by(Dataset.created_at.desc()).limit(5)).all()
    recent_changes = db.execute(
        select(MetricVersion, Metric).join(Metric, Metric.id == MetricVersion.metric_id).where(MetricVersion.workspace_id == ws).order_by(MetricVersion.created_at.desc()).limit(6)
    ).all()
    names = {u.id: u.name for u in db.scalars(select(User).where(User.workspace_id == ws)).all()}
    notes = db.scalars(select(Notification).where(Notification.workspace_id == ws).order_by(Notification.created_at.desc()).limit(6)).all()

    # revenue & performance charts straight from the governed layer (empty when no published Revenue metric exists)
    charts: dict = {"revenue_by_month": None, "revenue_by_region": None, "orders_by_month": None}
    for name, key, dim, grain in (("revenue_by_month", "revenue", None, "month"), ("revenue_by_region", "revenue", "region", None), ("orders_by_month", "orders", None, "month")):
        try:
            m = find_metric(db, ws, key)
            ds = m.dataset
            d = dim if dim else (ds.date_column if ds else None)
            if not d:
                continue
            res, meta = run_metric(db, ws, user.id, key, dimension=d, grain=grain, order="dim" if grain else "value_desc", limit=36 if grain else 8, kind="dashboard")
            rows = res.rows[-12:] if grain else res.rows
            charts[name] = {"metric": meta["metric_name"], "unit": meta["unit"], "version": meta["version"], "data": [{"x": str(r[0]), "y": r[-1]} for r in rows]}
        except (MetricUnavailable, Exception):  # noqa: BLE001
            continue
    db.commit()
    return {
        "kpis": {
            "total_metrics": total_metrics, "published_metrics": published, "in_review": in_review, "connected_datasets": datasets, "processing_datasets": processing,
            "active_conflicts": conflicts_active, "resolved_conflicts": conflicts_resolved,
            "validation_pass_rate": round(defs_ok / len(defs), 4) if defs else None, "validation_checks": len(defs), "lab_validations": val_total,
            "query_success_rate": round(int(ex[1] or 0) / ex[0], 4) if ex[0] else None, "avg_query_ms": round(ex[2], 1) if ex[2] else None,
            "dashboards": cnt(select(func.count()).select_from(Dashboard).where(Dashboard.workspace_id == ws)),
        },
        "recent_uploads": [{"id": d.id, "name": d.name, "status": d.status, "row_count": d.row_count, "progress": d.progress, "created_at": d.created_at.isoformat(), "is_demo": d.is_demo} for d in recent_uploads],
        "recent_changes": [{"metric_id": m.id, "metric_name": m.name, "version": v.number, "summary": v.change_summary, "author": names.get(v.author_id), "created_at": v.created_at.isoformat()} for v, m in recent_changes],
        "notifications": [{"id": n.id, "title": n.title, "body": n.body, "kind": n.kind, "link": n.link, "created_at": n.created_at.isoformat()} for n in notes],
        "charts": charts,
        "ai": ai_status(user.workspace),
        "is_demo_workspace": user.workspace.is_demo,
    }
