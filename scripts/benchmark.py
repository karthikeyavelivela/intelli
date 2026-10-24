"""Reproducible benchmark on the 62,000-row synthetic Indian retail dataset. Writes docs/data/benchmark.json.

Runs against an ISOLATED temporary database (never your dev DB):
    backend/.venv/Scripts/python.exe scripts/benchmark.py        (Windows)
    backend/.venv/bin/python scripts/benchmark.py                 (Linux/macOS)

Everything reported is MEASURED on this machine in offline TARA mode (no AI key). Manual-effort baselines live in the
evaluation module and are labelled as assumptions there; this script does not invent any."""
from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
_tmp = tempfile.mkdtemp(prefix="im_bench_")
os.environ.update(ENV="test", DATABASE_URL=f"sqlite:///{_tmp}/bench.db", DATA_DIR=f"{_tmp}/datasets", RATE_LIMIT_ENABLED="false", AI_PROVIDER="none",
                  OPENAI_API_KEY="", GEMINI_API_KEY="", USE_CELERY="false", SECRET_KEY="benchmark-secret-benchmark-secret-12345")

import duckdb  # noqa: E402
import polars as pl  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_all  # noqa: E402
from app.seed_data import gen_frames  # noqa: E402
from app.services.calendar_in import now_ist  # noqa: E402

H = {"X-Requested-With": "IntelliMetrics"}


def pctl(vals: list[float], p: float) -> float:
    s = sorted(vals)
    k = (len(s) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 2)


def stats_of(vals: list[float]) -> dict:
    return {"n": len(vals), "mean": round(statistics.mean(vals), 2), "min": round(min(vals), 2), "p50": pctl(vals, 50), "p95": pctl(vals, 95), "p99": pctl(vals, 99), "max": round(max(vals), 2)}


def login(who: str, pw: str) -> TestClient:
    c = TestClient(app, headers=H)
    r = c.post("/api/auth/login", json={"email": who, "password": pw})
    assert r.status_code == 200, r.text
    return c


def wait_ready(c: TestClient, did: str, timeout: float = 300) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get(f"/api/datasets/{did}/status").json()
        if s["status"] in ("ready", "failed"):
            return s
        time.sleep(0.05)
    raise TimeoutError(did)


def main() -> None:
    out: dict = {"started_at_ist": now_ist().strftime("%d-%b-%Y %H:%M IST")}
    out["environment"] = {
        "platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(), "processor": platform.processor(),
        "duckdb": duckdb.__version__, "polars": pl.__version__, "database": "SQLite (temporary)", "job_runner": "in-process thread (USE_CELERY=false)", "ai_mode": "offline deterministic (no AI key)",
    }
    Base.metadata.create_all(engine)
    t0 = time.perf_counter()
    seed_all()
    out["seed_seconds"] = round(time.perf_counter() - t0, 2)

    analyst = login("analyst@intellimetrics.demo", "Analyst@12345")
    admin = login("admin@intellimetrics.demo", "Admin@12345")
    business = login("business@intellimetrics.demo", "Business@12345")
    reviewer = login("reviewer@intellimetrics.demo", "Reviewer@12345")
    ds = next(d for d in analyst.get("/api/datasets").json()["items"] if d["name"] == "sales_transactions")
    out["dataset"] = {"name": ds["name"], "rows": ds["row_count"], "columns": ds["column_count"], "parquet_bytes": ds["size_bytes"]}

    # ------------------------------------------------------------------ 1. ingestion (background job) on 62k rows, 3 formats x 3 runs, + a 4x scale run
    frames = gen_frames()
    sales: pl.DataFrame = frames["sales_transactions"]
    files = Path(_tmp) / "upload"
    files.mkdir()
    sales.write_csv(files / "sales.csv")
    sales.write_parquet(files / "sales.parquet")
    sales.write_ndjson(files / "sales.ndjson")
    big = pl.concat([sales.with_columns((pl.col("order_id") + f"-{i}").alias("order_id")) for i in range(4)])
    big.write_csv(files / "sales_x4.csv")
    ingestion = []
    for label, fname, mime, runs in (("CSV", "sales.csv", "text/csv", 3), ("Parquet", "sales.parquet", "application/octet-stream", 3), ("NDJSON", "sales.ndjson", "application/json", 3), ("CSV x4 (scale test)", "sales_x4.csv", "text/csv", 1)):
        walls, jobs, rows = [], [], 0
        for _ in range(runs):
            data = (files / fname).read_bytes()
            t = time.perf_counter()
            r = analyst.post("/api/datasets/upload", files={"file": (fname, data, mime)})
            assert r.status_code == 202, r.text
            did = r.json()["dataset"]["id"]
            st = wait_ready(analyst, did)
            walls.append((time.perf_counter() - t) * 1000)
            assert st["status"] == "ready", st
            rows = st["row_count"]
            jobs.append(analyst.get(f"/api/datasets/{did}/jobs").json()["items"][0]["duration_ms"])
        size_mb = round((files / fname).stat().st_size / 1_048_576, 1)
        ingestion.append({"format": label, "rows": rows, "file_mb": size_mb, "runs": runs, "job_ms": stats_of([float(x) for x in jobs]) if runs > 1 else {"mean": float(jobs[0])},
                          "upload_to_ready_ms": stats_of(walls) if runs > 1 else {"mean": round(walls[0], 1)}, "rows_per_second": round(rows / (statistics.mean(jobs) / 1000))})
    out["ingestion"] = ingestion

    # ------------------------------------------------------------------ 2. query latency
    live = [m for m in analyst.get("/api/metrics", params={"live_only": True, "page_size": 100}).json()["items"]]
    workloads = []
    for m in live:
        workloads.append((f"{m['name']} (KPI)", {"dataset_id": ds["id"], "formula": m["formula"], "filters": m["filters"]}))
    workloads += [
        ("Revenue by month", {"dataset_id": ds["id"], "formula": "SUM(net_sales)", "dimensions": [{"column": "order_date", "grain": "month"}]}),
        ("Revenue by state (top 10)", {"dataset_id": ds["id"], "formula": "SUM(net_sales)", "dimensions": [{"column": "state"}], "order": "value_desc", "limit": 10}),
        ("Revenue by region x payment method", {"dataset_id": ds["id"], "formula": "SUM(net_sales)", "dimensions": [{"column": "region"}, {"column": "payment_method"}]}),
        ("Top 10 customers by revenue", {"dataset_id": ds["id"], "formula": "SUM(net_sales)", "dimensions": [{"column": "customer_name"}], "order": "value_desc", "limit": 10}),
        ("Return rate by payment method", {"dataset_id": ds["id"], "formula": "COUNTIF(refund_amount > 0) / COUNT(*) * 100", "dimensions": [{"column": "payment_method"}]}),
    ]
    engine_ms, http_ms, per = [], [], []
    for name, body in workloads:
        e, h = [], []
        for _ in range(30):
            t = time.perf_counter()
            r = analyst.post("/api/execution/run", json=body)
            h.append((time.perf_counter() - t) * 1000)
            assert r.status_code == 200, (name, r.text)
            e.append(r.json()["duration_ms"])
        engine_ms += e
        http_ms += h
        per.append({"workload": name, "engine_p50_ms": pctl(e, 50), "engine_p95_ms": pctl(e, 95), "http_p50_ms": pctl(h, 50), "http_p95_ms": pctl(h, 95)})
    out["query_latency"] = {"workloads": len(workloads), "samples": len(engine_ms), "engine_ms": stats_of(engine_ms), "http_roundtrip_ms": stats_of(http_ms), "per_workload": per}

    # ------------------------------------------------------------------ 3. dashboards
    dash = []
    for tpl in ("sales", "finance", "operations"):
        d = analyst.post("/api/dashboards/from-template", json={"template": tpl, "name": f"Benchmark {tpl}"}).json()
        loads, walls, failed = [], [], 0
        for _ in range(10):
            t = time.perf_counter()
            r = analyst.post(f"/api/dashboards/{d['id']}/data", json={"filters": {"range": "this_fy"}}).json()
            walls.append((time.perf_counter() - t) * 1000)
            loads.append(r["load_ms"])
            failed += sum(1 for w in r["widgets"].values() if not w["ok"])
        dash.append({"template": tpl, "widgets": len(d["widgets"]), "server_load_ms": stats_of(loads), "http_ms": stats_of(walls), "failed_widgets": failed})
    out["dashboards"] = dash

    # ------------------------------------------------------------------ 4. Ask TARA (offline planner) end to end
    questions = [
        "What was net revenue by month in the last quarter of this financial year?", "Which 5 states had the highest sales this year?",
        "Compare Diwali-season sales with the previous quarter", "What is the UPI vs COD split by region?", "Top 10 customers by revenue",
        "What is the weather in Paris?", "revenue by weather",
    ]
    ask = []
    for q in questions:
        walls, kinds = [], set()
        for _ in range(10):
            t = time.perf_counter()
            a = business.post("/api/chat/ask", json={"question": q}).json()
            walls.append((time.perf_counter() - t) * 1000)
            kinds.add(a["kind"])
        ask.append({"question": q, "result": sorted(kinds)[0], "http_ms": stats_of(walls)})
    out["ask_tara"] = ask

    # ------------------------------------------------------------------ 5. conflict detection
    det = []
    for _ in range(5):
        t = time.perf_counter()
        r = reviewer.post("/api/conflicts/detect").json()
        det.append((time.perf_counter() - t) * 1000)
        out.setdefault("conflict_detection_result", {"created": r["created"], "total_open": r["total_open"]}) if r["created"] else None
    out["conflict_detection_ms"] = stats_of(det)

    # ------------------------------------------------------------------ 6. scripted TARA generator session (offline mode): accept valid suggestions, discard the rest
    prompts = [
        "Total net sales for the Online channel", "Average quantity per order line", "Number of distinct customers who ordered in the South region", "Total GST collected",
        "Total refunds amount", "Gross margin percentage", "Total quantity of units sold in the West region", "Number of orders from UPI payments",
        "The flux capacitor harmonic resonance", "Sum of the happiness index",
    ]
    gens, accepted, valid, lat = 0, 0, 0, []
    for p in prompts:
        r = analyst.post("/api/ai/generate-metric", json={"prompt": p, "dataset_id": ds["id"]}).json()
        gens += 1
        if r.get("ok"):
            lat.append(r["latency_ms"])
            if r["validation"]["ok"]:
                valid += 1
                s = analyst.post(f"/api/ai/generations/{r['id']}/save", json={"definition": {"name": f"Bench {gens} {r['suggestion']['name']}"[:120]}, "submit": False})
                accepted += int(s.status_code == 200)
    out["tara_generator_session"] = {"prompts": gens, "generated": len(lat), "valid": valid, "accepted": accepted, "latency_ms": stats_of(lat) if lat else None,
                                     "note": "Scripted session in offline mode: 2 of the 10 prompts are deliberately unanswerable."}

    # ------------------------------------------------------------------ 7. the platform's own evaluation module
    ev = analyst.post("/api/evaluation/run").json()
    out["evaluation"] = ev["results"]
    out["evaluation_run_ms"] = ev["duration_ms"]
    out["finished_at_ist"] = now_ist().strftime("%d-%b-%Y %H:%M IST")

    dest = ROOT / "docs" / "data" / "benchmark.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("seed_seconds", "dataset")}, indent=1))
    print("ingestion:", [(i["format"], i["rows"], i["job_ms"].get("mean"), i["rows_per_second"]) for i in ingestion])
    print("query engine ms:", out["query_latency"]["engine_ms"])
    print("dashboards:", [(d["template"], d["server_load_ms"]["p50"], d["failed_widgets"]) for d in dash])
    print("written", dest)


if __name__ == "__main__":
    main()
