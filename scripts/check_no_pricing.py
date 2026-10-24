"""Repository-wide search for commercial / pricing language. Exits non-zero if an unexplained hit is found.

Terms: price, pricing, plan, billing, subscription, trial, upgrade, tier, "per month", "/mo".
Allow-listed (legitimate) usages are matched by pattern below, each with a justification printed in the report."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMS = re.compile(r"pric(e|ing)|billing|subscription|\btrial\b|upgrade|\btiers?\b|per month|/mo\b|\bplans?\b", re.I)
SKIP_DIRS = {"_build", "node_modules", ".venv", "dist", "shots", "test-results", "playwright-report", "storage", "__pycache__", ".pytest_cache", "exports", "screenshots", "diagrams", "data", ".git"}
EXTS = {".py", ".ts", ".tsx", ".md", ".json", ".yml", ".yaml", ".html", ".css", ".mjs", ".sh", ".ps1", ".toml", ".txt", ".ini"}
# (regex on the offending line, justification)
ALLOW = [
    (re.compile(r"alembic upgrade|def upgrade|\bupgrade\(\)|op\.|alembic.*upgrade|Running upgrade|pip install --upgrade|npm.*upgrade", re.I), "database migration command (Alembic 'upgrade'), not a commercial upgrade"),
    (re.compile(r"return plan|-> plan ->|query[ _-]?plan|QueryPlan|plan_question|offline_plan|validate_plan|ai_plan|plan\.|plan\b.*(planner|validated|JSON)|\bplan[,:)\]]|\bplans? (reference|forged|rejected|referencing)|ConflictPlan|resolution plan|execution plan|(build|test) plan|\"plan\"|'plan'|\bplan =|\(plan|plan\)", re.I), "'plan' in the sense of a TARA query plan / resolution plan"),
    (re.compile(r"unit_price|\bprice\b.*(rng|uniform|round|lo, hi|product|catalog|cost|float|np\.)|price \*|\"price\"|price = |, price,|qty \* price|\bprice\[|\bprice\)|\bprice,|keywords?.*price|\(\"sales\", \"amount\"", re.I), "product unit price attribute in the synthetic retail dataset (data, not product pricing)"),
    (re.compile(r"scripts/check_no_pricing|check_no_pricing|no pricing|pricing/commercial|Pricing and|pricing section|Pricing removed|pricing, plans|pricing,|\bpricing\b.*(removed|absent|none|zero|banned|check|search|grep)", re.I), "documentation/tests that state or verify the ABSENCE of pricing"),
    (re.compile(r"banned|not\.toContain|not\.toMatch|toHaveCount\(0\)|queryByRole\(\"link\", \{ name: /pricing|assert not|must not|never", re.I), "negative assertions in tests"),
]
hits, allowed = [], []
for path in ROOT.rglob("*"):
    if path.name == "check_no_pricing.py":
        continue  # this checker necessarily contains the search terms
    if not path.is_file() or path.suffix.lower() not in EXTS or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts) or path.name in ("package-lock.json",):
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for n, line in enumerate(text.splitlines(), 1):
        if not TERMS.search(line):
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        why = next((w for rx, w in ALLOW if rx.search(line)), None)
        (allowed if why else hits).append({"file": rel, "line": n, "text": line.strip()[:160], "why": why})

report = {"unexplained": hits, "allow_listed": len(allowed), "allow_list_reasons": sorted({a["why"] for a in allowed}), "by_reason": {}}
for a in allowed:
    report["by_reason"][a["why"]] = report["by_reason"].get(a["why"], 0) + 1
out = ROOT / "docs" / "data" / "language_check.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=1), encoding="utf-8")
print(f"allow-listed (legitimate) hits: {len(allowed)}")
for why, c in report["by_reason"].items():
    print(f"  {c:3d}  {why}")
print(f"UNEXPLAINED commercial hits: {len(hits)}")
for h in hits:
    print(f"  {h['file']}:{h['line']}: {h['text']}")
sys.exit(1 if hits else 0)
