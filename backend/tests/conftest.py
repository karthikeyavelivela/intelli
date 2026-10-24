import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="im_test_")
os.environ.update(
    ENV="test", DATABASE_URL=os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db"), DATA_DIR=f"{_tmp}/datasets", RATE_LIMIT_ENABLED="false",
    AI_PROVIDER="none", OPENAI_API_KEY="", GEMINI_API_KEY="", USE_CELERY="false", SECRET_KEY="test-secret-key-test-secret-key-1234",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

HEADERS = {"X-Requested-With": "IntelliMetrics"}
CREDS = {
    "admin": ("admin@intellimetrics.demo", "Admin@12345"),
    "analyst": ("analyst@intellimetrics.demo", "Analyst@12345"),
    "business": ("business@intellimetrics.demo", "Business@12345"),
    "reviewer": ("reviewer@intellimetrics.demo", "Reviewer@12345"),
    "other_admin": ("admin@sagarfoods.demo", "Admin@12345"),
}


@pytest.fixture(scope="session", autouse=True)
def seeded():
    if not os.environ.get("TEST_SKIP_CREATE_ALL"):  # Postgres CI applies Alembic migrations instead
        Base.metadata.create_all(engine)
    from app.seed import seed_all

    seed_all()
    yield


def _client(email: str, pw: str) -> TestClient:
    c = TestClient(app, headers=HEADERS)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture(scope="session")
def anon():
    return TestClient(app, headers=HEADERS)


@pytest.fixture(scope="session")
def clients(seeded):
    return {k: _client(*v) for k, v in CREDS.items()}


@pytest.fixture(scope="session")
def admin(clients):
    return clients["admin"]


@pytest.fixture(scope="session")
def analyst(clients):
    return clients["analyst"]


@pytest.fixture(scope="session")
def business(clients):
    return clients["business"]


@pytest.fixture(scope="session")
def reviewer(clients):
    return clients["reviewer"]


@pytest.fixture(scope="session")
def other(clients):
    return clients["other_admin"]


def find_metric(client, name, department=None, status=None):
    items = client.get("/api/metrics", params={"q": name, "page_size": 100}).json()["items"]
    for m in items:
        if m["name"] == name and (department is None or m["department"] == department) and (status is None or m["status"] == status):
            return m
    raise AssertionError(f"metric {name}/{department} not found")


def sales_dataset(client):
    return next(d for d in client.get("/api/datasets").json()["items"] if d["name"] == "sales_transactions")
