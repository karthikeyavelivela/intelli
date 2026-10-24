"""Demo data seeding. EVERYTHING created here is synthetic, fictional and flagged is_demo=True; the UI labels it
"Demonstration data (synthetic)". Indian context: INR, GST, financial year April-March, IST.
Usage:  python -m app.seed            (seed if empty)
        python -m app.seed --reset    (wipe everything and re-seed)"""
from __future__ import annotations

import logging
import shutil
import sys
import time
from pathlib import Path

import polars as pl
from sqlalchemy import select

from .config import settings
from .db import Base, SessionLocal, engine
from .models import Dashboard, Dataset, IngestionJob, Metric, User, Workspace, utcnow
from .security import hash_password
from .seed_data import gen_dispatches, gen_frames
from .services import metrics as svc
from .services.audit import audit, notify
from .services.dashboards import TEMPLATES, layout_widgets
from .services.ingest import dataset_dir, profile_parquet
from .services.metric_query import MetricUnavailable, run_metric

log = logging.getLogger("app.seed")

DEMO_USERS = [
    ("admin@intellimetrics.demo", "Admin@12345", "Aarav Menon", "admin", "Head of Data Governance"),
    ("analyst@intellimetrics.demo", "Analyst@12345", "Diya Reddy", "data_analyst", "Senior Data Analyst"),
    ("business@intellimetrics.demo", "Business@12345", "Rohan Sharma", "business_user", "Regional Sales Manager, West"),
    ("reviewer@intellimetrics.demo", "Reviewer@12345", "Meera Iyer", "reviewer", "Finance Controller"),
]
OTHER_WS_USERS = [
    ("admin@sagarfoods.demo", "Admin@12345", "Suresh Naidu", "admin", "Head of Supply Chain Analytics"),
    ("analyst@sagarfoods.demo", "Analyst@12345", "Kavya Raju", "data_analyst", "Logistics Analyst"),
]
WS_A = ("Bharat Retail Pvt Ltd", "bharat-retail")
WS_B = ("Sagar Foods & Beverages Ltd", "sagar-foods")

DESCRIPTIONS = {
    "sales_transactions": "Line-level sales: gross, discount, GST and invoice amounts in INR, payment method, channel, state and region. Demonstration data (synthetic).",
    "orders": "Order headers aggregated from sales transactions. Demonstration data (synthetic).",
    "customers": "Customer master with Indian cities, states, PIN codes and fake +91 mobile numbers. Demonstration data (synthetic).",
    "products": "Product catalogue across FMCG, electronics, apparel and ethnic wear with GST slabs. Demonstration data (synthetic).",
    "refunds": "Refund events with reasons (damaged item, wrong item, COD returns, quality issue). Demonstration data (synthetic).",
    "departments": "Organisational departments and annual budgets in INR. Demonstration data (synthetic).",
    "distributor_dispatches": "Distributor dispatches of packaged foods and beverages with invoice value in INR. Demonstration data (synthetic).",
}


def register_dataset(db, ws: Workspace, name: str, df: pl.DataFrame, owner: User) -> Dataset:
    t0 = time.perf_counter()
    d = Dataset(workspace_id=ws.id, name=name, description=DESCRIPTIONS.get(name), source_type="seed", file_format="parquet", status="processing", is_demo=True, created_by=owner.id)
    db.add(d)
    db.flush()
    out = dataset_dir(ws.id) / f"{d.id}.parquet"
    df.write_parquet(out, compression="zstd")
    schema, profile, rows, date_col = profile_parquet(str(out))
    d.parquet_path, d.schema_json, d.profile, d.row_count, d.column_count, d.date_column = str(out), schema, profile, rows, len(schema), date_col
    d.size_bytes, d.status, d.progress, d.stage = out.stat().st_size, "ready", 100, "complete"
    ms = int((time.perf_counter() - t0) * 1000)
    db.add(IngestionJob(workspace_id=ws.id, dataset_id=d.id, status="succeeded", stage="complete", progress=100, rows=rows, bytes=d.size_bytes, duration_ms=ms, runner="seed", finished_at=utcnow()))
    return d


def _mk(db, user, ds, name, formula, *, key=None, filters=None, unit=None, dept=None, cat=None, desc=None, bdef=None, tw="all_time", dc=None, owner=None):
    data = {"name": name, "formula": formula, "filters": filters, "unit": unit, "department": dept, "category": cat, "description": desc,
            "business_definition": bdef, "dataset_id": ds.id, "time_window": tw, "date_column": dc, "owner_id": (owner or user).id}
    if key:
        data["key"] = key
    return svc.create_metric(db, user, data)


def _publish(db, m, submitter, reviewer, comment="Approved by governance review"):
    svc.transition(db, submitter, m, "submit", "Ready for review")
    svc.transition(db, reviewer, m, "approve", comment)
    svc.transition(db, reviewer, m, "publish", "Published as the governed definition")


def seed_all() -> None:
    db = SessionLocal()
    t0 = time.perf_counter()
    try:
        wsA = Workspace(name=WS_A[0], slug=WS_A[1], is_demo=True, settings={})
        wsB = Workspace(name=WS_B[0], slug=WS_B[1], is_demo=True, settings={})
        db.add_all([wsA, wsB])
        db.flush()
        users = {}
        for ws, rows in ((wsA, DEMO_USERS), (wsB, OTHER_WS_USERS)):
            for email, pw, name, role, title in rows:
                u = User(workspace_id=ws.id, email=email, name=name, password_hash=hash_password(pw), role=role, is_demo=True, title=title)
                db.add(u)
                users[email] = u
        db.flush()
        for u in users.values():
            u.workspace = wsA if u.workspace_id == wsA.id else wsB
        admin, analyst, biz, reviewer = (users[e[0]] for e in DEMO_USERS)

        log.info("generating synthetic Indian retail data")
        frames = gen_frames()
        ds = {n: register_dataset(db, wsA, n, df, admin) for n, df in frames.items()}
        sales = ds["sales_transactions"]
        db.flush()

        # --- governed metrics, published through the real workflow so versions/reviews/audit are authentic
        rev = _mk(db, analyst, sales, "Revenue", "SUM(gross_sales)", dept="Sales", cat="Financial", unit="INR", desc="Total revenue.", bdef="Initial draft: gross sales before discounts.")
        _publish(db, rev, analyst, reviewer, "Initial version approved")
        svc.update_metric(db, analyst, rev, {"formula": "SUM(net_sales)", "description": "Official company revenue: taxable net sales (after discounts, excluding GST), before refunds.",
                                             "business_definition": "Revenue is the SUM of net_sales (taxable value = gross sales less discounts, excluding GST) across all sales lines. GST collected and refunds are reported separately.",
                                             "date_column": "order_date"}, "Gross sales overstated revenue; discounts and GST must be excluded", None)
        _publish(db, rev, analyst, reviewer, "Net sales excluding GST is the agreed definition")
        orders = _mk(db, analyst, sales, "Orders", "COUNT_DISTINCT(order_id)", dept="Sales", cat="Volume", unit="count", desc="Number of distinct customer orders.", bdef="Each order may contain several lines; count distinct order_id.")
        _publish(db, orders, analyst, reviewer)
        units = _mk(db, analyst, sales, "Units Sold", "SUM(quantity)", dept="Operations", cat="Volume", unit="count", desc="Total units sold across all lines.", bdef="Sum of quantity.")
        _publish(db, units, analyst, reviewer)
        aov = _mk(db, analyst, sales, "Average Order Value", "[Revenue] / [Orders]", dept="Sales", cat="Financial", unit="INR", desc="Revenue divided by orders.", bdef="Derived metric: governed Revenue (ex-GST) divided by governed Orders.")
        _publish(db, aov, analyst, reviewer)
        refunds = _mk(db, analyst, sales, "Refunds", "SUM(refund_amount)", dept="Finance", cat="Financial", unit="INR", desc="Total refunded amount (taxable value).", bdef="Sum of refund_amount on sales lines.")
        _publish(db, refunds, analyst, reviewer)
        gstc = _mk(db, analyst, sales, "GST Collected", "SUM(gst_amount)", dept="Finance", cat="Financial", unit="INR", desc="GST charged on invoices (CGST + SGST + IGST combined).", bdef="Sum of gst_amount. Not part of Revenue.")
        _publish(db, gstc, analyst, reviewer)
        gm = _mk(db, analyst, sales, "Gross Margin %", "(SUM(net_sales) - SUM(cost)) / SUM(net_sales) * 100", dept="Finance", cat="Financial", unit="percent", desc="Share of net sales left after cost of goods.", bdef="(Net sales - cost) / net sales x 100, both excluding GST.")
        _publish(db, gm, analyst, reviewer)
        cust = _mk(db, analyst, sales, "Active Customers", "COUNT_DISTINCT(customer_id)", dept="Operations", cat="Customers", unit="count", desc="Distinct customers who ordered.", bdef="Distinct customer_id with at least one line in the period.")
        _publish(db, cust, analyst, reviewer)
        rr = _mk(db, analyst, sales, "Return Rate", "COUNTIF(refund_amount > 0) / COUNT(*) * 100", dept="Operations", cat="Quality", unit="percent", desc="Share of lines with a refund.", bdef="Lines with refund_amount > 0 divided by all lines.")
        _publish(db, rr, analyst, reviewer)

        # --- departmental variants (the conflict scenarios; left in review/draft, conflicts NOT pre-detected)
        fin_rev = _mk(db, analyst, sales, "Revenue", "SUM(net_sales) - SUM(refund_amount)", dept="Finance", cat="Financial", unit="INR", owner=reviewer,
                      desc="Finance view of revenue: net sales less refunds.", bdef="Finance reports revenue net of refunds so it reconciles to the ledger.", dc="order_date")
        svc.transition(db, analyst, fin_rev, "submit", "Finance variant for month-end close")
        gst_rev = _mk(db, analyst, sales, "Revenue", "SUM(net_amount)", dept="Marketing", cat="Financial", unit="INR", owner=analyst,
                      desc="Marketing view of revenue: invoice value INCLUDING GST.", bdef="Marketing quotes campaign revenue on the customer invoice value, which includes GST.", dc="order_date")
        svc.transition(db, analyst, gst_rev, "submit", "Revenue as shown on customer invoices (GST inclusive)")
        mk_orders = _mk(db, analyst, sales, "Orders", "COUNT(order_id)", dept="Marketing", cat="Volume", unit="count", desc="Order lines attributed to campaigns.", bdef="Marketing counts order lines.")
        svc.transition(db, analyst, mk_orders, "submit", "Campaign attribution reporting")
        _mk(db, analyst, sales, "Gross Margin %", "(SUM(net_sales) - SUM(cost)) / SUM(net_sales)", dept="Operations", cat="Financial", unit="ratio", desc="Margin as a 0-1 ratio.", bdef="Same as finance but as a ratio.")
        _mk(db, analyst, sales, "North India Revenue", "SUM(net_sales)", filters="region = 'North'", dept="Sales", cat="Financial", unit="INR", desc="Net sales in the North region.", bdef="Revenue limited to the North region.", dc="order_date")
        _mk(db, analyst, sales, "Revenue (Last 12 Months)", "SUM(net_sales)", dept="Sales", cat="Financial", unit="INR", tw="last_12_months", dc="order_date", desc="Rolling 12-month net sales.", bdef="Net sales over a rolling 365 days.")
        legacy = _mk(db, analyst, sales, "Legacy Sales Total", "SUM(gross_sales)", dept="Sales", cat="Financial", unit="INR", desc="Superseded by Revenue.", bdef="Deprecated.")
        svc.transition(db, reviewer, legacy, "deprecate", "Superseded by Revenue")

        # --- workspace B: Sagar Foods & Beverages Ltd
        ship_ws = users["analyst@sagarfoods.demo"]
        sh = register_dataset(db, wsB, "distributor_dispatches", gen_dispatches(), users["admin@sagarfoods.demo"])
        for nm, f, unit in (("Dispatches", "COUNT(*)", "count"), ("Invoice Value", "SUM(invoice_value)", "INR"), ("Average Delivery Days", "AVG(delivery_days)", "days")):
            mm = _mk(db, ship_ws, sh, nm, f, dept="Supply Chain", cat="Logistics", unit=unit, desc=f"{nm}. Demonstration data (synthetic).")
            _publish(db, mm, ship_ws, users["admin@sagarfoods.demo"])
        db.flush()

        # --- dashboards for workspace A
        for tkey, nm in (("sales", "Sales Overview"), ("finance", "Finance Review")):
            t = TEMPLATES[tkey]
            db.add(Dashboard(workspace_id=wsA.id, name=nm, description=t["description"], template=tkey, filters={"range": "this_fy"}, version_policy="latest_published",
                             widgets=layout_widgets(t["widgets"]), created_by=analyst.id))
        notify(db, wsA.id, "Welcome to IntelliMetrics AI", "TARA is your governed-metrics assistant. Try: Which 5 states had the highest sales this year?", "info", "/app/ask")
        notify(db, wsA.id, "Demonstration data loaded", "Bharat Retail Pvt Ltd is a fictional workspace: 62,000 synthetic sales lines (INR, GST, FY April-March). Run conflict detection to find the Finance and Marketing Revenue conflicts.", "info", "/app/conflicts")
        notify(db, wsB.id, "Demonstration data loaded", "Sagar Foods & Beverages Ltd is a fictional workspace (synthetic data).", "info", "/app/dashboard")
        audit(db, admin, "seed.demo", "workspace", wsA.id, {"note": "Synthetic demo data seeded"})
        db.commit()

        # --- warm telemetry so Evaluation/Dashboard have real history (these are genuine executions)
        for wid, u in ((wsA.id, analyst), (wsB.id, ship_ws)):
            for m in db.scalars(select(Metric).where(Metric.workspace_id == wid, Metric.is_live.is_(True))).all():
                try:
                    run_metric(db, wid, u.id, m.key, kind="execute")
                except (MetricUnavailable, Exception):  # noqa: BLE001
                    pass
        db.commit()
        log.info("seed complete in %.1fs", time.perf_counter() - t0)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_if_empty() -> bool:
    if settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Workspace).limit(1)):
            return False
    seed_all()
    return True


def reset_demo() -> None:
    """Wipe ALL data (tables + dataset files) and re-seed. Destructive: intended for demo environments."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    root = Path(settings.DATA_DIR)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    seed_all()


if __name__ == "__main__":
    from .logging_setup import setup_logging

    setup_logging()
    if "--reset" in sys.argv:
        reset_demo()
        print("Demo reset complete.")
    else:
        print("Seeded." if seed_if_empty() else "Database already has data; use --reset to wipe and reseed.")
