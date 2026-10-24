import json
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require
from ..errors import NotFound
from ..models import ChatConversation, ChatMessage, Dataset, Metric, User
from ..services.audit import audit
from ..services.engine import QueryError, QueryTimeout, live_definition
from ..services.formula import FormulaError
from ..services.metric_query import MetricUnavailable, find_metric, run_metric
from ..services.formatting import format_value
from ..services.planner import compose_compare_text, compose_text, plan_question

router = APIRouter(prefix="/chat", tags=["chat"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    conversation_id: str | None = None


def authorised_metrics(db: Session, user: User) -> tuple[list[dict], dict[str, Dataset]]:
    """Permission boundary for Ask TARA: only approved/published metrics of the user's own workspace, on ready datasets."""
    out, datasets = [], {}
    for m in db.scalars(select(Metric).where(Metric.workspace_id == user.workspace_id, Metric.status != "deprecated")).all():
        if not (m.is_live or m.status == "approved"):
            continue
        snap = live_definition(db, m)
        if not snap or not snap.get("dataset_id"):
            continue
        ds = db.get(Dataset, snap["dataset_id"])
        if not ds or ds.workspace_id != user.workspace_id or ds.status != "ready":
            continue
        datasets[ds.id] = ds
        out.append({"key": m.key, "name": snap.get("name") or m.name, "description": snap.get("description"), "unit": snap.get("unit"), "dataset_id": ds.id, "live": m.is_live})
    # one entry per key (live wins)
    seen, uniq = set(), []
    for m in sorted(out, key=lambda x: not x["live"]):
        if m["key"] not in seen:
            seen.add(m["key"])
            uniq.append(m)
    return uniq, datasets


SUGGESTED = [
    "What was net revenue by month in the last quarter of this financial year?",
    "Which 5 states had the highest sales this year?",
    "Compare Diwali-season sales with the previous quarter",
    "What is the UPI vs COD split by region?",
    "Top 10 customers by revenue",
]


def suggestions(metrics: list[dict], datasets: dict[str, Dataset]) -> list[str]:
    """Indian-context starter questions (each is verified to return a data-backed answer in the demo workspace)."""
    keys = {m["key"] for m in metrics}
    out = list(SUGGESTED) if "revenue" in keys else []
    extra = [("orders", "How many orders did we have last month?"), ("refunds", "What were refunds in the last quarter?"),
             ("gross_margin", "What was the gross margin % in FY 2025-26?"), ("active_customers", "How many active customers in this financial year?")]
    out += [q for k, q in extra if k in keys]
    if not out and metrics:
        out = [f"What was {metrics[0]['name'].lower()} this financial year?"]
    return out[:8]


def _chart(plan, columns, rows, unit):
    if not plan.dimension or not rows:
        return None
    if plan.dimension2:
        series = sorted({str(r[1]) for r in rows})
        xs: dict[str, dict] = {}
        for r in rows:
            xs.setdefault(str(r[0]), {"x": str(r[0])})[str(r[1])] = r[-1]
        return {"type": "grouped", "x": columns[0], "series": series, "unit": "percent" if plan.share else unit, "data": list(xs.values())}
    kind = plan.chart if plan.chart in ("line", "bar", "pie") else "bar"
    if kind == "pie" and len(rows) > 8:
        kind = "bar"
    return {"type": kind, "x": columns[0], "y": columns[-1], "unit": unit, "data": [{"x": str(r[0]), "y": r[-1]} for r in rows]}


def _range(tr):
    return {"start": tr.start, "end": tr.end} if tr else None


def process_question(db: Session, user: User, question: str, history: list[dict]) -> dict:
    t0 = time.perf_counter()
    metrics, datasets = authorised_metrics(db, user)
    plan, notice = plan_question(db, user.workspace, question, metrics, datasets, history)
    base = {"plan": plan.model_dump(), "notice": notice, "suggestions": suggestions(metrics, datasets)}
    if not plan.supported:
        return {**base, "kind": "unsupported", "text": plan.reason or "I can't answer that from the approved metrics and data I have access to.", "duration_ms": round((time.perf_counter() - t0) * 1000, 1)}
    try:
        find_metric(db, user.workspace_id, plan.metric_key)
        common = dict(dimension=plan.dimension, dimension2=plan.dimension2, grain=plan.grain, filters=[f.model_dump() for f in plan.filters], order=plan.order, limit=plan.limit, kind="chat")
        res, meta = run_metric(db, user.workspace_id, user.id, plan.metric_key, time_range=_range(plan.time_range), **common)
        res_b = None
        if plan.compare_range:
            res_b, _ = run_metric(db, user.workspace_id, user.id, plan.metric_key, time_range=_range(plan.compare_range), **common)
    except (FormulaError, QueryError, QueryTimeout, MetricUnavailable) as e:
        msg = getattr(e, "message", str(e))
        return {**base, "kind": "error", "text": f"I couldn't run that query safely: {msg}. No numbers were estimated.", "error": msg, "duration_ms": round((time.perf_counter() - t0) * 1000, 1)}
    unit = meta["unit"]
    columns, rows = res.columns, res.rows
    kpi = None
    if res_b is not None and not plan.dimension:
        va = res.rows[0][-1] if res.rows else None
        vb = res_b.rows[0][-1] if res_b.rows else None
        text = compose_compare_text(plan, meta["metric_name"], unit, va, vb)
        columns, rows = ["period", "value"], [[plan.time_range.label, va], [plan.compare_range.label, vb]]
        chart = {"type": "bar", "x": "period", "y": "value", "unit": unit, "data": [{"x": r[0].split(" (")[0], "y": r[1]} for r in rows]}
        kpi = {"label": meta["metric_name"], "value": va, "formatted": format_value(va, unit), "unit": unit}
    else:
        text = compose_text(plan, meta["metric_name"], unit, columns, rows, res.truncated)
        if plan.share and plan.dimension2 and rows:
            totals: dict = {}
            for r in rows:
                totals[r[0]] = totals.get(r[0], 0) + (r[-1] or 0)
            columns = [*columns, "share_pct"]
            rows = [[*r, round((r[-1] or 0) / totals[r[0]] * 100, 1) if totals[r[0]] else None] for r in rows]
        chart = _chart(plan, columns, rows, unit)
        if not plan.dimension and rows:
            kpi = {"label": meta["metric_name"], "value": rows[0][-1], "formatted": format_value(rows[0][-1], unit), "unit": unit}
    if plan.assumption:
        text = f"{text} _({plan.assumption})_"
    out = {
        **base, "kind": "answer", "text": text, "table": {"columns": columns, "rows": rows, "truncated": res.truncated},
        "chart": chart, "kpi": kpi if (kpi and res_b is None) else None,
        "sources": [{"metric_id": meta["metric_id"], "key": meta["metric_key"], "name": meta["metric_name"], "version": meta["version"], "formula": meta["formula"], "dataset": meta["dataset_name"], "status": meta["status"], "unit": unit}],
        "applied": {
            "time_range": plan.time_range.model_dump() if plan.time_range else None, "compare_range": plan.compare_range.model_dump() if plan.compare_range else None,
            "filters": [f.model_dump() for f in plan.filters], "dimension": plan.dimension, "dimension2": plan.dimension2, "grain": plan.grain, "order": plan.order, "limit": plan.limit,
        },
        "query": {"sql": res.sql, "params": res.params, "duration_ms": res.duration_ms, "scanned_rows": res.scanned_rows},
        "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    return out


def _conv(db: Session, user: User, cid: str | None, title_hint: str) -> ChatConversation:
    if cid:
        c = db.get(ChatConversation, cid)
        if not c or c.workspace_id != user.workspace_id or c.user_id != user.id:
            raise NotFound("Conversation")
        return c
    c = ChatConversation(workspace_id=user.workspace_id, user_id=user.id, title=title_hint[:80])
    db.add(c)
    db.flush()
    return c


def _history(db: Session, c: ChatConversation) -> list[dict]:
    rows = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == c.id).order_by(ChatMessage.created_at.desc()).limit(6)).all()
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def _persist(db: Session, user: User, c: ChatConversation, question: str, out: dict, request: Request | None):
    db.add(ChatMessage(conversation_id=c.id, role="user", content=question))
    db.add(ChatMessage(conversation_id=c.id, role="assistant", content=out["text"], payload={k: v for k, v in out.items() if k != "text"}))
    audit(db, user, "chat.ask", "conversation", c.id, {"question": question[:200], "kind": out["kind"]}, request)


@router.get("/suggestions")
def get_suggestions(user: User = Depends(require("chat.ask")), db: Session = Depends(get_db)):
    metrics, datasets = authorised_metrics(db, user)
    return {"items": suggestions(metrics, datasets), "metrics": [m["name"] for m in metrics]}


@router.post("/ask")
def ask(body: AskIn, request: Request, user: User = Depends(require("chat.ask")), db: Session = Depends(get_db)):
    c = _conv(db, user, body.conversation_id, body.question)
    out = process_question(db, user, body.question.strip(), _history(db, c))
    _persist(db, user, c, body.question, out, request)
    db.commit()
    return {"conversation_id": c.id, **out}


@router.post("/ask/stream")
def ask_stream(body: AskIn, request: Request, user: User = Depends(require("chat.ask")), db: Session = Depends(get_db)):
    """Server-sent events: status -> plan -> result (table/chart/kpi) -> text chunks -> done."""
    c = _conv(db, user, body.conversation_id, body.question)
    out = process_question(db, user, body.question.strip(), _history(db, c))
    _persist(db, user, c, body.question, out, request)
    db.commit()

    def sse(event: str, data) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    def gen():
        yield sse("status", {"conversation_id": c.id, "stage": "planning"})
        yield sse("plan", {"plan": out["plan"], "notice": out.get("notice")})
        yield sse("result", {k: v for k, v in out.items() if k not in ("text", "plan")})
        words = out["text"].split(" ")
        for i in range(0, len(words), 4):
            yield sse("text", {"delta": " ".join(words[i : i + 4]) + (" " if i + 4 < len(words) else "")})
            time.sleep(0.02)
        yield sse("done", {"conversation_id": c.id, "text": out["text"]})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
def conversations(user: User = Depends(require("chat.ask")), db: Session = Depends(get_db)):
    rows = db.scalars(select(ChatConversation).where(ChatConversation.user_id == user.id).order_by(ChatConversation.updated_at.desc()).limit(50)).all()
    return {"items": [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()} for c in rows]}


@router.get("/conversations/{cid}")
def conversation(cid: str, user: User = Depends(require("chat.ask")), db: Session = Depends(get_db)):
    c = _conv(db, user, cid, "")
    rows = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == c.id).order_by(ChatMessage.created_at)).all()
    return {"id": c.id, "title": c.title, "messages": [{"id": m.id, "role": m.role, "content": m.content, "payload": m.payload, "created_at": m.created_at.isoformat()} for m in rows]}


@router.delete("/conversations/{cid}")
def delete_conversation(cid: str, user: User = Depends(require("chat.ask")), db: Session = Depends(get_db)):
    c = _conv(db, user, cid, "")
    for m in db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == c.id)).all():
        db.delete(m)
    db.delete(c)
    db.commit()
    return {"ok": True}
