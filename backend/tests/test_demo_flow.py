"""End-to-end backend walkthrough of the headline scenario: Finance Revenue vs official Revenue."""
import datetime as dt

from conftest import find_metric, sales_dataset


def test_revenue_conflict_end_to_end(analyst, reviewer, admin, business):
    # 1. detect
    r = analyst.post("/api/conflicts/detect")
    assert r.status_code == 200, r.text
    assert r.json()["created"] >= 4  # Finance Revenue, Marketing (GST-inclusive) Revenue, Orders, Gross Margin %
    items = admin.get("/api/conflicts", params={"status": "active"}).json()["items"]
    rev_conflicts = [c for c in items if c["metric_key"] == "revenue"]
    assert {c["metric_b"]["department"] for c in rev_conflicts} == {"Finance", "Marketing"}
    rc = next(c for c in rev_conflicts if c["metric_b"]["department"] == "Finance")
    assert rc["severity"] in ("high", "critical")
    assert any(d["type"] == "formula" for d in rc["differences"])
    assert rc["metric_a"]["is_live"] and rc["metric_b"]["department"] == "Finance"

    detail = admin.get(f"/api/conflicts/{rc['id']}").json()
    assert any(s["op"] != "equal" for s in detail["formula_diff"])

    # workflow must be strictly ordered
    assert reviewer.post(f"/api/conflicts/{rc['id']}/resolve", json={"action": "accept_both", "note": "too early"}).status_code == 409
    users = admin.get("/api/users").json()["items"]
    rev_user = next(u for u in users if u["role"] == "reviewer")
    assert business.post(f"/api/conflicts/{rc['id']}/assign", json={"assignee_id": rev_user["id"]}).status_code == 403
    assert reviewer.post(f"/api/conflicts/{rc['id']}/assign", json={"assignee_id": rev_user["id"], "note": "please review"}).status_code == 200
    assert reviewer.post(f"/api/conflicts/{rc['id']}/review", json={}).json()["status"] == "in_review"
    assert reviewer.post(f"/api/conflicts/{rc['id']}/approve", json={"note": "rename is right"}).json()["status"] == "approved"
    res = reviewer.post(f"/api/conflicts/{rc['id']}/resolve", json={"action": "rename_variant", "note": "Finance uses refunds-adjusted revenue", "new_name": "Net Revenue (after refunds)"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "resolved"

    # new version recorded for the renamed variant; published Revenue untouched
    ren = find_metric(admin, "Net Revenue (after refunds)")
    assert ren["version"] >= 2 and ren["key"] == "net_revenue_after_refunds"
    vers = admin.get(f"/api/metrics/{ren['id']}/versions").json()["items"]
    assert vers[0]["change_summary"].startswith("Renamed")
    official = find_metric(admin, "Revenue", "Sales", "published")
    assert official["is_live"]

    # history shows the full audit trail
    ev = admin.get(f"/api/conflicts/{rc['id']}/events").json()["items"]
    assert [e["action"] for e in ev][-1] == "conflict.resolve"
    assert {"conflict.detect", "conflict.assign", "conflict.review", "conflict.approve"} <= {e["action"] for e in ev}

    # re-detect: resolved pair no longer produces a revenue conflict
    analyst.post("/api/conflicts/detect")
    active = admin.get("/api/conflicts", params={"status": "active"}).json()["items"]
    assert not [c for c in active if c["metric_b"]["department"] == "Finance" and c["metric_key"] == "revenue"]
    assert [c for c in active if c["metric_b"]["department"] == "Marketing"]  # the GST-inclusive Revenue conflict is still open


def test_formula_lab_and_chat_agree(analyst, business):
    ds = sales_dataset(analyst)
    v = analyst.post("/api/validation/formula", json={"dataset_id": ds["id"], "formula": "[Revenue] - SUM(refund_amount)"})
    assert v.status_code == 200 and v.json()["ok"], v.text
    run = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "[Revenue] - SUM(refund_amount)"})
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["scanned_rows"] >= 50000 and body["duration_ms"] >= 0 and body["rows"][0][0] > 0
    assert "?" not in body["sql"] or body["params"] is not None

    # business user can ask TARA but cannot use the lab
    assert business.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "SUM(net_sales)"}).status_code == 403
    ans = business.post("/api/chat/ask", json={"question": "What was revenue by month last quarter?"})
    assert ans.status_code == 200, ans.text
    a = ans.json()
    assert a["kind"] == "answer", a
    assert a["applied"]["grain"] == "month" and "last quarter" in a["applied"]["time_range"]["label"]
    assert len(a["table"]["rows"]) == 3
    assert a["sources"][0]["key"] == "revenue" and a["chart"]["type"] == "line"
    # numbers must equal an independent computation through the lab
    tr = a["applied"]["time_range"]
    direct = analyst.post("/api/execution/run", json={
        "dataset_id": ds["id"], "formula": "SUM(net_sales)", "time_range": {"column": "order_date", "start": tr["start"], "end": tr["end"]},
    }).json()["rows"][0][0]
    assert abs(sum(r[1] for r in a["table"]["rows"]) - direct) < 0.01

    # no fabrication
    nope = business.post("/api/chat/ask", json={"question": "What is the weather forecast for Paris?"}).json()
    assert nope["kind"] == "unsupported" and "table" not in nope
    bad = business.post("/api/chat/ask", json={"question": "revenue by weather"}).json()
    assert bad["kind"] == "unsupported" and "no matching column" in bad["text"]


def test_dashboard_templates_render(analyst):
    r = analyst.post("/api/dashboards/from-template", json={"template": "operations", "name": "Ops test"})
    assert r.status_code == 201, r.text
    d = r.json()
    data = analyst.post(f"/api/dashboards/{d['id']}/data", json={"filters": {"range": "last_90_days"}}).json()
    assert data["widgets"] and all(w["ok"] for w in data["widgets"].values()), data
    kpi = next(w for w in d["widgets"] if w["type"] == "kpi")
    assert data["widgets"][kpi["id"]]["rows"][0][-1] is not None
    assert analyst.delete(f"/api/dashboards/{d['id']}").status_code == 200


def test_evaluation_and_reports(analyst, admin):
    r = analyst.post("/api/evaluation/run")
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    ca = res["conflict_detection"]
    assert ca["automated"]["precision"] >= 0.9 and ca["automated"]["recall"] >= 0.9
    assert ca["naive_manual"]["precision"] < ca["automated"]["precision"]
    assert res["dashboard_load"]["dashboards"] >= 1 and res["query_latency"]["benchmark_queries"] >= 8
    for fmt, magic in (("csv", b"Name"), ("xlsx", b"PK"), ("pdf", b"%PDF")):
        for kind in ("metrics", "conflicts", "evaluation"):
            rr = admin.get(f"/api/reports/{kind}", params={"format": fmt})
            assert rr.status_code == 200, (kind, fmt, rr.text[:200])
            assert magic in rr.content[:200] or fmt == "csv"
    dash = admin.get("/api/dashboards").json()["items"][0]
    assert admin.get("/api/reports/dashboard", params={"format": "csv", "dashboard_id": dash["id"]}).status_code == 200
