"""TARA: grounded metric generator. AI output is parsed into Pydantic models, validated by the formula compiler,
and never saved/published/executed automatically. Deterministic offline mode when no AI key is configured."""
from __future__ import annotations

import json
import re
import time

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AIGeneration, Dataset, Metric, User, Workspace
from .ai import AIUnavailable, ai_status, effective_provider, generate_json
from .metrics import validate_definition

DEPARTMENTS = ["Sales", "Finance", "Operations", "Marketing", "Product", "Customer Success"]


class GeneratedMetric(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    business_definition: str = ""
    formula: str = Field(min_length=3, max_length=2000)
    filters: str | None = None
    aggregation: str | None = None
    unit: str | None = None
    department: str | None = None
    category: str | None = None
    date_column: str | None = None
    time_window: str = "all_time"
    explanation: str = ""
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("filters", "aggregation", "unit", "department", "category", "date_column", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return None if v in ("", "null", "None") else v

    @field_validator("assumptions", mode="before")
    @classmethod
    def _assump(cls, v):
        if v is None:
            return []
        return [str(x) for x in v] if isinstance(v, list) else [str(v)]


SYSTEM = """You are TARA, the metric-definition assistant inside IntelliMetrics AI.
You turn a plain-English description into ONE governed metric definition for a semantic layer.
RULES:
- Use ONLY columns that exist in the provided dataset schema. Never invent columns.
- Write `formula` in the restricted grammar: aggregates SUM, AVG, MIN, MAX, COUNT, COUNT_DISTINCT, MEDIAN, STDDEV, SUMIF(expr, cond), COUNTIF(cond), AVGIF(expr, cond); scalar ABS, ROUND, COALESCE, IF, NULLIF, UPPER, LOWER, YEAR, MONTH; arithmetic + - * /; reference other published metrics as [Metric Name]. NO raw SQL, no semicolons, no subqueries.
- Put row-level conditions in `filters` as a boolean expression (e.g. region = 'EU' AND channel <> 'Wholesale'); dates as DATE '2025-01-01' or '2025-01-01'.
- Prefer reusing existing metrics via [Name] when the described metric is derived from them.
- If an existing metric already matches, say so in `explanation` and still return a definition.
Return ONLY a JSON object with keys: name, description, business_definition, formula, filters, aggregation, unit, department, category, date_column, time_window (one of all_time, ytd, mtd, last_12_months, last_90_days, last_30_days), explanation, assumptions (array of strings)."""


def schema_context(ds: Dataset) -> list[dict]:
    prof = {c["name"]: c for c in (ds.profile or {}).get("columns", [])}
    out = []
    for c in ds.schema_json:
        p = prof.get(c["name"], {})
        e = {"name": c["name"], "type": c["category"]}
        if p.get("top_values"):
            e["sample_values"] = [t["value"] for t in p["top_values"][:6]]
        if c["category"] == "numeric" and p.get("min") is not None:
            e["range"] = [p["min"], p["max"]]
        out.append(e)
    return out


def catalog_context(db: Session, ws_id: str, limit: int = 40) -> list[dict]:
    ms = db.scalars(select(Metric).where(Metric.workspace_id == ws_id, Metric.status != "deprecated").order_by(Metric.updated_at.desc()).limit(limit)).all()
    return [{"name": m.name, "key": m.key, "formula": m.formula, "unit": m.unit, "status": m.status, "department": m.department} for m in ms]


# ----------------------------------------------------------------------------- offline deterministic generator
STOP = set("the a an of for per by in on to and or is are was were what how many much total our my metric measure calculate number".split())


def _tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP]


def _stem(t: str) -> str:
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


def offline_generate(prompt: str, ds: Dataset, catalog: list[dict]) -> GeneratedMetric:
    p = prompt.lower()
    toks = {_stem(t) for t in _tokens(prompt)}
    cols = ds.schema_json
    prof = {c["name"]: c for c in (ds.profile or {}).get("columns", [])}

    def score(col: dict) -> int:
        parts = {_stem(x) for x in re.split(r"_", col["name"].lower())}
        return len(parts & toks) * 2 + (1 if col["name"].lower() in p else 0)

    numeric = [c for c in cols if c["category"] == "numeric"]
    best_num = max(numeric, key=score, default=None) if numeric else None
    if best_num is not None and score(best_num) == 0:
        best_num = None
    id_cols = [c for c in cols if c["name"].endswith("_id")]
    best_id = max(id_cols, key=score, default=None)
    if best_id is not None and score(best_id) == 0:
        best_id = None

    wants_avg = bool(re.search(r"\b(average|avg|mean|per order|typical)\b", p))
    wants_distinct = bool(re.search(r"\b(distinct|unique|different)\b", p))
    wants_count = bool(re.search(r"\b(count|number of|how many|# of)\b", p)) or wants_distinct
    ratio = re.search(r"\b(rate|ratio|percent|percentage|margin|%)\b", p)

    assumptions: list[str] = ["Generated by TARA offline deterministic mode (keyword matching against the dataset schema)."]
    name = " ".join(w.capitalize() for w in re.findall(r"[A-Za-z0-9]+", prompt)[:6]) or "New Metric"
    unit = None
    existing = next((c for c in catalog if _stem(c["name"].lower()) in p or c["key"].replace("_", " ") in p), None)

    if ratio and "margin" in p and any(c["name"] in ("cost", "net_sales") for c in cols):
        formula = "(SUM(net_sales) - SUM(cost)) / SUM(net_sales) * 100"
        unit, name = "percent", "Gross Margin %"
        assumptions.append("Margin interpreted as (net sales - cost) / net sales.")
    elif wants_count and best_id is not None:
        col = best_id["name"]
        formula = f"COUNT_DISTINCT({col})" if wants_distinct or "order" in col or "customer" in col else f"COUNT({col})"
        unit = "count"
    elif wants_count:
        formula, unit = "COUNT(*)", "count"
        assumptions.append("No identifier column matched; counting rows.")
    elif best_num is not None:
        col = best_num["name"]
        fn = "AVG" if wants_avg else "SUM"
        formula = f"{fn}({col})"
        unit = "INR" if any(k in col for k in ("sales", "amount", "revenue", "cost", "price", "profit")) else None
    elif existing:
        formula = f"[{existing['name']}]"
        assumptions.append(f"Reuses existing metric [{existing['name']}].")
    else:
        raise AIUnavailable(
            "TARA offline mode could not map your description to a column. Mention a column name "
            f"({', '.join(c['name'] for c in numeric[:6])}...) or configure an AI provider for richer generation."
        )

    # simple categorical filter detection ("in EU", "for online channel")
    filters = []
    for c in cols:
        if c["category"] != "string":
            continue
        for tv in (prof.get(c["name"], {}).get("top_values") or [])[:8]:
            v = tv["value"]
            if len(v) >= 2 and re.search(rf"\b{re.escape(v.lower())}\b", p):
                filters.append(f"{c['name']} = '{v}'")
                break
    if "excluding refund" in p or "net of refund" in p or "after refund" in p:
        if any(c["name"] == "refund_amount" for c in cols) and "SUM(net_sales)" in formula:
            formula = formula.replace("SUM(net_sales)", "(SUM(net_sales) - SUM(refund_amount))", 1)
            assumptions.append("Refunds subtracted from net sales.")
    dc = ds.date_column
    tw = "all_time"
    for k, v in (("year to date", "ytd"), ("ytd", "ytd"), ("last 12 months", "last_12_months"), ("last 30 days", "last_30_days"), ("last 90 days", "last_90_days"), ("month to date", "mtd")):
        if k in p:
            tw = v
            break
    dept = next((d for d in DEPARTMENTS if d.lower() in p), None)
    return GeneratedMetric(
        name=name if not existing else f"{name} (variant)",
        description=f"{prompt.strip().rstrip('.')}.",
        business_definition=f"Computed from dataset '{ds.name}' as {formula}" + (f" where {' AND '.join(filters)}" if filters else "") + ".",
        formula=formula,
        filters=" AND ".join(filters) or None,
        aggregation=None,
        unit=unit,
        department=dept,
        date_column=dc if tw != "all_time" else None,
        time_window=tw,
        explanation=(
            f"Mapped your description onto columns of '{ds.name}'. "
            + (f"Note: an existing metric '{existing['name']}' looks related; check for duplicates." if existing else "")
        ).strip(),
        assumptions=assumptions,
    )


# ----------------------------------------------------------------------------- orchestration
def generate_metric(db: Session, user: User, ws: Workspace, prompt: str, ds: Dataset) -> dict:
    catalog = catalog_context(db, ws.id)
    status = ai_status(ws)
    start = time.perf_counter()
    gen: GeneratedMetric | None = None
    mode, notice, err = status["mode"], None, None
    if status["enabled"]:
        user_msg = json.dumps(
            {"request": prompt, "dataset": {"id": ds.id, "name": ds.name, "rows": ds.row_count, "columns": schema_context(ds)}, "existing_metrics": catalog}
        )
        try:
            raw = generate_json(db, ws, SYSTEM, user_msg, "metric_generation")
            gen = GeneratedMetric.model_validate(raw)
            rep = validate_definition(db, ws.id, {**gen.model_dump(), "dataset_id": ds.id})
            if not rep["ok"]:  # one self-repair round, feeding the compiler error back
                fix = json.loads(user_msg)
                fix["previous_attempt"] = raw
                fix["validation_errors"] = [e["message"] for e in rep["errors"]]
                raw2 = generate_json(db, ws, SYSTEM + "\nFix the validation errors from your previous attempt.", json.dumps(fix), "metric_generation_repair")
                gen = GeneratedMetric.model_validate(raw2)
        except (AIUnavailable, ValidationError) as e:
            err = f"TARA AI call failed ({e if isinstance(e, AIUnavailable) else 'malformed structured output'}); fell back to offline deterministic mode."
            gen, mode, notice = None, "offline", err
    if gen is None:
        mode = "offline"
        try:
            gen = offline_generate(prompt, ds, catalog)
        except AIUnavailable as e:
            row = AIGeneration(
                workspace_id=ws.id, user_id=user.id, prompt=prompt, dataset_id=ds.id, mode="offline", provider=None,
                latency_ms=round((time.perf_counter() - start) * 1000, 1), output={}, valid=False, status="generated", error=str(e),
            )
            db.add(row)
            db.flush()
            return {"id": row.id, "mode": "offline", "ok": False, "error": str(e), "notice": notice, "suggestion": None, "validation": None}
    data = gen.model_dump()
    data["dataset_id"] = ds.id
    rep = validate_definition(db, ws.id, data)
    row = AIGeneration(
        workspace_id=ws.id, user_id=user.id, prompt=prompt, dataset_id=ds.id, mode=mode,
        provider=effective_provider(ws) if mode == "ai" else None,
        latency_ms=round((time.perf_counter() - start) * 1000, 1), output=data, valid=rep["ok"], error=err,
    )
    db.add(row)
    db.flush()
    return {
        "id": row.id, "mode": mode, "ok": True, "notice": notice, "provider": row.provider, "latency_ms": row.latency_ms,
        "suggestion": data, "validation": rep,
        "label": "Generated by TARA (AI)" if mode == "ai" else "Generated by TARA offline deterministic mode - review carefully",
    }
