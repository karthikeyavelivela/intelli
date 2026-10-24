"""Performance evaluation: every number here is computed from stored telemetry or fresh measurements, never hardcoded.
Reference assumptions (manual effort baselines) are explicit constants and labelled as such in the output."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AIGeneration, Dashboard, Dataset, EvaluationRun, Execution, IngestionJob, Metric, User
from .conflicts import _groups, diff_definitions
from .dashboards import dashboard_data
from .engine import metric_snapshot
from .metric_query import MetricUnavailable, run_metric
from .formula import FormulaError
from .metrics import validate_definition

CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "eval_cases.json"
MANUAL_METRIC_CREATION_SEC = 360  # reference assumption: analyst writes + checks one metric definition by hand (~6 min)
MANUAL_PAIR_REVIEW_SEC = 45  # reference assumption: manually eyeballing one pair of definitions (~45 s)


def load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


def _pct(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    k = min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))
    return round(s[k], 2)


def _prf(tp: int, fp: int, fn: int) -> dict:
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def naive_detect(a: dict, b: dict) -> set[str]:
    """Stand-in for a manual/text-diff comparison: any raw string difference is flagged under that field."""
    out = set()
    if a["formula"] != b["formula"]:
        out.add("formula")
    if (a.get("filters") or "") != (b.get("filters") or ""):
        out.add("filter")
    if (a.get("unit") or "") != (b.get("unit") or ""):
        out.add("unit")
    if (a.get("time_window") or "all_time") != (b.get("time_window") or "all_time") or (a.get("date_column") or "") != (b.get("date_column") or ""):
        out.add("date_range")
    if a.get("dataset_id") != b.get("dataset_id"):
        out.add("dataset")
    return out


def evaluate_conflict_detection() -> dict:
    cases = load_cases()
    auto = {"tp": 0, "fp": 0, "fn": 0}
    naive = {"tp": 0, "fp": 0, "fn": 0}
    rows = []
    t0 = time.perf_counter()
    for c in cases:
        exp = set(c["expected"])
        got = {d["type"] for d in diff_definitions(c["a"], c["b"])}
        ng = naive_detect(c["a"], c["b"])
        for tgt, pred in ((auto, got), (naive, ng)):
            tgt["tp"] += len(exp & pred)
            tgt["fp"] += len(pred - exp)
            tgt["fn"] += len(exp - pred)
        rows.append({"id": c["id"], "description": c["description"], "expected": sorted(exp), "automated": sorted(got), "naive": sorted(ng),
                     "automated_correct": got == exp, "naive_correct": ng == exp})
    ms = (time.perf_counter() - t0) * 1000
    return {
        "cases": len(cases), "automated": _prf(**auto), "naive_manual": _prf(**naive), "rows": rows,
        "automated_exact_match": round(sum(r["automated_correct"] for r in rows) / len(rows), 4),
        "naive_exact_match": round(sum(r["naive_correct"] for r in rows) / len(rows), 4),
        "eval_time_ms": round(ms, 2),
    }


def run_evaluation(db: Session, user: User) -> EvaluationRun:
    t_all = time.perf_counter()
    ws = user.workspace_id
    res: dict = {"assumptions": {"manual_metric_creation_seconds": MANUAL_METRIC_CREATION_SEC, "manual_pair_review_seconds": MANUAL_PAIR_REVIEW_SEC,
                                  "note": "Manual baselines are explicit reference assumptions, not measurements. Everything else is measured."}}

    # 1. dataset processing
    jobs = db.scalars(select(IngestionJob).where(IngestionJob.workspace_id == ws, IngestionJob.status == "succeeded").order_by(IngestionJob.created_at.desc()).limit(50)).all()
    names = {d.id: d.name for d in db.scalars(select(Dataset).where(Dataset.workspace_id == ws)).all()}
    durs = [j.duration_ms for j in jobs if j.duration_ms is not None]
    res["dataset_processing"] = {
        "jobs": len(jobs), "avg_ms": round(statistics.mean(durs), 1) if durs else None, "p95_ms": _pct(durs, 95),
        "rows_per_second": round(sum(j.rows for j in jobs) / (sum(durs) / 1000)) if durs and sum(durs) else None,
        "failed_jobs": len(db.scalars(select(IngestionJob).where(IngestionJob.workspace_id == ws, IngestionJob.status == "failed")).all()),
        "per_dataset": [{"dataset": names.get(j.dataset_id, "?"), "rows": j.rows, "ms": j.duration_ms, "runner": j.runner} for j in jobs[:10]],
    }

    # 2. fresh benchmark: run every live metric once
    live = db.scalars(select(Metric).where(Metric.workspace_id == ws, Metric.is_live.is_(True))).all()
    lat, bench_ok, bench = [], 0, []
    for m in live:
        t0 = time.perf_counter()
        try:
            r, _ = run_metric(db, ws, user.id, m.key, kind="execute")
            ms = r.duration_ms
            bench_ok += 1
            ok = True
        except (FormulaError, MetricUnavailable, Exception) as e:  # noqa: BLE001
            ms, ok = (time.perf_counter() - t0) * 1000, False
        lat.append(ms)
        bench.append({"metric": m.name, "ms": round(ms, 2), "ok": ok})
    hist = [e.duration_ms for e in db.scalars(select(Execution).where(Execution.workspace_id == ws, Execution.ok.is_(True), Execution.kind.in_(["execute", "chat", "dashboard"])).order_by(Execution.created_at.desc()).limit(300)).all()]
    res["query_latency"] = {
        "benchmark_queries": len(lat), "benchmark_avg_ms": round(statistics.mean(lat), 2) if lat else None, "benchmark_p95_ms": _pct(lat, 95),
        "history_samples": len(hist), "history_p50_ms": _pct(hist, 50), "history_p95_ms": _pct(hist, 95), "benchmark": bench,
    }

    # 3. validation pass rate (fresh over all non-deprecated metrics + historical Lab validations)
    allm = db.scalars(select(Metric).where(Metric.workspace_id == ws, Metric.status != "deprecated")).all()
    v_ok = sum(1 for m in allm if validate_definition(db, ws, metric_snapshot(m))["ok"])
    hv = db.scalars(select(Execution).where(Execution.workspace_id == ws, Execution.kind == "validate")).all()
    res["validation"] = {
        "metrics_checked": len(allm), "metrics_passing": v_ok, "pass_rate": round(v_ok / len(allm), 4) if allm else None,
        "lab_validations": len(hv), "lab_pass_rate": round(sum(1 for h in hv if h.ok) / len(hv), 4) if hv else None,
    }

    # 4. query success rate (historical)
    ex = db.scalars(select(Execution).where(Execution.workspace_id == ws, Execution.kind.in_(["execute", "chat", "dashboard"]))).all()
    by_kind = {}
    for e in ex:
        k = by_kind.setdefault(e.kind, {"total": 0, "ok": 0})
        k["total"] += 1
        k["ok"] += int(e.ok)
    res["query_success"] = {
        "total": len(ex), "ok": sum(1 for e in ex if e.ok), "success_rate": round(sum(1 for e in ex if e.ok) / len(ex), 4) if ex else None,
        "by_kind": [{"kind": k, **v, "rate": round(v["ok"] / v["total"], 4)} for k, v in by_kind.items()],
    }

    # 5. conflict detection precision/recall on labelled ground truth
    res["conflict_detection"] = evaluate_conflict_detection()

    # 6. AI suggestion acceptance
    gens = db.scalars(select(AIGeneration).where(AIGeneration.workspace_id == ws)).all()
    good = [g for g in gens if g.output]
    res["ai_acceptance"] = {
        "generations": len(gens), "with_output": len(good), "valid": sum(1 for g in good if g.valid), "accepted": sum(1 for g in gens if g.accepted),
        "acceptance_rate": round(sum(1 for g in gens if g.accepted) / len(gens), 4) if gens else None,
        "validity_rate": round(sum(1 for g in good if g.valid) / len(good), 4) if good else None,
        "by_mode": [{"mode": m, "count": sum(1 for g in gens if g.mode == m), "accepted": sum(1 for g in gens if g.mode == m and g.accepted)} for m in ("ai", "offline")],
    }

    # 7. dashboard load time (fresh)
    dloads = []
    for d in db.scalars(select(Dashboard).where(Dashboard.workspace_id == ws)).all():
        out = dashboard_data(db, d, user.id)
        dloads.append({"dashboard": d.name, "widgets": len(d.widgets or []), "ms": out["load_ms"], "failed_widgets": sum(1 for w in out["widgets"].values() if not w["ok"])})
    ms_list = [x["ms"] for x in dloads]
    res["dashboard_load"] = {"dashboards": len(dloads), "avg_ms": round(statistics.mean(ms_list), 1) if ms_list else None, "p95_ms": _pct(ms_list, 95), "items": dloads}

    # 8. manual vs AI-assisted metric creation
    ai_lat = [g.latency_ms for g in good if g.latency_ms]
    avg_ai = statistics.mean(ai_lat) / 1000 if ai_lat else None
    tara_made = [m for m in allm if m.source == "tara"]
    res["creation_comparison"] = {
        "manual_seconds_per_metric_assumed": MANUAL_METRIC_CREATION_SEC,
        "ai_generation_avg_seconds_measured": round(avg_ai, 2) if avg_ai is not None else None,
        "ai_assisted_total_seconds_est": round(avg_ai + 60, 1) if avg_ai is not None else None,  # +60 s human review/edit assumption
        "review_edit_seconds_assumed": 60,
        "time_saved_pct": round((1 - (avg_ai + 60) / MANUAL_METRIC_CREATION_SEC) * 100, 1) if avg_ai is not None else None,
        "tara_created_metrics": len(tara_made), "tara_created_valid": sum(1 for m in tara_made if validate_definition(db, ws, metric_snapshot(m))["ok"]),
    }

    # 9. manual vs automated conflict detection time
    grp = _groups(list(allm))
    pairs = sum(len(g) * (len(g) - 1) // 2 for g in grp)
    t0 = time.perf_counter()
    for g in grp:
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                diff_definitions(metric_snapshot(g[i]), metric_snapshot(g[j]))
    auto_ms = (time.perf_counter() - t0) * 1000
    res["detection_comparison"] = {
        "candidate_pairs": pairs, "automated_ms_measured": round(auto_ms, 2), "manual_seconds_assumed": pairs * MANUAL_PAIR_REVIEW_SEC,
        "automated_precision": res["conflict_detection"]["automated"]["precision"], "automated_recall": res["conflict_detection"]["automated"]["recall"],
        "manual_text_diff_precision": res["conflict_detection"]["naive_manual"]["precision"], "manual_text_diff_recall": res["conflict_detection"]["naive_manual"]["recall"],
    }

    total_ms = (time.perf_counter() - t_all) * 1000
    run = EvaluationRun(workspace_id=ws, user_id=user.id, results=res, duration_ms=round(total_ms, 1))
    db.add(run)
    db.flush()
    return run
