import pytest

from app.services.engine import QuerySpec, build_sql
from app.services.formula import Compiler, FormulaError, canonical_formula, extract_refs, parse_condition, parse_formula

SCHEMA = {"net_sales": "numeric", "refund_amount": "numeric", "quantity": "numeric", "region": "string", "order_id": "string", "order_date": "date", "flag": "bool"}


def compile_(text, resolver=None):
    return Compiler(SCHEMA, resolver).compile_formula(parse_formula(text))


def test_basic_compile_and_parameterization():
    r = compile_("SUM(net_sales) - SUM(refund_amount) WHERE region = 'EU' AND order_date >= '2025-01-01'")
    assert r.sql == '(SUM("net_sales") - SUM("refund_amount"))'
    assert [w.sql for w in r.where] == ['(("region" = ?) AND ("order_date" >= CAST(? AS DATE)))']
    assert r.where[0].params == ["EU", "2025-01-01"]
    assert r.columns == {"net_sales", "refund_amount", "region", "order_date"}


def test_division_is_zero_safe_and_functions():
    r = compile_("ROUND(SUM(net_sales) / COUNT_DISTINCT(order_id), 2)")
    assert "NULLIF" in r.sql and r.params == []
    r = compile_("SUMIF(net_sales, region IN ('EU','US')) / COUNT(*)")
    assert r.sql.count("?") == 2
    r = compile_("COUNTIF(refund_amount > 0) / COUNT(*) * 100")
    assert "CASE WHEN" in r.sql


def test_metric_reference_inlines_with_filter():
    def resolver(name):
        return (parse_formula("SUM(net_sales)"), parse_condition("region = 'EU'")) if name == "EuRev" else None

    r = compile_("[EuRev] / COUNT(*)", resolver)
    assert 'FILTER (WHERE ("region" = ?))' in r.sql and r.params == ["EU"] and r.metrics == ["EuRev"]
    with pytest.raises(FormulaError, match="Unknown or unpublished"):
        compile_("[Nope] + 1", resolver)


def test_circular_reference_detected():
    table = {"a": parse_formula("[B] + 1"), "b": parse_formula("[A] + 1")}
    with pytest.raises(FormulaError, match="Circular"):
        compile_("[A]", lambda n: (table[n.lower()], None))


@pytest.mark.parametrize(
    "bad,msg",
    [
        ("SUM(net_sales); DROP TABLE users", "Unexpected character ';'"),
        ("SUM(net_sales) -- comment", "Comments"),
        ("SUM(net_sales) /* x */", "Comments"),
        ("SUM(net_sales) WHERE 1=1; SELECT 1", "Unexpected character ';'"),
        ("read_csv('/etc/passwd')", "not allowed"),
        ("SUM(net_sales) UNION SELECT 1", "Expected"),
        ("(SELECT 1)", "Expected"),
        ("SUM(net_sales) WHERE region = 'a' OR 1=1 --", "Comments"),
        ("SUM(`net_sales`)", "Unexpected character"),
        ('SUM("net_sales")', "Unexpected character"),
        ("pg_sleep(10)", "not allowed"),
        ("SUM(net_sales) WHERE region LIKE 5", "Expected"),
        ("SUM(region)", "numeric"),
        ("SUM(nope)", "Unknown column"),
        ("net_sales", "aggregate"),
        ("SUM(net_sales) + net_sales", "mix"),
        ("SUM(SUM(net_sales))", "Nested aggregate"),
        ("SUM(net_sales) WHERE SUM(net_sales) > 1", "not allowed"),
        ("SUM(net_sales) WHERE region = 5", "Cannot compare"),
        ("SUM(net_sales) WHERE order_date > 'yesterday'", "valid date"),
        ("", "empty"),
        ("SUM(net_sales", "Expected"),
        ("SUM(net_sales) WHERE", "Unexpected"),
        ("ROUND(SUM(net_sales), 99)", "0-10"),
        ("[Metric", "Invalid metric reference"),
    ],
)
def test_injection_and_invalid_inputs_rejected(bad, msg):
    with pytest.raises(FormulaError) as e:
        compile_(bad)
    assert msg.lower() in e.value.message.lower(), e.value.message


def test_string_literals_are_never_inlined():
    evil = "x' OR '1'='1"
    r = compile_(f"SUM(net_sales) WHERE region = '{evil.replace(chr(39), chr(39) * 2)}'")
    assert evil in r.where[0].params
    assert "OR '1'='1" not in r.where[0].sql


def test_deep_nesting_and_length_limits():
    with pytest.raises(FormulaError):
        compile_("(" * 100 + "SUM(net_sales)" + ")" * 100)
    with pytest.raises(FormulaError, match="too long"):
        parse_formula("SUM(net_sales)" + " + 1" * 2000)


def test_canonical_equivalence():
    assert canonical_formula(parse_formula("sum(Net_Sales) + SUM(refund_amount)")) == canonical_formula(parse_formula("SUM(refund_amount)+SUM(net_sales)"))
    assert canonical_formula(parse_formula("SUM(a)/SUM(b)")) != canonical_formula(parse_formula("SUM(b)/SUM(a)"))
    assert extract_refs(parse_formula("[Revenue] / [Orders] + [Revenue]")) == ["Revenue", "Orders"]


def test_build_sql_dimensions_filters_and_limits(admin):
    from app.db import SessionLocal
    from app.models import Dataset
    from sqlalchemy import select

    with SessionLocal() as db:
        ds = db.scalar(select(Dataset).where(Dataset.name == "sales_transactions"))
        sql, params, meta = build_sql(
            ds,
            QuerySpec("SUM(net_sales)", dimensions=[{"column": "order_date", "grain": "month"}], time_range={"start": "2025-01-01", "end": "2025-12-31"},
                      where=[{"column": "region", "op": "in", "value": ["Europe", "Asia Pacific"]}], limit=999999),
        )
        assert sql.count("?") == len(params) == 4
        assert "date_trunc('month'" in sql and meta["limit"] <= 10000 and sql.endswith("LIMIT 10001")
        for evil in (
            QuerySpec("SUM(net_sales)", dimensions=[{"column": "region; DROP TABLE data"}]),
            QuerySpec("SUM(net_sales)", dimensions=[{"column": "region", "grain": "month"}]),
            QuerySpec("SUM(net_sales)", dimensions=[{"column": "order_date", "grain": "month'); --"}]),
            QuerySpec("SUM(net_sales)", where=[{"column": "region", "op": "=; DROP", "value": "x"}]),
            QuerySpec("SUM(net_sales)", where=[{"column": "nope", "op": "=", "value": "x"}]),
        ):
            with pytest.raises(FormulaError):
                build_sql(ds, evil)


def test_execute_endpoint_rejects_injection(analyst):
    from conftest import sales_dataset

    ds = sales_dataset(analyst)
    for bad in ("SUM(net_sales); DROP TABLE x", "SELECT * FROM data", "SUM(net_sales) WHERE region = 'a' --"):
        r = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": bad})
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_formula", bad
    ok = analyst.post("/api/execution/run", json={"dataset_id": ds["id"], "formula": "SUM(net_sales)", "dimensions": [{"column": "region"}], "order": "value_desc", "limit": 3})
    assert ok.status_code == 200 and ok.json()["row_count"] == 3 and ok.json()["truncated"] is True
    hist = analyst.get("/api/execution/history", params={"ok": False}).json()
    assert hist["total"] >= 3
