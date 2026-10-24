import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import HEADERS, find_metric, sales_dataset


def test_login_wrong_password_and_envelope(anon):
    r = anon.post("/api/auth/login", json={"email": "admin@intellimetrics.demo", "password": "nope-nope1"})
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "invalid_credentials" and err["request_id"]


def test_requires_auth(anon):
    for url in ("/api/metrics", "/api/datasets", "/api/overview", "/api/conflicts", "/api/dashboards", "/api/admin/audit-logs"):
        assert TestClient(app).get(url).status_code == 401, url


def test_cookie_flags_and_refresh_rotation():
    c = TestClient(app, headers=HEADERS)
    r = c.post("/api/auth/login", json={"email": "analyst@intellimetrics.demo", "password": "Analyst@12345"})
    sc = " ".join(r.headers.get_list("set-cookie")).lower()
    assert "httponly" in sc and "access_token" in sc and "refresh_token" in sc
    old = c.cookies.get("refresh_token")
    assert c.post("/api/auth/refresh").status_code == 200
    # old refresh token is revoked after rotation
    c2 = TestClient(app, headers=HEADERS)
    c2.cookies.set("refresh_token", old, path="/api/auth")
    assert c2.post("/api/auth/refresh").status_code == 401
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_csrf_header_required_for_cookie_mutations():
    c = TestClient(app)  # no X-Requested-With
    c.post("/api/auth/login", json={"email": "analyst@intellimetrics.demo", "password": "Analyst@12345"})
    r = c.post("/api/conflicts/detect")
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf"


def test_register_creates_isolated_workspace(anon):
    c = TestClient(app, headers=HEADERS)
    r = c.post("/api/auth/register", json={"name": "New Person", "email": "new.person@example.com", "password": "Passw0rd!x", "workspace_name": "Fresh Co"})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "admin"
    assert c.get("/api/metrics").json()["total"] == 0 and c.get("/api/datasets").json()["total"] == 0
    assert c.post("/api/auth/register", json={"name": "Dup", "email": "new.person@example.com", "password": "Passw0rd!x", "workspace_name": "X Co"}).status_code == 409
    weak = TestClient(app, headers=HEADERS).post("/api/auth/register", json={"name": "Weak", "email": "weak@example.com", "password": "12345678", "workspace_name": "Weak Co"})
    assert weak.status_code == 400


def test_forgot_and_reset_password_flow():
    c = TestClient(app, headers=HEADERS)
    c.post("/api/auth/register", json={"name": "Reset Me", "email": "reset.me@example.com", "password": "Passw0rd!x", "workspace_name": "Reset Co"})
    anon2 = TestClient(app, headers=HEADERS)
    r = anon2.post("/api/auth/forgot-password", json={"email": "reset.me@example.com"})
    assert r.status_code == 200 and "dev_reset_link" in r.json()  # dev-only helper
    token = r.json()["dev_reset_link"].split("token=")[1]
    assert anon2.post("/api/auth/reset-password", json={"token": token, "password": "BrandN3wPass"}).status_code == 200
    assert anon2.post("/api/auth/reset-password", json={"token": token, "password": "BrandN3wPass2"}).status_code == 400  # single use
    assert anon2.post("/api/auth/login", json={"email": "reset.me@example.com", "password": "BrandN3wPass"}).status_code == 200
    # unknown email gives the same 200 with no link
    r2 = anon2.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r2.status_code == 200 and "dev_reset_link" not in r2.json()


# ------------------------------------------------------------------ RBAC
@pytest.mark.parametrize(
    "who,method,url,expected",
    [
        ("business", "post", "/api/metrics", 403),
        ("business", "post", "/api/conflicts/detect", 403),
        ("business", "post", "/api/ai/generate-metric", 403),
        ("business", "post", "/api/evaluation/run", 403),
        ("business", "get", "/api/admin/audit-logs", 403),
        ("business", "get", "/api/users", 200),
        ("business", "post", "/api/users", 403),
        ("analyst", "post", "/api/users", 403),
        ("analyst", "get", "/api/admin/audit-logs", 403),
        ("analyst", "put", "/api/workspaces/current/settings", 403),
        ("reviewer", "post", "/api/datasets/upload", 403),
        ("reviewer", "post", "/api/metrics", 403),
        ("reviewer", "post", "/api/evaluation/run", 403),
        ("reviewer", "get", "/api/evaluation/latest", 200),
        ("admin", "get", "/api/admin/audit-logs", 200),
        ("admin", "get", "/api/admin/api-usage", 200),
    ],
)
def test_rbac_matrix(clients, who, method, url, expected):
    c = clients[who]
    kwargs = {"json": {}} if method in ("post", "put") else {}
    r = getattr(c, method)(url, **kwargs)
    assert r.status_code == expected, (who, url, r.status_code, r.text[:200])


def test_reviewer_cannot_write_but_can_approve(reviewer, analyst):
    m = analyst.post("/api/metrics", json={"name": "RBAC Probe", "formula": "SUM(quantity)", "dataset_id": sales_dataset(analyst)["id"], "unit": "units"}).json()
    assert reviewer.patch(f"/api/metrics/{m['id']}", json={"description": "x"}).status_code == 403
    assert analyst.post(f"/api/metrics/{m['id']}/approve", json={}).status_code == 403
    assert analyst.post(f"/api/metrics/{m['id']}/submit", json={}).status_code == 200
    assert analyst.post(f"/api/metrics/{m['id']}/approve", json={}).status_code == 403
    assert reviewer.post(f"/api/metrics/{m['id']}/reject", json={}).status_code == 400  # comment required
    assert reviewer.post(f"/api/metrics/{m['id']}/reject", json={"comment": "needs docs"}).json()["status"] == "draft"


# ------------------------------------------------------------------ workspace isolation
def test_workspace_isolation(admin, other):
    sales = sales_dataset(admin)
    rev = find_metric(admin, "Revenue", "Sales", "published")
    # direct object access across workspaces looks like "not found", never leaks
    assert other.get(f"/api/datasets/{sales['id']}").status_code == 404
    assert other.get(f"/api/datasets/{sales['id']}/preview").status_code == 404
    assert other.get(f"/api/metrics/{rev['id']}").status_code == 404
    assert other.get(f"/api/metrics/{rev['id']}/versions").status_code == 404
    assert other.post("/api/execution/run", json={"dataset_id": sales["id"], "formula": "SUM(net_sales)"}).status_code == 404
    assert other.post("/api/validation/formula", json={"dataset_id": sales["id"], "formula": "SUM(net_sales)"}).status_code == 404
    assert other.delete(f"/api/datasets/{sales['id']}").status_code == 404
    # lists only contain own data
    assert {d["name"] for d in other.get("/api/datasets").json()["items"]} == {"distributor_dispatches"}
    names = {m["name"] for m in other.get("/api/metrics", params={"page_size": 100}).json()["items"]}
    assert "Revenue" not in names and "Dispatches" in names
    # cannot create a metric on another workspace's dataset
    r = other.post("/api/metrics", json={"name": "Steal", "formula": "SUM(net_sales)", "dataset_id": sales["id"]})
    assert r.status_code in (400, 404)
    # users, audit logs, conversations
    assert all(u["email"].endswith("sagarfoods.demo") for u in other.get("/api/users").json()["items"])
    assert all("intellimetrics.demo" not in (a["user_email"] or "") for a in other.get("/api/admin/audit-logs", params={"page_size": 200}).json()["items"])
    # TARA in workspace B cannot see workspace A metrics
    a = other.post("/api/chat/ask", json={"question": "What was revenue by month last quarter?"}).json()
    assert a["kind"] == "unsupported"


def test_cannot_deactivate_self_or_cross_workspace_user(admin, other):
    me = admin.get("/api/auth/me").json()["user"]
    assert admin.patch(f"/api/users/{me['id']}", json={"role": "business_user"}).status_code == 403
    victim = next(u for u in admin.get("/api/users").json()["items"] if u["role"] == "business_user")
    assert other.patch(f"/api/users/{victim['id']}", json={"is_active": False}).status_code == 404
