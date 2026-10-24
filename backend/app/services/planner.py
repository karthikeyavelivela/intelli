"""Ask TARA: question -> validated structured query plan (permission check, compile and execute happen elsewhere).
The AI (or the offline rule engine) only ever produces a PLAN; it never writes SQL and never supplies numbers.

Dates follow the Indian business calendar: financial year 1-Apr to 31-Mar, quarters Q1 Apr-Jun, Q2 Jul-Sep,
Q3 Oct-Dec, Q4 Jan-Mar, and IST for "today"."""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from ..models import Dataset, Workspace
from .ai import AIUnavailable, effective_provider, generate_json
from .calendar_in import (
    FESTIVAL_LABEL, fmt_date, fq_bounds, fq_label, fq_of, fy_bounds, fy_label, fy_start_year, last_completed_fq, latest_festival_window,
    prev_fq, today_ist,
)
from .formatting import format_value  # noqa: F401  (re-exported; shared with reports)
from .formula import GRAINS


class PlanFilter(BaseModel):
    column: str
    op: Literal["=", "!=", ">", ">=", "<", "<=", "in"] = "="
    value: str | float | int | list[str] | list[float]


class TimeRange(BaseModel):
    label: str
    start: str | None = None
    end: str | None = None


class QueryPlan(BaseModel):
    supported: bool = True
    metric_key: str | None = None
    dimension: str | None = None
    dimension2: str | None = None  # optional second breakdown, e.g. region x payment_method
    grain: str | None = None
    time_range: TimeRange | None = None
    compare_range: TimeRange | None = None  # run the same query for a second period and compare
    filters: list[PlanFilter] = Field(default_factory=list)
    order: Literal["dim", "value_desc", "value_asc"] = "dim"
    limit: int = Field(default=50, ge=1, le=1000)
    chart: Literal["kpi", "line", "bar", "pie", "table", "grouped"] | None = None
    share: bool = False  # add each group's percentage share within the first dimension
    assumption: str | None = None
    reason: str | None = None
    planner: str = "offline"


STOP = set("what was were is are the a an of for in on by per and to me show give tell how much many total did do our my last this which had have has".split())
SYN = {"sales": "revenue", "income": "revenue", "turnover": "revenue", "aov": "average order value"}
MONTHS = {m.lower(): i for i, m in enumerate(["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]) if m}
MONTHS.update({m[:3].lower(): i for m, i in list(MONTHS.items())})
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}


def _stem(t: str) -> str:
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    return t[:-1] if t.endswith("s") and not t.endswith("ss") and len(t) > 3 else t


def _toks(s: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", s.lower())]


def _tr(label: str, a: dt.date, b: dt.date) -> TimeRange:
    return TimeRange(label=f"{label} ({fmt_date(a)} to {fmt_date(b)})", start=a.isoformat(), end=b.isoformat())


# ----------------------------------------------------------------------------- time ranges (Indian fiscal calendar)
def _explicit_fy(s: str) -> int | None:
    m = re.search(r"(?:\bfy|financial year|fiscal year)\s*'?(\d{4})\s*[-–/]\s*(\d{2,4})\b", s)
    if m:
        return int(m.group(1))
    m = re.search(r"\bfy\s*'?(\d{2})\s*[-–/]\s*(\d{2})\b", s)
    if m:
        return 2000 + int(m.group(1))
    m = re.search(r"\bfy\s*'?(\d{2})\b", s)
    if m:
        return 2000 + int(m.group(1)) - 1  # FY26 == FY 2025-26
    m = re.search(r"\bfy\s*(\d{4})\b", s)
    if m:
        return int(m.group(1))
    return None


def festival_range(s: str, today: dt.date) -> TimeRange | None:
    for key, pat in (("diwali", r"diwali|deepavali"), ("dussehra", r"dussehra|dasara|navratri"), ("sankranti", r"pongal|sankranti"), ("eid", r"\beid\b"), ("holi", r"\bholi\b"), ("eoss", r"end[- ]of[- ]season|\beoss\b")):
        if re.search(pat, s):
            w = latest_festival_window(key, today)
            if w:
                return _tr(FESTIVAL_LABEL[key], *w)
    return None


def previous_period(tr: TimeRange, today: dt.date) -> TimeRange | None:
    """The period immediately before `tr`, aligned to the fiscal calendar (quarter before the quarter that contains tr.start)."""
    if not tr.start:
        return None
    a = dt.date.fromisoformat(tr.start)
    b = dt.date.fromisoformat(tr.end or tr.start)
    sy, q = fq_of(a)
    qs, qe = fq_bounds(sy, q)
    if a == qs and b == qe or "quarter" in tr.label.lower() or "season" in tr.label.lower() or "sale" in tr.label.lower():
        psy, pq = prev_fq(sy, q)
        s2, e2 = fq_bounds(psy, pq)
        return _tr(f"previous quarter, {fq_label(psy, pq)}", s2, e2)
    if (b - a).days >= 360:
        s2, e2 = fy_bounds(fy_start_year(a) - 1)
        return _tr(fy_label(fy_start_year(a) - 1), s2, e2)
    days = (b - a).days + 1
    e2 = a - dt.timedelta(days=1)
    return _tr("previous period", e2 - dt.timedelta(days=days - 1), e2)


def parse_time_range(q: str, today: dt.date | None = None) -> TimeRange | None:
    today = today or today_ist()
    s = q.lower()
    fy_now = fy_start_year(today)
    explicit = _explicit_fy(s)

    # "<ordinal|last> quarter of this/last financial year"
    m = re.search(r"\b(first|second|third|fourth|last)\s+quarter\s+of\s+(this|current|last|previous)\s+(?:financial|fiscal)\s+year|\b(first|second|third|fourth|last)\s+quarter\s+of\s+(this|current|last|previous)\s+fy\b", s)
    if m:
        which, scope = (m.group(1) or m.group(3)), (m.group(2) or m.group(4))
        sy = fy_now if scope in ("this", "current") else fy_now - 1
        if which == "last":
            if sy == fy_now:
                lq = last_completed_fq(today)
                sy, qn = lq if lq[0] == fy_now else (fy_now - 1, 4)
            else:
                qn = 4
        else:
            qn = ORD[which]
        a, b = fq_bounds(sy, qn)
        return _tr(fq_label(sy, qn), a, min(b, today) if a <= today else b)
    # Q1..Q4 with an explicit FY ("Q3 FY26", "Q2 of FY 2025-26", "Q4 2025-26")
    m = re.search(r"\bq([1-4])\b", s)
    if m and explicit is not None:
        qn = int(m.group(1))
        a, b = fq_bounds(explicit, qn)
        return _tr(fq_label(explicit, qn), a, b)
    m2 = re.search(r"\bq([1-4])\s*(?:of\s*)?(20\d{2})\b", s)
    if m2:  # "Q2 2025" -> fiscal Q2 of FY starting 2025 (documented convention)
        sy, qn = int(m2.group(2)), int(m2.group(1))
        a, b = fq_bounds(sy, qn)
        return _tr(fq_label(sy, qn), a, b)
    if explicit is not None:
        a, b = fy_bounds(explicit)
        return _tr(fy_label(explicit), a, min(b, today) if a <= today <= b else b)
    if re.search(r"\blast quarter\b|\bprevious quarter\b|\bprior quarter\b|\blast fiscal quarter\b", s):
        sy, qn = last_completed_fq(today)
        return _tr(f"last quarter, {fq_label(sy, qn)}", *fq_bounds(sy, qn))
    if re.search(r"\bthis quarter\b|\bcurrent quarter\b|\bqtd\b", s):
        sy, qn = fq_of(today)
        return _tr(f"this quarter, {fq_label(sy, qn)} to date", fq_bounds(sy, qn)[0], today)
    if re.search(r"\blast (?:financial|fiscal) year\b|\bprevious (?:financial|fiscal) year\b|\blast fy\b|\blast year\b|\bprevious year\b", s):
        a, b = fy_bounds(fy_now - 1)
        return _tr(fy_label(fy_now - 1), a, b)
    if re.search(r"\bthis (?:financial|fiscal) year\b|\bcurrent (?:financial|fiscal) year\b|\bthis fy\b|\bfytd\b|\bytd\b|\byear to date\b|\bthis year\b|\bso far this year\b", s):
        return _tr(f"{fy_label(fy_now)} to date", fy_bounds(fy_now)[0], today)
    if re.search(r"\bthis calendar year\b", s):
        return _tr(f"calendar year {today.year} to date", dt.date(today.year, 1, 1), today)
    if re.search(r"\blast month\b|\bprevious month\b", s):
        end = today.replace(day=1) - dt.timedelta(days=1)
        return _tr(f"last month, {end.strftime('%B %Y')}", end.replace(day=1), end)
    if re.search(r"\bthis month\b|\bmtd\b|\bmonth to date\b", s):
        return _tr(f"this month, {today.strftime('%B %Y')} to date", today.replace(day=1), today)
    m = re.search(r"\blast (\d{1,3}) (day|week|month)s?\b", s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = n * {"day": 1, "week": 7, "month": 30}[unit]
        return _tr(f"last {n} {unit}s", today - dt.timedelta(days=days), today)
    if re.search(r"\byesterday\b", s):
        y = today - dt.timedelta(days=1)
        return _tr("yesterday", y, y)
    if re.search(r"\btoday\b", s):
        return _tr("today", today, today)
    m = re.search(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b\s*(20\d{2})?", s)
    if m and (re.search(r"\b(in|during|for|of)\s+" + m.group(1) + r"\b", s) or m.group(2)):
        mon = MONTHS[m.group(1)]
        y = int(m.group(2)) if m.group(2) else (today.year if dt.date(today.year, mon, 1) <= today else today.year - 1)
        end = (dt.date(y + (mon == 12), mon % 12 + 1, 1) - dt.timedelta(days=1))
        return _tr(end.strftime("%B %Y"), dt.date(y, mon, 1), end)
    m = re.search(r"\b(?:in|during|for|of)\s+(20\d{2})\b", s)
    if m:
        y = int(m.group(1))
        return _tr(f"calendar year {y}", dt.date(y, 1, 1), dt.date(y, 12, 31))
    return None


# ----------------------------------------------------------------------------- metric / dimension detection
def _pick_metric(q: str, metrics: list[dict]) -> dict | None:
    qt = set(_toks(q))
    s = q.lower()
    for k, v in SYN.items():
        if re.search(rf"\b{k}\b", s):
            qt |= set(_toks(v))
    best, best_score = None, 0.0
    for m in metrics:
        nt = [t for t in _toks(m["name"]) if t not in STOP]
        if not nt:
            continue
        hit = sum(1 for t in nt if t in qt)
        score = hit / len(nt) * len(nt) ** 0.5 if hit == len(nt) else hit * 0.3
        if m["name"].lower() in s:
            score += 5
        if m.get("live"):
            score += 0.2
        if score > best_score:
            best, best_score = m, score
    return best if best_score >= 0.9 else None


def _dimension_phrase(s: str, metric_tokens: set[str]) -> tuple[set[str], int | None, bool]:
    """Returns (dimension tokens, N for top/which-N, wants_desc)."""
    n = None
    m = re.search(r"\btop\s+(\d{1,3})\b", s) or re.search(r"\b(\d{1,3})\s+(?:best|highest|top)\b", s) or re.search(r"\bwhich\s+(\d{1,3})\b", s)
    if m:
        n = int(m.group(1))
    # "which 5 states had the highest sales"  /  "top 10 customers by revenue"
    pats = [
        r"\bwhich\s+(?:\d+\s+)?([a-z_ ]{2,30}?)\s+(?:had|have|has|did|were|are|is|generated|recorded|contributed)\b",
        r"\b(?:top|best|worst|bottom|highest|lowest)\s+(?:\d+\s+)?([a-z_ ]{2,30}?)(?:\s+(?:by|in|for|during|last|this|and|where|with|over|from)\b|[?.,]|$)",
    ]
    for p in pats:
        mm = re.search(p, s)
        if mm:
            toks = {t for t in _toks(mm.group(1)) if t not in metric_tokens and t not in STOP}
            if toks:
                return toks, n, True
    for mm in re.finditer(r"\b(?:by|per|for each|each|across|grouped by|split by|breakdown by|broken down by)\s+([a-z_ ]{2,30}?)(?:\s+(?:in|for|during|last|this|and|where|with|over|from|of)\b|[?.,]|$)", s):
        toks = {t for t in _toks(mm.group(1)) if t not in STOP}
        if toks and not toks <= metric_tokens:
            return toks, n, False
    return set(), n, False


def _col_for(tokens: set[str], cols: dict) -> str | None:
    best, best_score = None, 0.0
    for c, meta in cols.items():
        if meta["category"] != "string":
            continue
        ct = set(_toks(c.replace("_", " ")))
        ov = len(ct & tokens)
        if not ov:
            continue
        score = ov - (0.1 if c.endswith("_id") else 0) - 0.01 * len(ct - tokens)
        if score > best_score:
            best, best_score = c, score
    return best


def offline_plan(question: str, metrics: list[dict], datasets: dict[str, Dataset], today: dt.date | None = None, _allow_default: bool = True, force_metric: dict | None = None) -> QueryPlan:
    today = today or today_ist()
    q = question.strip()
    s = q.lower()
    cmp_m = re.search(r"\bcompare\b(.*?)\b(?:with|to|vs\.?|versus|against)\b(.*)", s)
    left_text = cmp_m.group(1) if cmp_m else s
    m = force_metric or _pick_metric(q, metrics)
    assumption = None
    if not m and _allow_default and re.search(r"\b(split|share|mix|breakdown|distribution|vs\.?|versus|compare)\b", s):
        default = next((x for x in metrics if x["key"] == "revenue"), None)
        if default:
            candidate = offline_plan(q, metrics, datasets, today, _allow_default=False, force_metric=default)
            if candidate.supported and (candidate.dimension or candidate.filters or candidate.compare_range):
                candidate.assumption = "Your question did not name a metric, so TARA used the governed Revenue metric."
                return candidate
    if not m:
        names = ", ".join(x["name"] for x in metrics[:6])
        return QueryPlan(supported=False, reason=f"I couldn't match your question to an approved metric. Metrics I can answer about: {names or 'none yet'}.")
    ds = datasets.get(m["dataset_id"])
    if ds is None or ds.status != "ready":
        return QueryPlan(supported=False, metric_key=m["key"], reason=f"The dataset behind '{m['name']}' is not available.")
    cols = {c["name"]: c for c in ds.schema_json}
    prof = {c["name"]: c for c in (ds.profile or {}).get("columns", [])}
    plan = QueryPlan(metric_key=m["key"], planner="offline-rules", assumption=assumption)

    # ---- time (single range, or compare two periods)
    if cmp_m:
        a = festival_range(left_text, today) or parse_time_range(left_text, today)
        right = cmp_m.group(2)
        relative = re.search(r"\b(previous|prior|preceding)\s+(quarter|period)\b", right)
        b = previous_period(a, today) if (a is not None and relative) else (festival_range(right, today) or parse_time_range(right, today))
        if a is None:
            return QueryPlan(supported=False, metric_key=m["key"], reason="I couldn't work out which periods to compare. Try: 'Compare Diwali-season sales with the previous quarter'.", planner="offline-rules")
        if b is None and re.search(r"\b(previous|prior|preceding|before)\b", right):
            b = previous_period(a, today)
        if b is None:
            return QueryPlan(supported=False, metric_key=m["key"], reason="I couldn't work out the second period to compare with.", planner="offline-rules")
        plan.time_range, plan.compare_range = a, b
    else:
        plan.time_range = festival_range(s, today) or parse_time_range(q, today)

    # ---- grain
    grain = None
    adj = {"daily": "day", "weekly": "week", "monthly": "month", "quarterly": "quarter", "yearly": "year", "annually": "year"}
    m_adj = re.search(r"\b(daily|weekly|monthly|quarterly|yearly|annually)\b", s)
    if m_adj:
        grain = adj[m_adj.group(1)]
    else:
        m_by = re.search(r"\b(?:by|per|each|every|over|across)\s+(?:the\s+)?(day|week|month|quarter|year)s?\b", s)
        if m_by:
            grain = m_by.group(1)
    if not grain and re.search(r"\b(trend|over time|time series|history)\b", s):
        grain = "month"

    metric_tokens = set(_toks(m["name"])) | set(_toks(m["key"].replace("_", " ")))
    phrase, n, desc = _dimension_phrase(s, metric_tokens)
    if phrase and not grain:
        for t in ("month", "quarter", "week", "year", "day"):
            if t in phrase:
                grain = t
    dim_col = _col_for(phrase, cols) if phrase else None
    if phrase and not dim_col and not grain:
        asked = " ".join(sorted(phrase))
        return QueryPlan(
            supported=False, metric_key=m["key"], planner="offline-rules",
            reason=f"'{m['name']}' cannot be broken down by '{asked}': dataset '{ds.name}' has no matching column. Available dimensions: {', '.join(c for c, v in cols.items() if v['category'] == 'string')}.",
        )
    if grain:
        if not ds.date_column:
            return QueryPlan(supported=False, metric_key=m["key"], reason=f"Dataset '{ds.name}' has no date column, so I can't group '{m['name']}' by {grain}.", planner="offline-rules")
        plan.grain, plan.dimension = grain, ds.date_column
        if dim_col:
            plan.reason = f"Grouping by {grain}; the extra breakdown by {dim_col} is not combined in one query. Ask for it separately."

    # ---- categorical values mentioned in the question -> filters (or a 2nd breakdown when several values of one column are named)
    used = {plan.dimension} if plan.dimension else set()
    if dim_col and not plan.grain:
        plan.dimension = dim_col
        used = {dim_col}
    for c, meta in cols.items():
        if meta["category"] != "string" or c in used:
            continue
        hits = []
        for tv in (prof.get(c, {}).get("top_values") or []):
            v = tv["value"]
            if len(v) >= 2 and re.search(rf"(?<![a-z0-9]){re.escape(v.lower())}(?![a-z0-9])", s):
                hits.append(v)
        if not hits:
            continue
        neg = re.search(rf"(excluding|except|without|not|other than)\s+(?:the\s+)?{re.escape(hits[0].lower())}", s)
        if len(hits) >= 2:
            plan.filters.append(PlanFilter(column=c, op="in", value=hits))
            if plan.dimension and not plan.grain and c != plan.dimension and not plan.dimension2:
                plan.dimension2 = c
            elif not plan.dimension:
                plan.dimension = c
        else:
            plan.filters.append(PlanFilter(column=c, op="!=" if neg else "=", value=hits[0]))
    plan.share = bool(re.search(r"\b(split|share|mix|proportion|percentage|distribution)\b", s)) and bool(plan.dimension2)

    # ---- order / limit
    if desc or re.search(r"\b(top|best|highest|most|largest|biggest)\b", s):
        if plan.dimension and not plan.grain:
            plan.order, plan.limit = "value_desc", n or 5
    elif re.search(r"\b(worst|lowest|least|bottom|smallest)\b", s) and plan.dimension and not plan.grain:
        plan.order, plan.limit = "value_asc", n or 5
    elif plan.dimension and not plan.grain:
        plan.order = "value_desc"
    if re.search(r"\b(worst|lowest|least|bottom|smallest)\b", s) and plan.dimension and not plan.grain:
        plan.order, plan.limit = "value_asc", n or 5
    if plan.dimension2:
        plan.limit = max(plan.limit, 200)
        plan.order = "dim"
    # ---- chart
    if plan.compare_range and not plan.dimension:
        plan.chart = "bar"
    elif plan.dimension2:
        plan.chart = "grouped"
    elif not plan.dimension:
        plan.chart = "kpi"
    elif plan.grain:
        plan.chart = "line"
    elif re.search(r"\b(share|breakdown|distribution|split|proportion|mix)\b", s):
        plan.chart = "pie"
    else:
        plan.chart = "bar"
    return plan


PLAN_SYSTEM = """You are TARA's query planner for a governed semantic layer used by an Indian business (currency INR, financial year 1 April - 31 March, quarters Q1 Apr-Jun, Q2 Jul-Sep, Q3 Oct-Dec, Q4 Jan-Mar, timezone IST).
Convert the user's question into a JSON QUERY PLAN. You do NOT write SQL and you do NOT compute or guess numbers. Choose from the provided metrics and columns only.
If the question cannot be answered with the provided metrics/columns, return {"supported": false, "reason": "<why>"}.
JSON keys: supported (bool), metric_key (one of the provided keys), dimension (a column name or null), dimension2 (optional second column), grain (day|week|month|quarter|year or null; only when dimension is a date column),
time_range ({label,start,end} ISO dates relative to the given today), compare_range (same shape, optional, for comparisons), filters (list of {column, op in [=,!=,>,>=,<,<=,in], value}),
order (dim|value_desc|value_asc), limit (int), chart (kpi|line|bar|pie|table|grouped), share (bool), reason."""


def ai_plan(db: Session, ws: Workspace, question: str, metrics: list[dict], datasets: dict[str, Dataset], history: list[dict]) -> QueryPlan:
    ctx = []
    for m in metrics:
        ds = datasets.get(m["dataset_id"])
        if not ds:
            continue
        prof = {c["name"]: c for c in (ds.profile or {}).get("columns", [])}
        ctx.append({
            "key": m["key"], "name": m["name"], "description": m.get("description"), "unit": m.get("unit"),
            "dataset_columns": [
                {"name": c["name"], "type": c["category"], **({"values": [t["value"] for t in prof[c["name"]].get("top_values", [])[:8]]} if c["name"] in prof and prof[c["name"]].get("top_values") else {})}
                for c in ds.schema_json
            ],
            "date_column": ds.date_column,
        })
    payload = {"today": today_ist().isoformat(), "question": question, "metrics": ctx, "recent_conversation": history[-4:]}
    raw = generate_json(db, ws, PLAN_SYSTEM, json.dumps(payload), "chat_plan")
    plan = QueryPlan.model_validate(raw)
    plan.planner = "ai"
    return plan


def validate_plan(plan: QueryPlan, metrics: dict[str, dict], datasets: dict[str, Dataset]) -> QueryPlan:
    """Reject plans referencing anything outside the authorised catalog (defends against hallucinated/forged plans)."""
    if not plan.supported:
        return plan
    m = metrics.get(plan.metric_key or "")
    if not m:
        return QueryPlan(supported=False, reason=f"Metric '{plan.metric_key}' is not an approved metric you can query.", planner=plan.planner)
    ds = datasets.get(m["dataset_id"])
    if not ds:
        return QueryPlan(supported=False, reason="Dataset is not available.", planner=plan.planner)
    cols = {c["name"].lower(): c for c in ds.schema_json}
    for col in (plan.dimension, plan.dimension2):
        if col and col.lower() not in cols:
            return QueryPlan(supported=False, metric_key=plan.metric_key, reason=f"Column '{col}' does not exist in dataset '{ds.name}'.", planner=plan.planner)
    if plan.grain:
        if plan.grain not in GRAINS or not plan.dimension or cols[plan.dimension.lower()]["category"] != "date":
            return QueryPlan(supported=False, metric_key=plan.metric_key, reason="Time grouping needs a date column.", planner=plan.planner)
    for f in plan.filters:
        if f.column.lower() not in cols:
            return QueryPlan(supported=False, metric_key=plan.metric_key, reason=f"Filter column '{f.column}' does not exist in dataset '{ds.name}'.", planner=plan.planner)
    return plan


def plan_question(db: Session, ws: Workspace, question: str, metrics: list[dict], datasets: dict[str, Dataset], history: list[dict]) -> tuple[QueryPlan, str | None]:
    """Returns (validated plan, notice). Falls back to offline rules if AI is unavailable/malformed."""
    by_key = {m["key"]: m for m in metrics}
    notice = None
    if effective_provider(ws):
        try:
            plan = ai_plan(db, ws, question, metrics, datasets, history)
            return validate_plan(plan, by_key, datasets), None
        except (AIUnavailable, ValidationError) as e:
            notice = f"TARA AI planner unavailable ({e if isinstance(e, AIUnavailable) else 'malformed plan'}); used offline rule-based planner."
    return validate_plan(offline_plan(question, metrics, datasets), by_key, datasets), notice


# ----------------------------------------------------------------------------- answer composition (no AI numbers)
def _flt(plan: QueryPlan) -> str:
    return (" (" + ", ".join(f"{f.column} {f.op} {', '.join(map(str, f.value)) if isinstance(f.value, list) else f.value}" for f in plan.filters) + ")") if plan.filters else ""


def compose_text(plan: QueryPlan, name: str, unit: str | None, columns: list[str], rows: list[list], truncated: bool) -> str:
    when = f" for {plan.time_range.label}" if plan.time_range else " across all available data"
    flt = _flt(plan)
    if not rows or all(r[-1] is None for r in rows):
        return f"No data matched your question{when}{flt}, so I can't report {name}. Nothing was estimated."
    if not plan.dimension:
        return f"{name} was **{format_value(rows[0][-1], unit)}**{when}{flt}."
    label = f"{name} by {plan.grain or plan.dimension}{(' and ' + plan.dimension2) if plan.dimension2 else ''}{when}{flt}"
    vals = [(tuple(r[:-1]), r[-1]) for r in rows if r[-1] is not None]
    top = max(vals, key=lambda x: x[1])
    low = min(vals, key=lambda x: x[1])

    def _lab(p):
        t = str(p)
        if plan.grain and re.match(r"\d{4}-\d{2}-\d{2}", t):
            d = dt.date.fromisoformat(t[:10])
            return d.strftime("%b %Y") if plan.grain == "month" else fmt_date(d)
        return t

    def lab(x):
        return " / ".join(_lab(p) for p in x)

    out = f"{label}: {len(vals)} {'periods' if plan.grain else 'groups'}. Highest: {lab(top[0])} ({format_value(top[1], unit)}); lowest: {lab(low[0])} ({format_value(low[1], unit)})."
    if truncated and plan.order == "dim":
        out += " (Results truncated to the row limit.)"
    elif truncated:
        out += f" (Showing the top {plan.limit}.)"
    return out


def _days(tr: TimeRange) -> int:
    if not tr.start or not tr.end:
        return 0
    return (dt.date.fromisoformat(tr.end) - dt.date.fromisoformat(tr.start)).days + 1


def compose_compare_text(plan: QueryPlan, name: str, unit: str | None, a: float | None, b: float | None) -> str:
    la, lb = plan.time_range.label, plan.compare_range.label
    if a is None or b is None:
        return f"I could not compare {name}: one of the periods ({la if a is None else lb}) has no data. Nothing was estimated."
    delta = a - b
    pct = f"{delta / b * 100:+.1f}%" if b else "n/a (base is zero)"
    out = f"{name}: **{format_value(a, unit)}** for {la} vs **{format_value(b, unit)}** for {lb}. Change: {format_value(delta, unit)} ({pct}){_flt(plan)}."
    da, db_ = _days(plan.time_range), _days(plan.compare_range)
    if da and db_ and abs(da - db_) / max(da, db_) > 0.2 and (unit or "").lower() in ("inr", "usd", "count"):
        out += f" Note: the periods differ in length ({da} vs {db_} days); average per day is {format_value(a / da, unit)} vs {format_value(b / db_, unit)}."
    return out
