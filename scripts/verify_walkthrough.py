"""Re-runs the demonstration walkthrough against a RUNNING back end (default http://127.0.0.1:8000) and records the evidence.

Checks: all six demo logins, role-based access, the Revenue conflict workflow, Formula Lab and an injection attempt, the five suggested
Indian questions (INR / lakh formatting, no dollar amounts), a refused question, dashboards, audit log, workspace isolation.
Run after `scripts/reset-demo.sh`.  Usage: python scripts/verify_walkthrough.py [base_url]"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
H = {"X-Requested-With": "IntelliMetrics"}
ACCOUNTS = {
    "admin": ("admin@intellimetrics.demo", "Admin@12345"), "analyst": ("analyst@intellimetrics.demo", "Analyst@12345"),
    "business": ("business@intellimetrics.demo", "Business@12345"), "reviewer": ("reviewer@intellimetrics.demo", "Reviewer@12345"),
    "sagar_admin": ("admin@sagarfoods.demo", "Admin@12345"), "sagar_analyst": ("analyst@sagarfoods.demo", "Analyst@12345"),
}
results: list[dict] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def client(who: str) -> httpx.Client:
    c = httpx.Client(base_url=BASE + "/api", headers=H, timeout=60)
    r = c.post("/auth/login", json={"email": ACCOUNTS[who][0], "password": ACCOUNTS[who][1]})
    check(f"login {who}", r.status_code == 200, f"HTTP {r.status_code}" + (f", role={r.json()['user']['role']}, workspace={r.json()['user']['workspace']['name']}" if r.status_code == 200 else ""))
    return c


def main():
    c = {w: client(w) for w in ACCOUNTS}
    me = {w: c[w].get("/auth/me").json()["user"] for w in ACCOUNTS}
    check("workspaces are the two Indian companies", {me["admin"]["workspace"]["name"], me["sagar_admin"]["workspace"]["name"]} == {"Bharat Retail Pvt Ltd", "Sagar Foods & Beverages Ltd"})

    # role access
    check("business user cannot open Formula Lab execution (403)", c["business"].post("/execution/run", json={"dataset_id": "x", "formula": "SUM(net_sales)"}).status_code in (403, 404, 422) and c["business"].post("/execution/run", json={"dataset_id": "x", "formula": "SUM(net_sales)"}).status_code == 403)
    check("business user cannot run conflict detection (403)", c["business"].post("/conflicts/detect").status_code == 403)
    check("business user cannot read the audit log (403)", c["business"].get("/admin/audit-logs").status_code == 403)

    # conflict workflow as reviewer
    rv = c["reviewer"]
    det = rv.post("/conflicts/detect")
    check("conflict detection runs", det.status_code == 200, str(det.json())[:100])
    items = rv.get("/conflicts", params={"page_size": 50}).json()["items"]
    fin = next((x for x in items if x["metric_b"]["department"] == "Finance"), None)
    mkt = next((x for x in items if x["metric_b"]["department"] == "Marketing" and x["metric_key"] == "revenue"), None)
    check("Finance Revenue conflict found", fin is not None)
    check("GST-inclusive Marketing Revenue conflict found", mkt is not None)
    if fin:
        cid = fin["id"]
        steps = [("assign", {"assignee_id": me["reviewer"]["id"], "note": "please review"}), ("review", {}), ("approve", {"note": "rename is right"}), ("resolve", {"action": "rename_variant", "new_name": "Net Revenue (verification)", "note": "Finance reports net of refunds"})]
        ok = True
        for name, body in steps:
            r = rv.post(f"/conflicts/{cid}/{name}", json=body)
            ok = ok and r.status_code == 200
            if r.status_code != 200:
                check(f"conflict step {name}", False, f"HTTP {r.status_code} {r.text[:120]}")
        check("conflict assign, review, approve, resolve", ok)
        got = rv.get("/metrics", params={"q": "Net Revenue (verification)"}).json()["items"]
        check("renamed metric is version 2", bool(got) and got[0]["version"] == 2, str([g.get("version") for g in got]))

    # formula lab
    an = c["analyst"]
    ds = next(d for d in an.get("/datasets", params={"page_size": 50}).json()["items"] if d["name"] == "sales_transactions")
    ex = an.post("/execution/run", json={"dataset_id": ds["id"], "formula": "[Revenue] - SUM(refund_amount)", "dimension": "state", "limit": 10})
    check("Formula Lab runs Revenue minus refunds by state", ex.status_code == 200 and ex.json()["rows"] and ex.json()["scanned_rows"] >= 50000, f"HTTP {ex.status_code}")
    bad = an.post("/execution/run", json={"dataset_id": ds["id"], "formula": "SUM(net_sales); DROP TABLE users"})
    check("injection attempt rejected (422)", bad.status_code == 422, f"HTTP {bad.status_code}")
    check("users table intact after the attempt", c["admin"].get("/users").status_code == 200)

    # Ask TARA, as the business user
    bu = c["business"]
    qs = bu.get("/chat/suggestions").json()
    qlist = qs["items"]
    check("Indian suggested questions offered (first five are the headline questions)", len(qlist) >= 5 and "Diwali" in " ".join(qlist[:5]) and "UPI vs COD" in " ".join(qlist[:5]), str(len(qlist)))
    text_all = []
    for q in qlist:
        question = q if isinstance(q, str) else q.get("question", q.get("text"))
        r = bu.post("/chat/ask", json={"question": question})
        j = r.json()
        blob = json.dumps(j, ensure_ascii=False)
        text_all.append(blob)
        rows = (j.get("table") or {}).get("rows") or []
        check(f"ask: {question[:60]}", r.status_code == 200 and j.get("kind") == "answer" and (("₹" in blob) or re.search(r"orders|margin", question, re.I) is not None) and len(rows) > 0, f"HTTP {r.status_code}, kind={j.get('kind')}, rows={len(rows)}")
    joined = " ".join(text_all)
    check("no dollar amounts in any answer", not re.search(r"\$\s?\d", joined))
    check("lakh/crore grouping present (e.g. 12,34,567 or Cr/L)", bool(re.search(r"\d{1,2},\d{2},\d{3}", joined)) or bool(re.search(r"₹[\d.]+ (Cr|L)", joined)))
    ref = bu.post("/chat/ask", json={"question": "What is the weather in Delhi?"}).json()
    check("off-topic question is refused, not answered", "couldn't match" in json.dumps(ref).lower() or "could not" in json.dumps(ref).lower() or "cannot" in json.dumps(ref).lower(), json.dumps(ref)[:100])

    # dashboards
    dash = bu.get("/dashboards").json()["items"]
    sales = next((d for d in dash if d["name"] == "Sales Overview"), None)
    check("Sales Overview dashboard exists", sales is not None)
    if sales:
        w = bu.post(f"/dashboards/{sales['id']}/data", json={"filters": {"range": "this_fy"}}).json()
        widgets = w.get("widgets") or {}
        check("all dashboard widgets load", bool(widgets) and all(x.get("ok") for x in widgets.values()), f"{len(widgets)} widgets")

    # audit + isolation
    au = c["admin"].get("/admin/audit-logs", params={"page_size": 20}).json()
    check("audit log records the actions", au.get("total", len(au.get("items", []))) > 5, str(au.get("total")))
    sd = c["sagar_admin"]
    sm = sd.get("/metrics", params={"page_size": 100}).json()["items"]
    sdn = [d["name"] for d in sd.get("/datasets", params={"page_size": 50}).json()["items"]]
    check("second workspace sees only its own datasets", "sales_transactions" not in sdn and "distributor_dispatches" in sdn, str(sdn))
    check("second workspace sees none of Bharat Retail's metrics", all("Finance Revenue" not in m["name"] and "Marketing Revenue" not in m["name"] for m in sm), f"{len(sm)} metrics")
    check("cross-workspace dataset access returns 404", sd.get(f"/datasets/{ds['id']}").status_code == 404)

    summary = {"base": BASE, "passed": sum(r["ok"] for r in results), "total": len(results), "results": results}
    out = Path(__file__).resolve().parents[1] / "docs" / "data" / "walkthrough_verification.json"
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{summary['passed']}/{summary['total']} checks passed -> {out}")
    sys.exit(0 if summary["passed"] == summary["total"] else 1)


if __name__ == "__main__":
    main()
