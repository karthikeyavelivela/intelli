"""Run a governed metric (by key) through the same compiler/engine as the Formula Lab. Shared by chat + dashboards."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Dataset, Metric
from .calendar_in import fq_bounds, fq_of, fy_bounds, fy_start_year, last_completed_fq, today_ist
from .engine import QueryResult, QuerySpec, live_definition, make_resolver, run_query, window_range
from .formula import FormulaError


class MetricUnavailable(Exception):
    pass


def find_metric(db: Session, ws_id: str, key: str) -> Metric:
    rows = db.scalars(select(Metric).where(Metric.workspace_id == ws_id, Metric.key == key, Metric.status != "deprecated")).all()
    live = [m for m in rows if m.is_live]
    cand = live or [m for m in rows if m.status == "approved"]
    if not cand:
        raise MetricUnavailable(f"No published or approved definition exists for metric '{key}'")
    return cand[0]


def preset_range(preset: str | None, today: dt.date | None = None) -> dict | None:
    """Dashboard time-range presets on the Indian financial-year calendar (Apr-Mar, IST)."""
    today = today or today_ist()
    if not preset or preset == "all":
        return None
    if preset in ("this_fy", "ytd"):
        return {"start": fy_bounds(fy_start_year(today))[0].isoformat(), "end": today.isoformat()}
    if preset == "last_fy":
        a, b = fy_bounds(fy_start_year(today) - 1)
        return {"start": a.isoformat(), "end": b.isoformat()}
    if preset == "last_quarter":
        a, b = fq_bounds(*last_completed_fq(today))
        return {"start": a.isoformat(), "end": b.isoformat()}
    if preset == "this_quarter":
        a, _ = fq_bounds(*fq_of(today))
        return {"start": a.isoformat(), "end": today.isoformat()}
    w = window_range(preset, today)
    return {"start": w[0], "end": w[1]} if w else None


def run_metric(
    db: Session, ws_id: str, user_id: str | None, key: str, *, dimension: str | None = None, dimension2: str | None = None, grain: str | None = None,
    time_range: dict | None = None, filters: list[dict] | None = None, order: str = "dim", limit: int = 1000,
    policy: str = "latest_published", pinned_version: int | None = None, kind: str = "dashboard", dept: str | None = None,
) -> tuple[QueryResult, dict]:
    m = find_metric(db, ws_id, key)
    snap = live_definition(db, m, pinned_version if policy == "pinned" else None)
    if snap is None:
        raise MetricUnavailable(f"Metric '{m.name}' has no usable version")
    ds = db.get(Dataset, snap["dataset_id"]) if snap.get("dataset_id") else None
    if ds is None or ds.workspace_id != ws_id:
        raise MetricUnavailable("The dataset for this metric is not available")
    where = list(filters or [])
    if dept:
        dc = next((c["name"] for c in ds.schema_json if c["name"].lower() in ("department", "business_unit")), None)
        if dc:
            where.append({"column": dc, "op": "=", "value": dept})
    tr = time_range
    if not tr:
        w = window_range(snap.get("time_window"))
        if w:
            tr = {"column": snap.get("date_column"), "start": w[0], "end": w[1]}
    elif not tr.get("column") and snap.get("date_column"):
        tr = {**tr, "column": snap["date_column"]}
    dims = []
    if dimension:
        dims = [{"column": dimension, **({"grain": grain} if grain else {})}]
        if dimension2:
            dims.append({"column": dimension2})
    spec = QuerySpec(formula=snap["formula"], filters=snap.get("filters"), dimensions=dims, time_range=tr, where=where, order=order, limit=limit)
    pins = {key: pinned_version} if (policy == "pinned" and pinned_version) else {}
    res = run_query(db, ds, spec, user_id, kind, make_resolver(db, ws_id, ds.id, "live", pins))
    meta = {
        "metric_id": m.id, "metric_key": m.key, "metric_name": snap.get("name") or m.name, "version": snap.get("_version"), "unit": snap.get("unit"),
        "formula": snap["formula"], "filters": snap.get("filters"), "dataset_id": ds.id, "dataset_name": ds.name, "policy": policy,
        "time_range": tr, "department": m.department, "status": m.status,
    }
    return res, meta


def default_dimension(ds: Dataset) -> str | None:
    prof = {c["name"]: c for c in (ds.profile or {}).get("columns", [])}
    for c in ds.schema_json:
        if c["category"] == "string" and 1 < prof.get(c["name"], {}).get("distinct", 0) <= 30 and not c["name"].endswith("_id"):
            return c["name"]
    return None


__all__ = ["run_metric", "find_metric", "MetricUnavailable", "preset_range", "default_dimension", "FormulaError"]
