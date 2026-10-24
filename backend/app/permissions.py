"""Single source of truth for RBAC. Frontend receives the resolved capability list from /auth/me."""

ROLES = ("admin", "data_analyst", "business_user", "reviewer")
ROLE_LABELS = {
    "admin": "Admin",
    "data_analyst": "Data Analyst",
    "business_user": "Business User",
    "reviewer": "Reviewer",
}

A, D, B, R = "admin", "data_analyst", "business_user", "reviewer"

CAPABILITIES: dict[str, tuple[str, set[str], str]] = {
    # key: (label, roles, group)
    "catalog.view": ("View metrics catalog, datasets, dashboards", {A, D, B, R}, "Read"),
    "dataset.write": ("Upload datasets / manage connections", {A, D}, "Data"),
    "dataset.delete": ("Delete datasets and connections", {A}, "Data"),
    "metric.write": ("Create and edit metrics", {A, D}, "Semantic layer"),
    "metric.review": ("Approve / reject / publish / deprecate metrics", {A, R}, "Semantic layer"),
    "metric.rollback": ("Roll back a metric (creates a new version)", {A, R}, "Semantic layer"),
    "ai.generate": ("Use TARA metric generator", {A, D}, "TARA"),
    "chat.ask": ("Ask TARA (natural-language BI)", {A, D, B, R}, "TARA"),
    "conflict.view": ("View conflicts", {A, D, R, B}, "Governance"),
    "conflict.detect": ("Run conflict detection", {A, D, R}, "Governance"),
    "conflict.manage": ("Assign / review / resolve conflicts", {A, R}, "Governance"),
    "formula.run": ("Formula Lab: validate and execute", {A, D, R}, "Analysis"),
    "dashboard.write": ("Create / edit dashboards", {A, D, B}, "Dashboards"),
    "evaluation.view": ("View performance evaluation", {A, D, R}, "Governance"),
    "evaluation.run": ("Run performance evaluation", {A, D}, "Governance"),
    "report.export": ("Export reports", {A, D, B, R}, "Reports"),
    "user.manage": ("Manage users and roles", {A}, "Admin"),
    "workspace.manage": ("Manage workspace and settings", {A}, "Admin"),
    "audit.view": ("View audit log", {A}, "Admin"),
}


def capabilities_for(role: str) -> list[str]:
    return sorted(k for k, (_, roles, _g) in CAPABILITIES.items() if role in roles)


def role_can(role: str, cap: str) -> bool:
    entry = CAPABILITIES.get(cap)
    return bool(entry and role in entry[1])


def matrix() -> list[dict]:
    return [
        {"capability": k, "label": label, "group": g, **{r: (r in roles) for r in ROLES}}
        for k, (label, roles, g) in CAPABILITIES.items()
    ]
