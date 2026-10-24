"""End-to-end check of the PRODUCTION job topology: API process -> Redis broker -> separate Celery worker -> Parquet + PostgreSQL.

Prerequisites (all supplied by docker compose in production; started manually in local verification):
  * PostgreSQL reachable at $VERIFY_DATABASE_URL with migrations applied (alembic upgrade head)
  * Redis reachable at $VERIFY_REDIS_URL
  * a worker running with the SAME env:   celery -A app.worker.celery_app worker --pool=solo
The script (API side, USE_CELERY=true) registers a throwaway user, uploads a 62,000-row CSV and asserts the job ran on the
'celery' runner. Writes docs/data/celery_verification.json."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(
    ENV="test", DATABASE_URL=os.environ["VERIFY_DATABASE_URL"], REDIS_URL=os.environ["VERIFY_REDIS_URL"], USE_CELERY="true",
    DATA_DIR=os.environ["VERIFY_DATA_DIR"], RATE_LIMIT_ENABLED="false", AI_PROVIDER="none", SECRET_KEY="verify-secret-verify-secret-123456",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed_data import gen_frames  # noqa: E402

H = {"X-Requested-With": "IntelliMetrics"}


def main() -> None:
    c = TestClient(app, headers=H)
    email = f"celery.verify.{int(time.time())}@example.com"
    r = c.post("/api/auth/register", json={"name": "Celery Verify", "email": email, "password": "Passw0rd!x1", "workspace_name": "Celery Verification"})
    assert r.status_code == 201, r.text
    csv_bytes = gen_frames()["sales_transactions"].write_csv().encode()
    t0 = time.perf_counter()
    up = c.post("/api/datasets/upload", files={"file": ("sales.csv", csv_bytes, "text/csv")})
    assert up.status_code == 202, up.text
    did = up.json()["dataset"]["id"]
    seen = set()
    while True:
        st = c.get(f"/api/datasets/{did}/status").json()
        seen.add((st["status"], st["stage"], st["progress"]))
        if st["status"] in ("ready", "failed"):
            break
        if time.perf_counter() - t0 > 300:
            raise TimeoutError("job did not finish: is the Celery worker running?")
        time.sleep(0.1)
    wall = (time.perf_counter() - t0) * 1000
    job = c.get(f"/api/datasets/{did}/jobs").json()["items"][0]
    out = {
        "status": st["status"], "rows": st["row_count"], "runner": job["runner"], "job_ms": job["duration_ms"], "upload_to_ready_ms": round(wall),
        "progress_states_seen": sorted(seen, key=lambda x: x[2]), "broker": os.environ["VERIFY_REDIS_URL"].split("@")[-1], "database": "PostgreSQL",
    }
    assert out["status"] == "ready" and out["rows"] == 62000 and out["runner"] == "celery", out
    run = c.post("/api/execution/run", json={"dataset_id": did, "formula": "SUM(net_sales)"})
    assert run.status_code == 200
    out["query_after_ingest_ms"] = run.json()["duration_ms"]
    (ROOT / "docs" / "data" / "celery_verification.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
