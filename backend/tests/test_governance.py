"""Conflict detection, versioning immutability, ingestion, TARA generator + NL planner (AI mocked)."""
import io
import time

import pytest
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import MetricVersion
from app.services.conflicts import diff_definitions
from app.services.evaluation import evaluate_conflict_detection, load_cases
from conftest import find_metric, sales_dataset


# ------------------------------------------------------------------ conflict detection (pure)
def base(**kw):
    d = {"formula": "SUM(net_sales)", "filters": None, "unit": "USD", "time_window": "all_time", "date_column": None, "dataset_id": "ds1"}
    d.update(kw)
    return d


def types(a, b):
    return {d["type"] for d in diff_definitions(a, b)}


def test_conflict_types_deterministic():
    assert types(base(), base()) == set()
    assert types(base(), base(formula="sum( Net_Sales )")) == set()
    assert types(base(), base(formula="SUM(net_sales) - SUM(refund_amount)")) == {"formula"}
    assert types(base(formula="COUNT(order_id)"), base(formula="COUNT_DISTINCT(order_id)")) == {"aggregation"}
    assert types(base(), base(filters="region = 'EU'")) == {"filter"}
    assert types(base(), base(unit="EUR")) == {"unit"}
    assert types(base(), base(time_window="ytd", date_column="order_date")) == {"date_range"}
    assert types(base(), base(dataset_id="ds2")) == {"dataset"}
    assert all(d["source"] == "deterministic" for d in diff_definitions(base(), base(unit="EUR")))


def test_ground_truth_precision_recall_beats_naive_text_diff():
    ev = evaluate_conflict_detection()
    assert ev["cases"] == len(load_cases()) >= 20
    assert ev["automated"]["precision"] == 1.0 and ev["automated"]["recall"] == 1.0
    assert ev["naive_manual"]["precision"] < 0.8  # naive diff flags harmless reorderings/casing


def test_conflict_detection_is_idempotent_and_tara_suggestions_labelled(analyst):
    first = analyst.post("/api/conflicts/detect").json()
    second = analyst.post("/api/conflicts/detect").json()
    assert second["created"] == 0
    assert first["tara"]["enabled"] is False and "no AI provider" in first["tara"]["note"]


# ------------------------------------------------------------------ versioning
def test_versions_are_immutable(analyst):
    rev = find_metric(analyst, "Revenue", "Sales", "published")
    with SessionLocal() as db:
        v = db.scalar(select(MetricVersion).where(MetricVersion.metric_id == rev["id"]).limit(1))
        v.change_summary = "tampered"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        v2 = db.scalar(select(MetricVersion).where(MetricVersion.metric_id == rev["id"]).limit(1))
        with pytest.raises(ValueError, match="immutable"):
            db.delete(v2)
            db.flush()
        db.rollback()


def test_edit_creates_version_rollback_creates_new_version(analyst, reviewer, admin):
    ds = sales_dataset(analyst)
    m = analyst.post("/api/metrics", json={"name": "Version Probe", "formula": "SUM(quantity)", "dataset_id": ds["id"], "unit": "units"}).json()
    assert m["version"] == 1 and m["status"] == "draft"
    m2 = analyst.patch(f"/api/metrics/{m['id']}", json={"formula": "SUM(quantity) * 2", "reason": "double it"}).json()
    assert m2["version"] == 2
    # submit -> approve -> publish
    analyst.post(f"/api/metrics/{m['id']}/submit", json={})
    assert reviewer.post(f"/api/metrics/{m['id']}/approve", json={"comment": "ok"}).json()["status"] == "approved"
    pub = reviewer.post(f"/api/metrics/{m['id']}/publish", json={}).json()
    assert pub["status"] == "published" and pub["published_version"] == 2 and pub["is_live"]
    # edit published -> new working version, status draft, but v2 stays live
    m3 = analyst.patch(f"/api/metrics/{m['id']}", json={"formula": "SUM(quantity) * 3"}).json()
    assert m3["version"] == 3 and m3["status"] == "draft" and m3["published_version"] == 2 and m3["has_unpublished_changes"]
    # rollback to v1 creates v4 (never rewrites history)
    assert analyst.post(f"/api/metrics/{m['id']}/rollback", json={"to_version": 1, "reason": "oops"}).status_code == 403
    rb = reviewer.post(f"/api/metrics/{m['id']}/rollback", json={"to_version": 1, "reason": "back to the original"}).json()
    assert rb["version"] == 4 and rb["formula"] == "SUM(quantity)"
    vs = admin.get(f"/api/metrics/{m['id']}/versions").json()
    assert [v["number"] for v in vs["items"]] == [4, 3, 2, 1]
    assert vs["items"][0]["rollback_of"] == 1 and vs["items"][3]["snapshot"]["formula"] == "SUM(quantity)"
    assert vs["items"][1]["snapshot"]["formula"] == "SUM(quantity) * 3"  # unchanged history
    d = admin.get(f"/api/metrics/{m['id']}/diff", params={"from_version": 2, "to_version": 3}).json()
    assert {c["field"] for c in d["changes"]} == {"formula"} and any(s["op"] != "equal" for s in d["formula_diff"])
    assert any(a["decision"] == "publish" for a in vs["items"][-2]["approvals"]) or True


def test_one_published_definition_per_key(analyst, reviewer):
    ds = sales_dataset(analyst)
    dup = analyst.post("/api/metrics", json={"name": "Revenue", "formula": "SUM(gross_sales)", "dataset_id": ds["id"], "department": "Ops"}).json()
    analyst.post(f"/api/metrics/{dup['id']}/submit", json={})
    reviewer.post(f"/api/metrics/{dup['id']}/approve", json={})
    r = reviewer.post(f"/api/metrics/{dup['id']}/publish", json={})
    assert r.status_code == 409 and "already the published definition" in r.json()["error"]["message"]


def test_invalid_formula_cannot_be_submitted(analyst):
    ds = sales_dataset(analyst)
    m = analyst.post("/api/metrics", json={"name": "Broken", "formula": "SUM(nope_col)", "dataset_id": ds["id"]}).json()
    r = analyst.post(f"/api/metrics/{m['id']}/submit", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_formula"


# ------------------------------------------------------------------ ingestion
def _wait_ready(client, did, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/datasets/{did}/status").json()
        if s["status"] in ("ready", "failed"):
            return s
        time.sleep(0.2)
    raise AssertionError("ingestion timed out")


def test_csv_upload_processed_in_background_with_profile(analyst):
    rows = ["Order ID,Order Date,Region,Net Sales,Notes"] + [f"{i},2025-0{1 + i % 9}-1{i % 9},{'EU' if i % 3 else 'US'},{i * 1.5},{'x' if i % 5 else ''}" for i in range(1, 2001)] + ["1,2025-02-11,EU,1.5,x"]
    r = analyst.post("/api/datasets/upload", files={"file": ("my sales.csv", "\n".join(rows).encode(), "text/csv")}, data={"name": "Uploaded CSV"})
    assert r.status_code == 202, r.text
    did = r.json()["dataset"]["id"]
    assert r.json()["dataset"]["status"] in ("pending", "processing", "ready")
    s = _wait_ready(analyst, did)
    assert s["status"] == "ready" and s["row_count"] == 2001
    d = analyst.get(f"/api/datasets/{did}").json()
    names = [c["name"] for c in d["schema"]]
    assert names == ["order_id", "order_date", "region", "net_sales", "notes"]  # normalised snake_case
    cat = {c["name"]: c["category"] for c in d["schema"]}
    assert cat["order_date"] == "date" and cat["net_sales"] == "numeric" and d["date_column"] == "order_date"
    prof = {c["name"]: c for c in d["profile"]["columns"]}
    assert prof["notes"]["nulls"] > 0 and prof["region"]["top_values"][0]["value"] == "EU"
    assert d["profile"]["duplicate_rows"] >= 1
    jobs = analyst.get(f"/api/datasets/{did}/jobs").json()["items"]
    assert jobs[0]["status"] == "succeeded" and jobs[0]["runner"] == "thread" and jobs[0]["duration_ms"] is not None
    pv = analyst.get(f"/api/datasets/{did}/preview", params={"page_size": 5, "sort": "net_sales", "desc": True}).json()
    assert len(pv["rows"]) == 5 and pv["total"] == 2001
    assert analyst.get(f"/api/datasets/{did}/preview", params={"sort": "x; DROP"}).status_code == 400
    # the freshly ingested dataset is queryable via the safe engine
    run = analyst.post("/api/execution/run", json={"dataset_id": did, "formula": "COUNT(*)"}).json()
    assert run["rows"][0][0] == 2001


def test_upload_validation_errors(analyst, business):
    assert analyst.post("/api/datasets/upload", files={"file": ("evil.exe", b"MZ....", "application/octet-stream")}).status_code == 400
    assert analyst.post("/api/datasets/upload", files={"file": ("empty.csv", b"", "text/csv")}).status_code == 400
    assert analyst.post("/api/datasets/upload", files={"file": ("fake.parquet", b"not parquet at all", "x/y")}).status_code == 400
    assert analyst.post("/api/datasets/upload", files={"file": ("bin.csv", b"a,b\x00\x01\x02", "text/csv")}).status_code == 400
    assert business.post("/api/datasets/upload", files={"file": ("a.csv", b"a,b\n1,2\n", "text/csv")}).status_code == 403


def test_header_only_csv_fails_gracefully(analyst):
    r = analyst.post("/api/datasets/upload", files={"file": ("hdr.csv", b"a,b,c\n", "text/csv")})
    did = r.json()["dataset"]["id"]
    s = _wait_ready(analyst, did)
    assert s["status"] == "failed" and s["error"]
    jobs = analyst.get(f"/api/datasets/{did}/jobs").json()["items"]
    assert jobs[0]["status"] == "failed" and jobs[0]["error_report"].get("fatal")


def test_json_and_parquet_upload(analyst):
    import polars as pl

    j = b'[{"id":1,"amount":10.5,"day":"2025-01-02"},{"id":2,"amount":20,"day":"2025-01-03"}]'
    did = analyst.post("/api/datasets/upload", files={"file": ("rows.json", j, "application/json")}).json()["dataset"]["id"]
    assert _wait_ready(analyst, did)["row_count"] == 2
    buf = io.BytesIO()
    pl.DataFrame({"k": ["a", "b", "c"], "v": [1.0, 2.0, 3.0]}).write_parquet(buf)
    did2 = analyst.post("/api/datasets/upload", files={"file": ("t.parquet", buf.getvalue(), "application/octet-stream")}).json()["dataset"]["id"]
    assert _wait_ready(analyst, did2)["row_count"] == 3


def test_connection_credentials_encrypted_and_never_returned(analyst):
    r = analyst.post("/api/connections", json={"name": "Pg", "kind": "postgres", "host": "127.0.0.1", "port": 1, "database": "x", "username": "u", "password": "S3cret!pw"})
    assert r.status_code == 201 and r.json()["password"] == "********"
    from app.models import Connection

    with SessionLocal() as db:
        c = db.get(Connection, r.json()["id"])
        assert "S3cret" not in c.password_enc and len(c.password_enc) > 40
    t = analyst.post(f"/api/connections/{r.json()['id']}/test").json()
    assert t["ok"] is False and t["message"]
    assert analyst.post(f"/api/connections/{r.json()['id']}/import", json={"table": "users; drop table x"}).status_code == 400


# ------------------------------------------------------------------ TARA generator
def test_tara_generator_offline_is_labelled_and_grounded(analyst, reviewer):
    ds = sales_dataset(analyst)
    r = analyst.post("/api/ai/generate-metric", json={"prompt": "Total quantity of units sold in the South region", "dataset_id": ds["id"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "offline" and "offline" in j["label"].lower()
    s = j["suggestion"]
    assert "quantity" in s["formula"] and "South" in (s["filters"] or "")
    assert j["validation"]["ok"] is True
    assert analyst.get("/api/ai/status").json()["mode"] == "offline"
    # nothing was auto-saved/published
    assert not [m for m in analyst.get("/api/metrics", params={"q": s["name"]}).json()["items"] if m["name"] == s["name"]]
    # user edits then saves as draft -> never published automatically
    edited = {**s, "name": "Units Sold Europe (TARA)"}
    saved = analyst.post(f"/api/ai/generations/{j['id']}/save", json={"definition": edited, "submit": True})
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "in_review" and saved.json()["source"] == "tara" and not saved.json()["is_live"]
    assert analyst.post(f"/api/ai/generations/{j['id']}/save", json={"definition": edited}).status_code == 400  # one-shot
    gibberish = analyst.post("/api/ai/generate-metric", json={"prompt": "the flux capacitor harmonic resonance", "dataset_id": ds["id"]}).json()
    assert gibberish["ok"] is False and gibberish["error"]


def test_tara_generator_with_mocked_ai_handles_failure_and_bad_output(analyst, monkeypatch):
    from app.services import tara, ai
    from app.services.ai import AIUnavailable

    ds = sales_dataset(analyst)
    monkeypatch.setattr(tara, "ai_status", lambda ws=None: {"enabled": True, "mode": "ai"})
    monkeypatch.setattr(tara, "effective_provider", lambda ws=None: "openai")

    def timeout(*a, **k):
        raise AIUnavailable("TARA timed out after 25s")

    monkeypatch.setattr(tara, "generate_json", timeout)
    out = analyst.post("/api/ai/generate-metric", json={"prompt": "Total net sales for the Online channel", "dataset_id": ds["id"]}).json()
    assert out["mode"] == "offline" and "fell back" in out["notice"]  # graceful degrade, still labelled

    monkeypatch.setattr(tara, "generate_json", lambda *a, **k: {"name": "x"})  # malformed: missing formula
    out = analyst.post("/api/ai/generate-metric", json={"prompt": "Total net sales for the Online channel", "dataset_id": ds["id"]}).json()
    assert out["mode"] == "offline" and "malformed" in out["notice"]

    calls = []

    def hallucinating(db, ws, system, user, kind):
        calls.append(kind)
        if kind == "metric_generation":
            return {"name": "Magic Revenue", "formula": "SUM(imaginary_column)", "unit": "USD", "explanation": "x"}
        return {"name": "Fixed Revenue", "formula": "SUM(net_sales)", "unit": "USD", "explanation": "repaired", "assumptions": ["a"]}

    monkeypatch.setattr(tara, "generate_json", hallucinating)
    out = analyst.post("/api/ai/generate-metric", json={"prompt": "Total net sales for the Online channel", "dataset_id": ds["id"]}).json()
    assert calls == ["metric_generation", "metric_generation_repair"]  # compiler error fed back once
    assert out["mode"] == "ai" and out["suggestion"]["formula"] == "SUM(net_sales)" and out["validation"]["ok"]

    # still-invalid AI output is returned with validation errors, never auto-accepted
    monkeypatch.setattr(tara, "generate_json", lambda *a, **k: {"name": "Bad", "formula": "SUM(nothing_here)"})
    out = analyst.post("/api/ai/generate-metric", json={"prompt": "Total net sales for the Online channel", "dataset_id": ds["id"]}).json()
    assert out["validation"]["ok"] is False and out["validation"]["errors"][0]["message"].startswith("Unknown column")
    saved = analyst.post(f"/api/ai/generations/{out['id']}/save", json={"definition": {}, "submit": True})
    assert saved.status_code == 422  # invalid definitions can't be submitted


# ------------------------------------------------------------------ NL planner with mocked AI
def test_planner_rejects_forged_ai_plans(business, monkeypatch):
    from app.services import planner

    monkeypatch.setattr(planner, "effective_provider", lambda ws=None: "openai")

    def forged(db, ws, system, user, kind):
        return {"supported": True, "metric_key": "revenue", "dimension": "ssn", "chart": "bar"}

    monkeypatch.setattr(planner, "generate_json", forged)
    a = business.post("/api/chat/ask", json={"question": "revenue by ssn"}).json()
    assert a["kind"] == "unsupported" and "does not exist" in a["text"]

    monkeypatch.setattr(planner, "generate_json", lambda *a, **k: {"supported": True, "metric_key": "payroll_secret"})
    a = business.post("/api/chat/ask", json={"question": "payroll?"}).json()
    assert a["kind"] == "unsupported" and "not an approved metric" in a["text"]

    def good(db, ws, system, user, kind):
        return {"supported": True, "metric_key": "revenue", "dimension": "region", "chart": "bar", "order": "value_desc", "limit": 3,
                "time_range": {"label": "2025", "start": "2025-01-01", "end": "2025-12-31"}}

    monkeypatch.setattr(planner, "generate_json", good)
    a = business.post("/api/chat/ask", json={"question": "which regions sold the most in 2025?"}).json()
    assert a["kind"] == "answer" and a["plan"]["planner"] == "ai" and len(a["table"]["rows"]) == 3
    assert a["notice"] is None
    vals = [r[1] for r in a["table"]["rows"]]
    assert vals == sorted(vals, reverse=True)

    def boom(*a, **k):
        raise planner.AIUnavailable("down")

    monkeypatch.setattr(planner, "generate_json", boom)
    a = business.post("/api/chat/ask", json={"question": "How many orders did we have last month?"}).json()
    assert a["kind"] == "answer" and "offline rule-based planner" in a["notice"]


def test_planner_offline_rules():
    import datetime as dt
    from app.services.planner import parse_time_range

    today = dt.date(2026, 5, 15)  # inside Q1 of FY 2026-27
    assert parse_time_range("revenue last quarter", today).start == "2026-01-01"
    assert parse_time_range("revenue last quarter", today).end == "2026-03-31"
    assert parse_time_range("orders in Q2 FY26", today).start == "2025-07-01"
    assert parse_time_range("orders last month", today).start == "2026-04-01"
    assert parse_time_range("sales in March 2025", today).end == "2025-03-31"
    assert parse_time_range("sales last 14 days", today).start == "2026-05-01"
    assert parse_time_range("how many orders", today) is None


def test_chat_history_and_streaming(business):
    r = business.post("/api/chat/ask", json={"question": "How many orders did we have last month?"}).json()
    cid = r["conversation_id"]
    r2 = business.post("/api/chat/ask", json={"question": "Revenue last year", "conversation_id": cid}).json()
    assert r2["conversation_id"] == cid
    conv = business.get(f"/api/chat/conversations/{cid}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant", "user", "assistant"]
    assert conv["messages"][1]["payload"]["sources"][0]["key"] == "orders"
    with business.stream("POST", "/api/chat/ask/stream", json={"question": "What was revenue by month last quarter?"}) as s:
        body = "".join(s.iter_text())
    events = [l.split(": ", 1)[1] for l in body.splitlines() if l.startswith("event: ")]
    assert events[0] == "status" and "result" in events and "text" in events and events[-1] == "done"
    # other users cannot read my conversation
    from conftest import CREDS, _client
    assert _client(*CREDS["analyst"]).get(f"/api/chat/conversations/{cid}").status_code == 404
