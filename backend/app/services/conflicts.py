"""Conflict detection. Deterministic structural comparison first; TARA (AI) only adds clearly-labelled semantic suggestions."""
from __future__ import annotations

import difflib
import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Conflict, Dashboard, Metric, User, Workspace
from .ai import AIUnavailable, effective_provider, generate_json
from .audit import audit, notify
from .engine import metric_snapshot, slugify
from .formula import FormulaError, canonical, extract_aggregations, parse_condition, parse_formula

SEV = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CURRENCY = {"usd", "eur", "gbp", "inr", "currency", "$", "₹", "rs"}


def _conjuncts(node) -> set[str]:
    if node is None:
        return set()
    if node[0] == "and":
        return _conjuncts(node[1]) | _conjuncts(node[2])
    return {canonical(node)}


def _norm(snap: dict) -> dict:
    out = {"expr": snap.get("formula", "").strip().lower(), "aggs": [], "filter": set(), "ok": True}
    try:
        p = parse_formula(snap["formula"])
        out["expr"] = canonical(p.expr)
        out["aggs"] = extract_aggregations(p)
        out["filter"] = _conjuncts(p.where)
        if (snap.get("filters") or "").strip():
            out["filter"] |= _conjuncts(parse_condition(snap["filters"]).where)
    except FormulaError:
        out["ok"] = False
    return out


def diff_definitions(a: dict, b: dict) -> list[dict]:
    """Pure function: structural differences between two metric snapshots. Used by detection AND by the evaluation suite."""
    diffs: list[dict] = []
    na, nb = _norm(a), _norm(b)
    if (a.get("dataset_id") or None) != (b.get("dataset_id") or None):
        diffs.append({
            "type": "dataset", "severity": "high", "source": "deterministic", "field": "dataset_id",
            "a": a.get("dataset_name") or a.get("dataset_id"), "b": b.get("dataset_name") or b.get("dataset_id"),
            "explanation": "The definitions read from different datasets, so they can never reconcile even with the same formula.",
        })
    if na["aggs"] != nb["aggs"]:
        diffs.append({
            "type": "aggregation", "severity": "high", "source": "deterministic", "field": "aggregation",
            "a": ", ".join(na["aggs"]) or "-", "b": ", ".join(nb["aggs"]) or "-",
            "explanation": f"Different aggregation functions ({', '.join(na['aggs']) or 'none'} vs {', '.join(nb['aggs']) or 'none'}) produce different numbers for the same data.",
        })
    elif na["expr"] != nb["expr"]:
        diffs.append({
            "type": "formula", "severity": "high", "source": "deterministic", "field": "formula",
            "a": a.get("formula"), "b": b.get("formula"),
            "explanation": "The formulas are not equivalent after normalisation (operand order and case are ignored), so they compute different values.",
        })
    if na["filter"] != nb["filter"]:
        only_a, only_b = sorted(na["filter"] - nb["filter"]), sorted(nb["filter"] - na["filter"])
        diffs.append({
            "type": "filter", "severity": "medium", "source": "deterministic", "field": "filters",
            "a": a.get("filters") or "(none)", "b": b.get("filters") or "(none)",
            "explanation": "Different row filters change which records are counted"
            + (f"; only A applies {only_a}" if only_a else "") + (f"; only B applies {only_b}" if only_b else "") + ".",
        })
    ua, ub = (a.get("unit") or "").strip().lower(), (b.get("unit") or "").strip().lower()
    if ua != ub:
        both_money = ua in CURRENCY and ub in CURRENCY
        sev = "medium" if both_money or not (ua and ub) else "high"
        diffs.append({
            "type": "unit", "severity": sev, "source": "deterministic", "field": "unit",
            "a": a.get("unit") or "(none)", "b": b.get("unit") or "(none)",
            "explanation": "Units differ, so values may be shown on different scales or in different currencies.",
        })
    tw_a, tw_b = a.get("time_window") or "all_time", b.get("time_window") or "all_time"
    dc_a, dc_b = (a.get("date_column") or "").lower(), (b.get("date_column") or "").lower()
    if tw_a != tw_b or dc_a != dc_b:
        diffs.append({
            "type": "date_range", "severity": "medium", "source": "deterministic", "field": "time_window",
            "a": f"{tw_a}" + (f" on {a.get('date_column')}" if dc_a else ""), "b": f"{tw_b}" + (f" on {b.get('date_column')}" if dc_b else ""),
            "explanation": "The time window or the date column used to apply it differs, so the periods covered do not match.",
        })
    return diffs


def _severity(diffs: list[dict], ref_live: bool, var_status: str) -> str:
    sev = max((SEV[d["severity"]] for d in diffs), default=1)
    kinds = {d["type"] for d in diffs}
    if ref_live and var_status in ("approved", "published", "in_review") and kinds & {"formula", "aggregation", "dataset"}:
        sev = 4
    elif len(kinds) >= 3 and sev >= 3:
        sev = 4
    return next(k for k, v in SEV.items() if v == sev)


def _recommend(ref: Metric, var: Metric, diffs: list[dict], ref_live: bool) -> tuple[str, str, str]:
    kinds = [d["type"] for d in diffs]
    dept = var.department or "departmental"
    desc = ", ".join(sorted(set(kinds)))
    if not ref_live:
        return (
            "publish_one",
            f"No published definition exists for '{ref.name}'. Choose one definition, get it approved and publish it; deprecate or rename the others.",
            "publish_one",
        )
    if set(kinds) <= {"unit", "date_range"}:
        return ("align_to_published", f"Only {desc} differ. Align the {dept} definition to the published one so every report uses the same scope.", "align_to_published")
    return (
        "rename_variant",
        f"Keep '{ref.name}' (v{ref.published_version or ref.version}) as the single governed definition. If the {dept} calculation is intentional, rename it to a distinct metric "
        f"(e.g. '{var.name} ({dept})') and document the {desc} difference; otherwise align it to the published formula.",
        "rename_variant",
    )


def _explanation(ref: Metric, var: Metric, diffs: list[dict]) -> str:
    bullets = "; ".join(f"{d['type']}: {d['explanation']}" for d in diffs)
    return (
        f"'{var.name}' ({var.department or 'no department'}, {var.status}) conflicts with '{ref.name}' ({ref.department or 'no department'}, {ref.status}). {bullets}"
    )


def _fingerprint(a: Metric, b: Metric) -> str:
    return hashlib.sha256(json.dumps([metric_snapshot(a), metric_snapshot(b)], sort_keys=True, default=str).encode()).hexdigest()


def _affected(db: Session, ws_id: str, key: str, others: list[Metric]) -> dict:
    from .metrics import dependents_of

    deps = {m.key: m.name for k in {key} for m in dependents_of(db, ws_id, k)}
    dashes = []
    for d in db.scalars(select(Dashboard).where(Dashboard.workspace_id == ws_id)).all():
        if any((w.get("metric_key") == key) for w in (d.widgets or [])):
            dashes.append({"id": d.id, "name": d.name})
    return {"metrics": [{"key": k, "name": v} for k, v in deps.items()], "dashboards": dashes}


def _groups(metrics: list[Metric]) -> list[list[Metric]]:
    by_key: dict[str, list[Metric]] = {}
    for m in metrics:
        by_key.setdefault(m.key, []).append(m)
    keys = list(by_key)
    merged: dict[str, str] = {}
    for i, k1 in enumerate(keys):
        for k2 in keys[i + 1 :]:
            if difflib.SequenceMatcher(a=k1, b=k2).ratio() >= 0.92:
                merged[k2] = merged.get(k1, k1)
    groups: dict[str, list[Metric]] = {}
    for k, ms in by_key.items():
        groups.setdefault(merged.get(k, k), []).extend(ms)
    return [g for g in groups.values() if len(g) > 1]


def _snap_with_ds(m: Metric) -> dict:
    s = metric_snapshot(m)
    s["dataset_name"] = m.dataset.name if m.dataset else None
    return s


def detect_conflicts(db: Session, user: User, ws: Workspace, request=None) -> dict:
    metrics = db.scalars(select(Metric).where(Metric.workspace_id == ws.id, Metric.status != "deprecated")).all()
    created = updated = unchanged = 0
    found: list[Conflict] = []
    for grp in _groups(list(metrics)):
        live = [m for m in grp if m.is_live]
        ref = live[0] if live else None
        if ref:
            pairs = [(ref, m) for m in grp if m.id != ref.id]
        else:
            ordered = sorted(grp, key=lambda m: m.created_at)
            pairs = [(ordered[i], ordered[j]) for i in range(len(ordered)) for j in range(i + 1, len(ordered))]
        for a, b in pairs:
            diffs = diff_definitions(_snap_with_ds(a), _snap_with_ds(b))
            existing = db.scalar(select(Conflict).where(Conflict.metric_a_id == a.id, Conflict.metric_b_id == b.id))
            if not diffs:
                continue
            fp = _fingerprint(a, b)
            if existing and existing.fingerprint == fp:
                unchanged += 1
                found.append(existing)
                continue
            action, rec, _ = _recommend(a, b, diffs, a.is_live)
            fields = dict(
                metric_key=a.key, conflict_type=diffs[0]["type"] if len({d["type"] for d in diffs}) == 1 else "multiple",
                severity=_severity(diffs, a.is_live, b.status), differences=diffs, explanation=_explanation(a, b, diffs),
                recommendation=rec, recommended_action=action, affected=_affected(db, ws.id, a.key, [a, b]), fingerprint=fp,
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                if existing.status in ("resolved", "dismissed"):
                    existing.status, existing.resolved_at = "open", None
                updated += 1
                found.append(existing)
                audit(db, user, "conflict.redetect", "conflict", existing.id, {"severity": existing.severity}, request)
            else:
                c = Conflict(workspace_id=ws.id, metric_a_id=a.id, metric_b_id=b.id, status="open", **fields)
                db.add(c)
                db.flush()
                created += 1
                found.append(c)
                audit(db, user, "conflict.detect", "conflict", c.id, {"key": a.key, "severity": c.severity, "types": [d["type"] for d in diffs]}, request)
                notify(db, ws.id, f"Conflict detected: {a.name}", f"{b.department or 'A variant'} definition differs from {a.department or 'the reference'} ({c.severity} severity)", "warning", f"/app/conflicts/{c.id}")
    # resolve conflicts whose pair no longer differs
    for c in db.scalars(select(Conflict).where(Conflict.workspace_id == ws.id, Conflict.status.notin_(["resolved", "dismissed"]))).all():
        if c.id not in {f.id for f in found}:
            a, b = db.get(Metric, c.metric_a_id), db.get(Metric, c.metric_b_id)
            moved_apart = c.conflict_type != "semantic" and a is not None and b is not None and a.key != b.key
            if not a or not b or moved_apart or a.status == "deprecated" or b.status == "deprecated" or not diff_definitions(_snap_with_ds(a), _snap_with_ds(b)):
                c.status = "resolved"
                c.resolution_note = (c.resolution_note or "") + " [auto-closed: definitions no longer conflict]"
                audit(db, user, "conflict.auto_close", "conflict", c.id, {}, request)
    tara = semantic_suggestions(db, user, ws, list(metrics), request)
    db.flush()
    return {
        "created": created, "updated": updated, "unchanged": unchanged, "total_open": len([c for c in found if c.status not in ("resolved", "dismissed")]),
        "tara": tara,
    }


SEM_SYSTEM = """You are TARA reviewing a metric catalog for SEMANTIC inconsistencies that structural comparison cannot catch:
two metrics with different names but overlapping meaning, or similar names with materially different meaning.
Only flag pairs you are confident about. Return JSON: {"suggestions":[{"metric_a":"<name>","metric_b":"<name>","issue":"...","severity":"low|medium|high"}]}. Return at most 5. Return {"suggestions":[]} if none."""


def semantic_suggestions(db: Session, user: User, ws: Workspace, metrics: list[Metric], request=None) -> dict:
    if not effective_provider(ws):
        return {"enabled": False, "note": "TARA semantic review skipped: no AI provider configured (deterministic checks still ran).", "created": 0}
    if len(metrics) < 2:
        return {"enabled": True, "created": 0, "note": "Not enough metrics for semantic review."}
    cat = [{"name": m.name, "description": m.description, "formula": m.formula, "unit": m.unit, "department": m.department} for m in metrics[:40]]
    try:
        out = generate_json(db, ws, SEM_SYSTEM, json.dumps(cat), "semantic_conflicts")
    except AIUnavailable as e:
        return {"enabled": True, "created": 0, "note": f"TARA semantic review unavailable: {e}"}
    by_name = {m.name.lower(): m for m in metrics}
    created = 0
    for s in (out.get("suggestions") or [])[:5]:
        a, b = by_name.get(str(s.get("metric_a", "")).lower()), by_name.get(str(s.get("metric_b", "")).lower())
        if not a or not b or a.id == b.id or a.key == b.key:
            continue
        a, b = sorted([a, b], key=lambda m: m.id)
        if db.scalar(select(Conflict).where(Conflict.metric_a_id == a.id, Conflict.metric_b_id == b.id)):
            continue
        sev = s.get("severity") if s.get("severity") in SEV else "low"
        issue = str(s.get("issue", ""))[:600]
        c = Conflict(
            workspace_id=ws.id, metric_key=a.key, metric_a_id=a.id, metric_b_id=b.id, conflict_type="semantic", severity=sev,
            differences=[{"type": "semantic", "severity": sev, "source": "tara", "field": "meaning", "a": a.name, "b": b.name, "explanation": issue}],
            explanation=f"TARA suggestion: {issue}", recommendation="Review both definitions and decide whether they should be merged, renamed or documented as distinct.",
            recommended_action="accept_both", affected={}, fingerprint=hashlib.sha256((a.id + b.id + issue).encode()).hexdigest(), status="open",
        )
        db.add(c)
        created += 1
    return {"enabled": True, "created": created}


def apply_resolution(db: Session, user: User, c: Conflict, action: str, note: str, new_name: str | None, request=None) -> None:
    from .metrics import add_version

    ref, var = db.get(Metric, c.metric_a_id), db.get(Metric, c.metric_b_id)
    if action == "rename_variant":
        if not new_name or not new_name.strip():
            from ..errors import BadRequest

            raise BadRequest("new_name is required to rename the variant")
        var.name, var.key = new_name.strip(), slugify(new_name)
        var.version += 1
        add_version(db, var, user, f"Renamed to '{var.name}' to resolve conflict with '{ref.name}'", note)
    elif action == "align_to_published":
        for f in ("formula", "filters", "aggregation", "unit", "time_window", "date_column", "dataset_id"):
            setattr(var, f, getattr(ref, f))
        var.version += 1
        if var.status in ("approved", "in_review", "published"):
            var.status = "draft"
        add_version(db, var, user, f"Aligned to '{ref.name}' to resolve conflict", note)
    elif action == "deprecate_variant":
        var.status, var.is_live = "deprecated", False
        var.version += 1
        add_version(db, var, user, f"Deprecated to resolve conflict with '{ref.name}'", note)
    elif action == "accept_both":
        pass
    else:
        from ..errors import BadRequest

        raise BadRequest("Unknown resolution action")
    audit(db, user, f"conflict.resolution.{action}", "metric", var.id, {"conflict": c.id, "note": note}, request)
