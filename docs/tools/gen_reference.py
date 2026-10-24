"""Generates documentation fragments FROM THE REAL CODE (nothing hand-written):
  docs/generated/api_reference.md   endpoints grouped by router, with methods and the roles allowed (from `require(capability)` + permissions.py)
  docs/generated/data_dictionary.md tables / columns / keys from the SQLAlchemy metadata
  docs/diagrams/src/er.mmd          ER diagram (Mermaid) of every table
  docs/generated/permissions.md     role x capability matrix
  docs/generated/stats.json         code statistics (files, lines, endpoints, tables)
Run:  backend/.venv/Scripts/python.exe docs/tools/gen_reference.py"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/ref.db")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ["ENV"] = "test"

from fastapi.routing import APIRoute  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.permissions import CAPABILITIES, ROLE_LABELS, ROLES  # noqa: E402

GEN = ROOT / "docs" / "generated"
GEN.mkdir(parents=True, exist_ok=True)
(ROOT / "docs" / "diagrams" / "src").mkdir(parents=True, exist_ok=True)

SUMMARY = {
    "auth": "Authentication", "workspaces": "Workspaces, settings, audit log", "users": "Users and roles", "datasets": "Datasets, uploads and connections",
    "metrics": "Metrics, workflow and versions", "ai": "TARA metric generator", "conflicts": "Conflict detection", "validation": "Formula validation",
    "execution": "Formula execution", "chat": "Ask TARA", "dashboards": "Dashboards", "evaluation": "Evaluation", "reports": "Reports and exports",
    "notifications": "Notifications and activity", "overview": "Main dashboard", "health": "Health",
}


def cap_of(route: APIRoute) -> str | None:
    stack = list(route.dependant.dependencies)
    while stack:
        d = stack.pop()
        cap = getattr(d.call, "required_cap", None)
        if cap:
            return cap
        stack.extend(d.dependencies)
    return None


def needs_auth(route: APIRoute) -> bool:
    stack = list(route.dependant.dependencies)
    while stack:
        d = stack.pop()
        if getattr(d.call, "__name__", "") == "current_user" or getattr(d.call, "required_cap", None):
            return True
        stack.extend(d.dependencies)
    return False


rows = []
for r in app.routes:
    if not isinstance(r, APIRoute) or not r.include_in_schema or r.path in ("/health",) and False:
        continue
    cap = cap_of(r)
    auth = needs_auth(r)
    roles = sorted(CAPABILITIES[cap][1], key=ROLES.index) if cap else (list(ROLES) if auth else [])
    tag = (r.tags or ["other"])[0]
    for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
        rows.append({"tag": tag, "method": m, "path": r.path, "cap": cap, "auth": auth, "roles": roles, "summary": (r.summary or r.name).replace("_", " ")})
rows.sort(key=lambda x: (list(SUMMARY).index(x["tag"]) if x["tag"] in SUMMARY else 99, x["path"], x["method"]))

short = {"admin": "Admin", "data_analyst": "Analyst", "business_user": "Business", "reviewer": "Reviewer"}
md = ["| Method | Path | Purpose | Capability | Roles allowed |", "|---|---|---|---|---|"]
out = []
cur = None
for x in rows:
    if x["tag"] != cur:
        cur = x["tag"]
        out.append(f"\n**{SUMMARY.get(cur, cur.title())}** (`{cur}` router)\n")
        out += md
    roles = "public (no login)" if not x["auth"] else ("any signed-in user" if x["cap"] is None else ", ".join(short[r] for r in x["roles"]))
    out.append(f"| {x['method']} | `{x['path']}` | {x['summary']} | {('`' + x['cap'] + '`') if x['cap'] else '-'} | {roles} |")
(GEN / "api_reference.md").write_text("\n".join(out) + "\n", encoding="utf-8")

# ----------------------------------------------------------------------------- permissions matrix
pm = ["| Capability | Admin | Data Analyst | Business User | Reviewer |", "|---|:-:|:-:|:-:|:-:|"]
for k, (label, rs, grp) in CAPABILITIES.items():
    pm.append(f"| {label} (`{k}`) | " + " | ".join("Yes" if r in rs else "-" for r in ROLES) + " |")
(GEN / "permissions.md").write_text("\n".join(pm) + "\n", encoding="utf-8")

# ----------------------------------------------------------------------------- data dictionary + ER
TABLE_DESC = {
    "workspaces": "Tenant boundary. Every other table carries a workspace_id; settings JSON holds AI provider, theme and retention.",
    "users": "Accounts with an Argon2 password hash, a role (admin, data_analyst, business_user, reviewer) and a workspace.",
    "refresh_tokens": "Hashed, rotating refresh tokens (httpOnly cookie) with expiry and revocation flag.",
    "password_resets": "Single-use, hashed, one-hour password reset tokens.",
    "connections": "External PostgreSQL/MySQL connections; the password is Fernet-encrypted at rest.",
    "datasets": "Dataset catalog: format, status/progress, detected schema, column profile and the Parquet path produced by ingestion.",
    "ingestion_jobs": "One row per background ingestion run: stage, progress, duration, runner and error report.",
    "metrics": "Governed metric definitions (working copy). A partial unique index allows only one live definition per workspace and key.",
    "metric_versions": "Immutable version snapshots. UPDATE/DELETE are blocked by an ORM guard and a database trigger.",
    "metric_reviews": "Append-only approval workflow events: submit, approve, reject, publish, deprecate.",
    "conflicts": "Detected definition conflicts with differences, severity, recommendation, affected objects and workflow status.",
    "audit_logs": "Audit trail of every sensitive action with user, entity, details, IP and request id.",
    "executions": "History of validations and executions (Formula Lab, Ask TARA, dashboards) with duration, scanned rows and error.",
    "ai_generations": "TARA metric-generator suggestions with mode (ai/offline), validity, acceptance and latency.",
    "api_usage": "AI provider call log used for usage statistics.",
    "chat_conversations": "Ask TARA conversations per user.",
    "chat_messages": "Messages with the structured answer payload (table, chart, sources, applied filters).",
    "dashboards": "Saved dashboards: widget layout JSON, filters and the version policy (latest_published or pinned).",
    "evaluation_runs": "Stored results of each performance evaluation run.",
    "notifications": "In-app notifications per workspace or user with per-user read state.",
}
dd, er = [], ["erDiagram"]
for t in Base.metadata.sorted_tables:
    dd.append(f"\n**`{t.name}`**: {TABLE_DESC.get(t.name, '')}\n")
    dd.append("| Column | Type | Null | Key / constraint |")
    dd.append("|---|---|:-:|---|")
    er.append(f"  {t.name} {{")
    for c in t.columns:
        keys = []
        if c.primary_key:
            keys.append("PK")
        for fk in c.foreign_keys:
            keys.append(f"FK -> {fk.column.table.name}.{fk.column.name}")
        if c.unique:
            keys.append("unique")
        if c.index and not c.primary_key and not c.unique:
            keys.append("indexed")
        typ = str(c.type).split("(")[0]
        dd.append(f"| `{c.name}` | {typ} | {'yes' if c.nullable else 'no'} | {', '.join(keys)} |")
        if c.primary_key or c.foreign_keys or c.name in ("name", "key", "status", "email", "role", "action"):  # ER shows keys + identifying columns only; all columns are in the data dictionary
            er.append(f"    {typ.replace(' ', '_')} {c.name}{' PK' if c.primary_key else (' FK' if c.foreign_keys else '')}")
    er.append("  }")
    for idx in t.indexes:
        if idx.unique and len(idx.columns) > 1:
            dd.append(f"\nUnique index `{idx.name}` on ({', '.join(c.name for c in idx.columns)})" + (" WHERE is_live IS TRUE (partial)" if "live" in idx.name else ""))
rel = set()
for t in Base.metadata.sorted_tables:
    for c in t.columns:
        for fk in c.foreign_keys:
            rel.add((fk.column.table.name, t.name))
for a, b in sorted(rel):
    er.append(f"  {a} ||--o{{ {b} : has")
(GEN / "data_dictionary.md").write_text("\n".join(dd) + "\n", encoding="utf-8")
(ROOT / "docs" / "diagrams" / "src" / "er.mmd").write_text("\n".join(er) + "\n", encoding="utf-8")

# ----------------------------------------------------------------------------- code statistics
def count(globs, base):
    files = [p for g in globs for p in base.rglob(g) if not any(x in p.parts for x in ("node_modules", ".venv", "dist", "__pycache__", "storage", "playwright-report", "test-results", "shots"))]
    return len(files), sum(len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) for p in files)


stats = {
    "endpoints": len(rows), "tables": len(Base.metadata.sorted_tables), "routers": len({r["tag"] for r in rows}),
    "capabilities": len(CAPABILITIES), "roles": len(ROLES),
    "backend_py": count(["*.py"], ROOT / "backend" / "app"), "backend_tests": count(["test_*.py"], ROOT / "backend" / "tests"),
    "frontend_src": count(["*.ts", "*.tsx"], ROOT / "frontend" / "src"), "e2e": count(["*.ts"], ROOT / "frontend" / "e2e"),
    "pages": len(list((ROOT / "frontend" / "src" / "pages").rglob("*.tsx"))),
}
(GEN / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
print(json.dumps(stats, indent=1))
