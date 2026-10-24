"""Charts for the reports, generated ONLY from measured data files in docs/data (never hand-entered numbers)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "docs" / "charts"
OUT.mkdir(parents=True, exist_ok=True)
INK, GREY, LIGHT, ACCENT = "#111111", "#6b6b6b", "#d9d9d9", "#6d4aff"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GREY, "axes.labelcolor": INK, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("chart", name)


def junit_counts(path):
    import xml.etree.ElementTree as ET

    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    t = f = e = s = 0
    for ts in suites:
        t += int(ts.get("tests", 0)); f += int(ts.get("failures", 0)); e += int(ts.get("errors", 0)); s += int(ts.get("skipped", 0))
    return t, f + e, s


def main():
    b = load("benchmark.json")
    # 1 ingestion
    ing = b["ingestion"]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    labels = [f"{i['format']}\n{i['rows']:,} rows" for i in ing]
    vals = [i["job_ms"]["mean"] for i in ing]
    bars = ax.bar(labels, vals, color=[ACCENT if "x4" in i["format"] else INK for i in ing], width=0.55)
    for r, i in zip(bars, ing):
        ax.text(r.get_x() + r.get_width() / 2, r.get_height() + max(vals) * 0.02, f"{r.get_height():,.0f} ms\n{i['rows_per_second']:,} rows/s", ha="center", va="bottom", fontsize=8.5)
    ax.set_ylabel("Background job time (ms)")
    ax.set_title("Dataset ingestion time by format (mean of runs)", loc="left", fontsize=11, fontweight="bold")
    ax.set_ylim(0, max(vals) * 1.3)
    save(fig, "ingestion_time.png")
    # 2 query latency
    pw = sorted(b["query_latency"]["per_workload"], key=lambda x: x["engine_p95_ms"])
    fig, ax = plt.subplots(figsize=(7.2, 0.33 * len(pw) + 1.4))
    y = range(len(pw))
    ax.barh([i + 0.2 for i in y], [w["engine_p50_ms"] for w in pw], height=0.38, color=INK, label="p50")
    ax.barh([i - 0.2 for i in y], [w["engine_p95_ms"] for w in pw], height=0.38, color=ACCENT, label="p95")
    ax.set_yticks(list(y)); ax.set_yticklabels([w["workload"] for w in pw], fontsize=8)
    ax.set_xlabel("DuckDB execution time (ms), 30 runs per workload")
    ax.set_title(f"Query latency on {b['dataset']['rows']:,} rows", loc="left", fontsize=11, fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    save(fig, "query_latency.png")
    # 3 dashboards
    d = b["dashboards"]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    xs = range(len(d))
    ax.bar([i - 0.18 for i in xs], [x["server_load_ms"]["p50"] for x in d], 0.34, color=INK, label="p50")
    ax.bar([i + 0.18 for i in xs], [x["server_load_ms"]["p95"] for x in d], 0.34, color=ACCENT, label="p95")
    ax.set_xticks(list(xs)); ax.set_xticklabels([f"{x['template'].title()}\n{x['widgets']} widgets" for x in d])
    ax.set_ylabel("Server-side load time (ms)")
    ax.set_title("Dashboard load time (all widgets), 10 loads each", loc="left", fontsize=11, fontweight="bold")
    ax.legend(frameon=False)
    save(fig, "dashboard_load.png")
    # 4 Ask TARA latency
    a = b["ask_tara"]
    fig, ax = plt.subplots(figsize=(7.2, 0.45 * len(a) + 1.2))
    names = [x["question"][:62] + ("..." if len(x["question"]) > 62 else "") for x in a]
    y = list(range(len(a)))
    ax.barh([i + 0.2 for i in y], [x["http_ms"]["p50"] for x in a], 0.38, color=INK, label="p50")
    ax.barh([i - 0.2 for i in y], [x["http_ms"]["p95"] for x in a], 0.38, color=ACCENT, label="p95")
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=7.5); ax.invert_yaxis()
    ax.set_xlabel("End-to-end HTTP time (ms), 10 runs each (offline planner)")
    ax.set_title("Ask TARA response time", loc="left", fontsize=11, fontweight="bold")
    ax.legend(frameon=False)
    save(fig, "ask_tara_latency.png")
    # 5 conflict detection quality
    cd = b["evaluation"]["conflict_detection"]
    metrics = [("Precision", cd["automated"]["precision"], cd["naive_manual"]["precision"]), ("Recall", cd["automated"]["recall"], cd["naive_manual"]["recall"]), ("F1", cd["automated"]["f1"], cd["naive_manual"]["f1"]), ("Exact match", cd["automated_exact_match"], cd["naive_exact_match"])]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    xs = range(len(metrics))
    ax.bar([i - 0.19 for i in xs], [m[1] for m in metrics], 0.36, color=ACCENT, label="Automated (AST-normalised)")
    ax.bar([i + 0.19 for i in xs], [m[2] for m in metrics], 0.36, color=LIGHT, edgecolor=GREY, label="Manual text diff")
    for i, m in enumerate(metrics):
        ax.text(i - 0.19, m[1] + 0.015, f"{m[1]:.2f}", ha="center", fontsize=8)
        ax.text(i + 0.19, m[2] + 0.015, f"{m[2]:.2f}", ha="center", fontsize=8)
    ax.set_xticks(list(xs)); ax.set_xticklabels([m[0] for m in metrics]); ax.set_ylim(0, 1.15)
    ax.set_title(f"Conflict detection on {cd['cases']} labelled ground-truth cases", loc="left", fontsize=11, fontweight="bold")
    ax.legend(frameon=False, loc="lower left")
    save(fig, "conflict_detection_quality.png")
    # 6 tests by suite
    suites = []
    for label, f in (("pytest (SQLite)", "backend_junit.xml"), ("pytest (PostgreSQL 18)", "backend_postgres_junit.xml"), ("Vitest", "frontend_junit.xml")):
        if (DATA / f).exists():
            t, fl, s = junit_counts(DATA / f)
            suites.append((label, t - fl - s, fl))
    if (DATA / "playwright_results.json").exists():
        pr = load("playwright_results.json")["stats"]
        suites.append(("Playwright E2E", pr["expected"], pr["unexpected"]))
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.bar([s[0] for s in suites], [s[1] for s in suites], color=INK, label="passed", width=0.55)
    ax.bar([s[0] for s in suites], [s[2] for s in suites], bottom=[s[1] for s in suites], color="#c0392b", label="failed", width=0.55)
    for i, s in enumerate(suites):
        ax.text(i, s[1] + s[2] + 2, f"{s[1]}/{s[1] + s[2]}", ha="center", fontsize=9)
    ax.set_ylabel("Tests"); ax.set_title("Automated tests by suite", loc="left", fontsize=11, fontweight="bold")
    ax.set_ylim(0, max(s[1] + s[2] for s in suites) * 1.3)
    ax.legend(frameon=False, loc="upper right")
    plt.setp(ax.get_xticklabels(), fontsize=8)
    save(fig, "tests_by_suite.png")
    # 7 backend coverage by package
    cov = load("backend_coverage.json")["files"]
    groups = {}
    for p, v in cov.items():
        k = p.replace("\\", "/")
        g = "routers" if "/routers/" in k else "services" if "/services/" in k else "core (models, auth, deps, config)"
        s = v["summary"]
        a = groups.setdefault(g, [0, 0])
        a[0] += s["covered_lines"]; a[1] += s["num_statements"]
    items = sorted(((g, 100 * c / n) for g, (c, n) in groups.items()), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    ax.barh([i[0] for i in items], [i[1] for i in items], color=INK, height=0.5)
    for i, (g, v) in enumerate(items):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=9)
    ax.set_xlim(0, 110); ax.set_xlabel("Statement coverage (%)")
    ax.set_title("Backend coverage by package (pytest-cov)", loc="left", fontsize=11, fontweight="bold")
    save(fig, "backend_coverage.png")
    # 8 TARA generator + validation quick view
    ev = b["evaluation"]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    kv = [("Validation pass rate", ev["validation"]["pass_rate"]), ("Query success rate", ev["query_success"]["success_rate"]), ("Conflict precision", cd["automated"]["precision"]), ("Conflict recall", cd["automated"]["recall"])]
    ax.barh([k for k, _ in kv][::-1], [v for _, v in kv][::-1], color=ACCENT, height=0.5)
    for i, (k, v) in enumerate(kv[::-1]):
        ax.text(min(v + 0.01, 1.0), i, f"{v:.1%}", va="center", fontsize=9)
    ax.set_xlim(0, 1.12); ax.set_title("Quality rates from the Evaluation module", loc="left", fontsize=11, fontweight="bold")
    save(fig, "evaluation_rates.png")


if __name__ == "__main__":
    main()
