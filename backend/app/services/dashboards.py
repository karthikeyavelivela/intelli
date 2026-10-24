from __future__ import annotations

import time

from sqlalchemy.orm import Session

from ..models import Dashboard, Dataset
from ..services.engine import QueryError, QueryTimeout
from ..services.formula import FormulaError
from ..services.metric_query import MetricUnavailable, default_dimension, find_metric, preset_range, run_metric

WIDGET_TYPES = ("kpi", "line", "bar", "pie", "table")

TEMPLATES = {
    "sales": {
        "name": "Sales Overview",
        "description": "Net revenue, orders and average order value with state-wise, region and payment-method breakdowns (INR, financial-year calendar).",
        "widgets": [
            {"type": "kpi", "title": "Revenue", "metric_key": "revenue", "w": 3, "h": 2},
            {"type": "kpi", "title": "Orders", "metric_key": "orders", "w": 3, "h": 2},
            {"type": "kpi", "title": "Average Order Value", "metric_key": "average_order_value", "w": 3, "h": 2},
            {"type": "kpi", "title": "Units Sold", "metric_key": "units_sold", "w": 3, "h": 2},
            {"type": "line", "title": "Revenue by month", "metric_key": "revenue", "grain": "month", "w": 8, "h": 4},
            {"type": "pie", "title": "Revenue by payment method", "metric_key": "revenue", "dimension": "payment_method", "w": 4, "h": 4},
            {"type": "bar", "title": "Top 10 states by revenue", "metric_key": "revenue", "dimension": "state", "limit": 10, "w": 6, "h": 4},
            {"type": "table", "title": "Revenue by category", "metric_key": "revenue", "dimension": "category", "w": 6, "h": 4},
        ],
    },
    "finance": {
        "name": "Finance Review",
        "description": "Revenue quality for the finance team: refunds, GST collected and gross margin.",
        "widgets": [
            {"type": "kpi", "title": "Revenue", "metric_key": "revenue", "w": 3, "h": 2},
            {"type": "kpi", "title": "Refunds", "metric_key": "refunds", "w": 3, "h": 2},
            {"type": "kpi", "title": "GST Collected", "metric_key": "gst_collected", "w": 3, "h": 2},
            {"type": "kpi", "title": "Gross Margin %", "metric_key": "gross_margin", "w": 3, "h": 2},
            {"type": "line", "title": "Refunds by month", "metric_key": "refunds", "grain": "month", "w": 6, "h": 4},
            {"type": "line", "title": "Gross margin % by month", "metric_key": "gross_margin", "grain": "month", "w": 6, "h": 4},
            {"type": "bar", "title": "GST collected by state (top 10)", "metric_key": "gst_collected", "dimension": "state", "limit": 10, "w": 6, "h": 4},
            {"type": "table", "title": "Refunds by category", "metric_key": "refunds", "dimension": "category", "w": 6, "h": 4},
        ],
    },
    "operations": {
        "name": "Operations Pulse",
        "description": "Order volume, active customers and return performance across channels and regions.",
        "widgets": [
            {"type": "kpi", "title": "Orders", "metric_key": "orders", "w": 3, "h": 2},
            {"type": "kpi", "title": "Units Sold", "metric_key": "units_sold", "w": 3, "h": 2},
            {"type": "kpi", "title": "Active Customers", "metric_key": "active_customers", "w": 3, "h": 2},
            {"type": "kpi", "title": "Return Rate", "metric_key": "return_rate", "w": 3, "h": 2},
            {"type": "line", "title": "Orders by week", "metric_key": "orders", "grain": "week", "w": 8, "h": 4},
            {"type": "pie", "title": "Orders by channel", "metric_key": "orders", "dimension": "channel", "w": 4, "h": 4},
            {"type": "bar", "title": "Units sold by region", "metric_key": "units_sold", "dimension": "region", "w": 12, "h": 4},
        ],
    },
}


def layout_widgets(widgets: list[dict]) -> list[dict]:
    """Assign ids and grid positions (12 columns) to widgets that lack them."""
    out, x, y, row_h = [], 0, 0, 0
    for i, w in enumerate(widgets):
        w = dict(w)
        w.setdefault("id", f"w{i + 1}")
        w.setdefault("w", 4)
        w.setdefault("h", 3)
        if "x" not in w or "y" not in w:
            if x + w["w"] > 12:
                x, y, row_h = 0, y + row_h, 0
            w["x"], w["y"] = x, y
            x += w["w"]
            row_h = max(row_h, w["h"])
        out.append(w)
    return out


def widget_data(db: Session, ws_id: str, user_id: str, widget: dict, filters: dict, policy: str) -> dict:
    t0 = time.perf_counter()
    try:
        m = find_metric(db, ws_id, widget.get("metric_key", ""))
        wtype = widget.get("type", "kpi")
        dim, grain = widget.get("dimension"), widget.get("grain")
        from ..services.engine import live_definition

        snap = live_definition(db, m, widget.get("pinned_version") if policy == "pinned" else None)
        ds = db.get(Dataset, snap["dataset_id"]) if snap else None
        if wtype == "kpi":
            dim, grain = None, None
        elif wtype == "line":
            if not grain:
                grain = "month"
            dim = dim or (ds.date_column if ds else None)
        elif not dim and ds is not None:
            dim = default_dimension(ds)
        tr = preset_range(filters.get("range")) or (
            {"start": filters["start"], "end": filters["end"]} if filters.get("start") and filters.get("end") else None
        )
        order = "dim" if grain else "value_desc"
        res, meta = run_metric(
            db, ws_id, user_id, widget["metric_key"], dimension=dim, grain=grain, time_range=tr, order=order,
            limit=int(widget.get("limit") or (50 if wtype in ("bar", "pie", "table") else 1000)), policy=policy,
            pinned_version=widget.get("pinned_version"), kind="dashboard", dept=filters.get("department"),
        )
        return {
            "ok": True, "columns": res.columns, "rows": res.rows, "unit": meta["unit"], "metric_name": meta["metric_name"],
            "version": meta["version"], "duration_ms": res.duration_ms, "dimension": dim, "grain": grain,
            "truncated": res.truncated, "load_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except (FormulaError, QueryError, QueryTimeout, MetricUnavailable) as e:
        return {"ok": False, "error": getattr(e, "message", str(e)), "load_ms": round((time.perf_counter() - t0) * 1000, 1)}


def dashboard_data(db: Session, d: Dashboard, user_id: str, filters: dict | None = None) -> dict:
    t0 = time.perf_counter()
    f = {**(d.filters or {}), **(filters or {})}
    data = {w["id"]: widget_data(db, d.workspace_id, user_id, w, f, d.version_policy) for w in (d.widgets or [])}
    return {"widgets": data, "load_ms": round((time.perf_counter() - t0) * 1000, 1), "filters": f, "policy": d.version_policy}
