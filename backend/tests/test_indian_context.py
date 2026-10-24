"""Indian-context behaviour: INR en-IN formatting, April-March fiscal calendar, IST, festival-aware synthetic data, Indian TARA questions."""
import datetime as dt
import re

import pytest

from app.services.calendar_in import (
    fmt_date, fq_bounds, fq_label, fq_of, fy_bounds, fy_label, fy_start_year, last_completed_fq, latest_festival_window, today_ist, to_ist,
)
from app.services.engine import window_range
from app.services.formatting import compact_in, format_value, group_indian, inr, number_en_in
from app.services.planner import TimeRange, compose_compare_text, parse_time_range, previous_period, QueryPlan
from conftest import sales_dataset


# ------------------------------------------------------------------ formatting
@pytest.mark.parametrize("raw,expected", [("1", "1"), ("999", "999"), ("1000", "1,000"), ("12345", "12,345"), ("123456", "1,23,456"), ("1245300", "12,45,300"), ("123456789", "12,34,56,789")])
def test_lakh_crore_grouping(raw, expected):
    assert group_indian(raw) == expected


def test_inr_and_compact_formats():
    assert inr(1245300) == "₹12,45,300"
    assert inr(45.5) == "₹45.50"
    assert inr(-250000.4) == "-₹2,50,000"
    assert number_en_in(1234567.891, 2) == "12,34,567.89"
    assert compact_in(12000000, currency=True) == "₹1.2 Cr"
    assert compact_in(4500000, currency=True) == "₹45 L"
    assert compact_in(12500) == "12.5 K"
    assert format_value(2500000, "INR") == "₹25,00,000"
    assert format_value(35.04, "percent") == "35.0%"
    assert format_value(1013, "count") == "1,013"
    assert format_value(None, "INR") == "n/a"


# ------------------------------------------------------------------ fiscal calendar (1 Apr - 31 Mar)
def test_fiscal_quarters():
    assert fy_start_year(dt.date(2026, 3, 31)) == 2025 and fy_start_year(dt.date(2026, 4, 1)) == 2026
    assert fy_label(2025) == "FY 2025-26"
    assert fy_bounds(2025) == (dt.date(2025, 4, 1), dt.date(2026, 3, 31))
    assert fq_bounds(2025, 1) == (dt.date(2025, 4, 1), dt.date(2025, 6, 30))
    assert fq_bounds(2025, 2) == (dt.date(2025, 7, 1), dt.date(2025, 9, 30))
    assert fq_bounds(2025, 3) == (dt.date(2025, 10, 1), dt.date(2025, 12, 31))
    assert fq_bounds(2025, 4) == (dt.date(2026, 1, 1), dt.date(2026, 3, 31))
    assert fq_of(dt.date(2026, 1, 15)) == (2025, 4) and fq_of(dt.date(2025, 4, 1)) == (2025, 1) and fq_of(dt.date(2025, 11, 5)) == (2025, 3)
    assert fq_label(2025, 3) == "Q3 FY 2025-26"
    assert last_completed_fq(dt.date(2026, 10, 24)) == (2026, 2)
    assert last_completed_fq(dt.date(2026, 4, 10)) == (2025, 4)


def test_date_display_and_ist():
    assert fmt_date(dt.date(2026, 3, 5)) == "05-Mar-2026"
    assert fmt_date("2025-10-20") == "20-Oct-2025"
    # 20:00 UTC on 31 Dec is already 01:30 on 1 Jan in IST (UTC+05:30)
    assert to_ist(dt.datetime(2025, 12, 31, 20, 0)).strftime("%d-%b-%Y %H:%M") == "01-Jan-2026 01:30"
    assert today_ist().year >= 2026


def test_metric_window_ytd_is_financial_year_to_date():
    assert window_range("ytd", dt.date(2026, 2, 10)) == ("2025-04-01", "2026-02-10")
    assert window_range("ytd", dt.date(2026, 4, 2)) == ("2026-04-01", "2026-04-02")


def test_festival_windows():
    w = latest_festival_window("diwali", dt.date(2026, 10, 24))  # Diwali 2026 (8-Nov) season has not started -> use 2025
    assert w == (dt.date(2025, 10, 6), dt.date(2025, 10, 25))
    assert latest_festival_window("diwali", dt.date(2026, 11, 1))[0] == dt.date(2026, 10, 25)


# ------------------------------------------------------------------ TARA time-range understanding
TODAY = dt.date(2026, 10, 24)  # Q3 of FY 2026-27


@pytest.mark.parametrize(
    "question,start,end",
    [
        ("revenue in the last quarter", "2026-07-01", "2026-09-30"),
        ("revenue this quarter", "2026-10-01", "2026-10-24"),
        ("net revenue in the last quarter of this financial year", "2026-07-01", "2026-09-30"),
        ("sales this financial year", "2026-04-01", "2026-10-24"),
        ("sales this year", "2026-04-01", "2026-10-24"),
        ("sales last financial year", "2025-04-01", "2026-03-31"),
        ("sales in FY 2025-26", "2025-04-01", "2026-03-31"),
        ("sales in FY26", "2025-04-01", "2026-03-31"),
        ("sales in fy25-26", "2025-04-01", "2026-03-31"),
        ("orders in Q3 FY26", "2025-10-01", "2025-12-31"),
        ("orders in the first quarter of last financial year", "2025-04-01", "2025-06-30"),
        ("orders last month", "2026-09-01", "2026-09-30"),
        ("sales in March 2025", "2025-03-01", "2025-03-31"),
        ("sales last 14 days", "2026-10-10", "2026-10-24"),
    ],
)
def test_fiscal_time_ranges(question, start, end):
    tr = parse_time_range(question, TODAY)
    assert tr is not None, question
    assert (tr.start, tr.end) == (start, end), tr.label


def test_last_quarter_when_current_fy_has_no_completed_quarter():
    tr = parse_time_range("revenue in the last quarter of this financial year", dt.date(2026, 5, 15))
    assert (tr.start, tr.end) == ("2026-01-01", "2026-03-31")  # falls back to Q4 of the previous FY


def test_previous_period_is_fiscal_quarter_before_the_festival_quarter():
    diwali = TimeRange(label="Diwali season", start="2025-10-06", end="2025-10-25")
    prev = previous_period(diwali, TODAY)
    assert (prev.start, prev.end) == ("2025-07-01", "2025-09-30")


def test_compare_text_flags_unequal_period_lengths():
    plan = QueryPlan(time_range=TimeRange(label="A", start="2025-10-06", end="2025-10-25"), compare_range=TimeRange(label="B", start="2025-07-01", end="2025-09-30"))
    t = compose_compare_text(plan, "Revenue", "INR", 7364558.0, 19667533.0)
    assert "₹73,64,558" in t and "differ in length (20 vs 92 days)" in t and "per day" in t


# ------------------------------------------------------------------ synthetic Indian dataset
def test_dataset_is_indian_and_large(analyst):
    ds = sales_dataset(analyst)
    d = analyst.get(f"/api/datasets/{ds['id']}").json()
    assert d["row_count"] >= 50000 and "Demonstration data (synthetic)" in d["description"]
    cols = {c["name"] for c in d["schema"]}
    assert {"gross_sales", "discount", "gst_rate", "gst_amount", "net_sales", "net_amount", "payment_method", "channel", "region", "state", "customer_name", "refund_reason"} <= cols
    prof = {c["name"]: c for c in d["profile"]["columns"]}
    pays = {t["value"] for t in prof["payment_method"]["top_values"]}
    assert pays == {"UPI", "Credit/Debit Card", "Net Banking", "COD", "Wallet"}
    assert {t["value"] for t in prof["region"]["top_values"]} == {"North", "South", "East", "West", "Central"}
    assert {t["value"] for t in prof["channel"]["top_values"]} == {"Online", "Store", "Marketplace"}
    states = {t["value"] for t in prof["state"]["top_values"]}
    assert {"Maharashtra", "Delhi", "Karnataka", "Telangana", "Tamil Nadu", "Andhra Pradesh", "West Bengal", "Gujarat", "Uttar Pradesh"} <= states
    cats = {t["value"] for t in prof["category"]["top_values"]}
    assert {"Groceries & Staples", "Packaged Foods", "Beverages", "Personal Care", "Home Appliances", "Mobiles & Electronics", "Apparel", "Ethnic Wear"} == cats


def test_gst_slabs_and_amount_arithmetic(analyst):
    ds = sales_dataset(analyst)
    run = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "COUNT(*)", "dimensions": [{"column": "gst_rate"}] if False else []})
    assert run.status_code == 200
    r = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "SUM(net_sales)", "dimensions": [{"column": "category"}], "limit": 20})
    assert r.status_code == 200
    # invoice value = taxable value + GST for the whole table (to the paisa)
    t = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "SUM(net_amount) - SUM(net_sales) - SUM(gst_amount)"}).json()
    assert abs(t["rows"][0][0]) < 5.0
    # GST appears only in the five official slabs
    prev = analyst.get(f"/api/datasets/{ds['id']}/preview", params={"page_size": 200}).json()
    idx = prev["columns"].index("gst_rate")
    assert {row[idx] for row in prev["rows"]} <= {0, 5, 12, 18, 28}


def test_customers_have_valid_indian_formats(analyst):
    ds = next(d for d in analyst.get("/api/datasets", params={"page_size": 50}).json()["items"] if d["name"] == "customers")
    prev = analyst.get(f"/api/datasets/{ds['id']}/preview", params={"page_size": 200}).json()
    col = {c: i for i, c in enumerate(prev["columns"])}
    for row in prev["rows"]:
        assert re.fullmatch(r"[1-9]\d{5}", row[col["pin_code"]])
        assert row[col["mobile"]].startswith("+91 90000 ")  # non-working demo series
        assert row[col["email"]].endswith("@example.com")
    assert len({r[col["customer_name"]] for r in prev["rows"]}) == len(prev["rows"])


def test_festive_seasonality_is_present(analyst):
    ds = sales_dataset(analyst)

    def daily(start, end, days):
        r = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "SUM(net_sales)", "time_range": {"column": "order_date", "start": start, "end": end}}).json()
        return r["rows"][0][0] / days

    diwali = daily("2025-10-06", "2025-10-25", 20)
    prev_q = daily("2025-07-01", "2025-09-30", 92)
    assert diwali > 1.3 * prev_q  # the Diwali season runs well above the preceding quarter's daily run-rate


def test_cod_has_higher_return_rate_than_upi(analyst):
    ds = sales_dataset(analyst)
    r = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "COUNTIF(refund_amount > 0) / COUNT(*) * 100", "dimensions": [{"column": "payment_method"}]}).json()
    rates = {row[0]: row[1] for row in r["rows"]}
    assert rates["COD"] > rates["UPI"] * 1.5


# ------------------------------------------------------------------ TARA answers to the Indian suggested questions
SUGGESTED = [
    "What was net revenue by month in the last quarter of this financial year?",
    "Which 5 states had the highest sales this year?",
    "Compare Diwali-season sales with the previous quarter",
    "What is the UPI vs COD split by region?",
    "Top 10 customers by revenue",
]


def test_suggested_questions_come_from_the_api(business):
    items = business.get("/api/chat/suggestions").json()["items"]
    assert items[:5] == SUGGESTED


@pytest.mark.parametrize("question", SUGGESTED)
def test_each_suggested_question_returns_real_data(business, question):
    a = business.post("/api/chat/ask", json={"question": question}).json()
    assert a["kind"] == "answer", a["text"]
    assert a["table"]["rows"] and a["sources"]
    assert "₹" in a["text"]  # INR
    assert not re.search(r"\$\d", a["text"])


def test_net_revenue_by_month_matches_direct_query(business, analyst):
    a = business.post("/api/chat/ask", json={"question": SUGGESTED[0]}).json()
    assert len(a["table"]["rows"]) == 3 and a["applied"]["grain"] == "month"
    tr = a["applied"]["time_range"]
    assert tr["start"] == "2026-07-01" and tr["end"] == "2026-09-30" and "Q2 FY 2026-27" in tr["label"]
    direct = analyst.post("/api/execution/run", json={"dataset_id": sales_dataset(analyst)["id"], "formula": "SUM(net_sales)", "time_range": {"column": "order_date", "start": tr["start"], "end": tr["end"]}}).json()["rows"][0][0]
    assert abs(sum(r[1] for r in a["table"]["rows"]) - direct) < 0.01


def test_top_states_customers_and_split(business):
    st = business.post("/api/chat/ask", json={"question": SUGGESTED[1]}).json()
    assert st["applied"]["dimension"] == "state" and len(st["table"]["rows"]) == 5
    vals = [r[1] for r in st["table"]["rows"]]
    assert vals == sorted(vals, reverse=True)
    cu = business.post("/api/chat/ask", json={"question": SUGGESTED[4]}).json()
    assert cu["applied"]["dimension"] == "customer_name" and len(cu["table"]["rows"]) == 10
    sp = business.post("/api/chat/ask", json={"question": SUGGESTED[3]}).json()
    assert sp["applied"]["dimension"] == "region" and sp["applied"]["dimension2"] == "payment_method"
    assert sp["table"]["columns"][-1] == "share_pct" and sp["chart"]["type"] == "grouped"
    by_region = {}
    for region, method, _v, share in sp["table"]["rows"]:
        assert method in ("UPI", "COD")
        by_region[region] = by_region.get(region, 0) + share
    assert all(abs(total - 100) < 0.5 for total in by_region.values())
    assert "did not name a metric" in sp["text"]  # the Revenue default is disclosed


def test_diwali_comparison_is_data_backed_and_labelled(business):
    a = business.post("/api/chat/ask", json={"question": SUGGESTED[2]}).json()
    ap = a["applied"]
    assert "Diwali season" in ap["time_range"]["label"] and "previous quarter" in ap["compare_range"]["label"]
    assert ap["compare_range"]["start"] == "2025-07-01" and ap["compare_range"]["end"] == "2025-09-30"
    assert len(a["table"]["rows"]) == 2 and "per day" in a["text"]


# ------------------------------------------------------------------ exports
def test_exports_use_inr_and_indian_dates(admin):
    dash = next(d for d in admin.get("/api/dashboards").json()["items"] if d["name"] == "Sales Overview")
    csv_body = admin.get("/api/reports/dashboard", params={"format": "csv", "dashboard_id": dash["id"]}).content.decode("utf-8-sig")
    assert "Formatted value" in csv_body and "₹" in csv_body
    assert re.search(r"₹\d{1,2},\d{2},\d{3}", csv_body)  # lakh/crore grouping
    metrics_csv = admin.get("/api/reports/metrics", params={"format": "csv"}).content.decode("utf-8-sig")
    assert re.search(r"\d{2}-[A-Z][a-z]{2}-\d{4} \d{2}:\d{2} IST", metrics_csv)


def test_gst_conflict_is_detected_with_marketing_variant(analyst):
    analyst.post("/api/conflicts/detect")
    items = analyst.get("/api/conflicts", params={"page_size": 50}).json()["items"]
    gst = next(c for c in items if c["metric_b"]["department"] == "Marketing" and c["metric_key"] == "revenue")
    assert any(d["type"] == "formula" for d in gst["differences"])
    assert "net_amount" in gst["metric_b"]["formula"]
