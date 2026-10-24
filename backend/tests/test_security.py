"""Security-focused tests: rate limiting, token tampering, secret leakage, path traversal, injection in query parameters."""
import time
from pathlib import Path

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.security import create_access_token
from conftest import HEADERS


def test_auth_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT", 5)
    from app import deps

    deps._hits.clear()
    c = TestClient(app, headers=HEADERS)
    codes = [c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong-pass1"}).status_code for _ in range(8)]
    assert codes[:5] == [401] * 5
    assert 429 in codes[5:] and codes[-1] == 429
    deps._hits.clear()


def test_tampered_expired_and_foreign_tokens_are_rejected(analyst):
    me = analyst.get("/api/auth/me").json()["user"]
    good = create_access_token(me["id"], me["workspace"]["id"], me["role"])
    c = TestClient(app)
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {good}"}).status_code == 200
    # tampered payload / wrong signature
    bad_sig = jwt.encode({"sub": me["id"], "type": "access", "exp": int(time.time()) + 600}, "not-the-server-secret", algorithm="HS256")
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {bad_sig}"}).status_code == 401
    # expired
    expired = jwt.encode({"sub": me["id"], "type": "access", "exp": int(time.time()) - 5}, settings.SECRET_KEY, algorithm="HS256")
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    # refresh token used as an access token
    refresh_like = jwt.encode({"sub": me["id"], "type": "refresh", "exp": int(time.time()) + 600}, settings.SECRET_KEY, algorithm="HS256")
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh_like}"}).status_code == 401
    # alg=none
    forged = jwt.encode({"sub": me["id"], "type": "access"}, "", algorithm="none")
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_no_secret_material_in_api_responses(admin, analyst):
    blob = " ".join([admin.get("/api/users").text, admin.get("/api/auth/me").text, admin.get("/api/connections").text, admin.get("/api/workspaces/current/settings").text])
    for needle in ("password_hash", "argon2", "$argon2", "password_enc", settings.SECRET_KEY, "OPENAI_API_KEY"):
        assert needle not in blob


def test_sql_metacharacters_in_query_parameters_are_inert(admin):
    for q in ("' OR 1=1 --", "'; DROP TABLE metrics; --", "%' UNION SELECT password_hash FROM users --", "\" OR \"\"=\""):
        r = admin.get("/api/metrics", params={"q": q})
        assert r.status_code == 200 and r.json()["total"] == 0
        assert admin.get("/api/datasets", params={"q": q}).status_code == 200
        assert admin.get("/api/conflicts", params={"q": q}).status_code == 200
    assert admin.get("/api/metrics").json()["total"] >= 8  # tables intact


def test_upload_filename_cannot_escape_the_storage_directory(analyst):
    r = analyst.post("/api/datasets/upload", files={"file": ("../../../evil name.csv", b"a,b\n1,2\n3,4\n", "text/csv")})
    assert r.status_code == 202
    from app.db import SessionLocal
    from app.models import Dataset

    with SessionLocal() as db:
        d = db.get(Dataset, r.json()["dataset"]["id"])
        raw = Path(d.raw_path).resolve()
        root = Path(settings.DATA_DIR).resolve()
        assert root in raw.parents and ".." not in raw.name and "/" not in raw.name


def test_mass_assignment_and_role_escalation_blocked(analyst, business):
    me = business.get("/api/auth/me").json()["user"]
    assert business.patch("/api/auth/me", json={"role": "admin", "is_active": True, "workspace_id": "x"}).json()["user"]["role"] == "business_user"
    assert business.patch(f"/api/users/{me['id']}", json={"role": "admin"}).status_code == 403
    assert analyst.post("/api/users", json={"email": "evil@example.com", "name": "Evil", "role": "admin"}).status_code == 403


def test_error_responses_do_not_leak_internals(anon):
    r = anon.get("/api/datasets/not-a-real-id")
    assert r.status_code == 401
    r = TestClient(app, headers=HEADERS).post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert r.status_code == 422 and "Traceback" not in r.text and "sqlalchemy" not in r.text.lower()
