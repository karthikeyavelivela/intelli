"""Verifies the PostgreSQL and MySQL connectors against REAL servers (isolated throwaway instances):
connection creation (credentials encrypted), test, table listing, chunked read-only import, query on the imported dataset,
and that the source session really is read-only. Writes docs/data/connections_verification.json.

Env: PG_URL=postgresql://user:pw@127.0.0.1:5544/db   MYSQL_URL=mysql://root:@127.0.0.1:3399/db"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
_tmp = tempfile.mkdtemp(prefix="im_conn_")
os.environ.update(ENV="test", DATABASE_URL=f"sqlite:///{_tmp}/c.db", DATA_DIR=f"{_tmp}/datasets", RATE_LIMIT_ENABLED="false", USE_CELERY="false", AI_PROVIDER="none", SECRET_KEY="conn-secret-conn-secret-1234567890")

import pymysql  # noqa: E402
import psycopg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Connection  # noqa: E402
from app.services import ingest  # noqa: E402

H = {"X-Requested-With": "IntelliMetrics"}
N = 30000


def seed_pg(u):
    with psycopg.connect(host=u.hostname, port=u.port, dbname=u.path[1:], user=u.username, password=u.password, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS sample_orders")
        c.execute("CREATE TABLE sample_orders (order_id serial primary key, order_date date, state text, amount numeric(12,2), paid boolean)")
        c.execute(f"INSERT INTO sample_orders (order_date, state, amount, paid) SELECT date '2025-04-01' + mod(g, 400), (ARRAY['Maharashtra','Delhi','Karnataka','Telangana','Tamil Nadu'])[1 + mod(g, 5)], mod(g, 977) * 13.5, mod(g, 7) <> 0 FROM generate_series(1, {N}) g")


def seed_mysql(u):
    c = pymysql.connect(host=u.hostname, port=u.port, user=u.username, password=u.password or "", autocommit=True)
    cur = c.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS im_verify")
    cur.execute("USE im_verify")
    cur.execute("DROP TABLE IF EXISTS sample_orders")
    cur.execute("CREATE TABLE sample_orders (order_id int primary key auto_increment, order_date date, state varchar(40), amount decimal(12,2))")
    rows = [(f"2025-{1 + (i % 12):02d}-{1 + (i % 28):02d}", ["Gujarat", "Kerala", "Bihar", "Assam", "Punjab"][i % 5], (i % 977) * 13.5) for i in range(N)]
    cur.executemany("INSERT INTO sample_orders (order_date, state, amount) VALUES (%s, %s, %s)", rows)
    c.close()


def check(client, kind, u, dbname, table):
    t0 = time.perf_counter()
    r = client.post("/api/connections", json={"name": f"{kind} verify", "kind": kind, "host": u.hostname, "port": u.port, "database": dbname, "username": u.username, "password": u.password or ""})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["password"] == "********"
    with SessionLocal() as db:
        enc = db.get(Connection, cid).password_enc
        assert enc and (not u.password or u.password not in enc)  # stored Fernet-encrypted (never plaintext)
        conn = db.get(Connection, cid)
        # the session used for reads must refuse writes
        c = ingest._open(conn)
        try:
            cur = c.cursor()
            cur.execute("CREATE TABLE should_fail (x int)")
            c.commit()
            ro = False
        except Exception as e:  # noqa: BLE001
            ro = True
            err = str(e).splitlines()[0][:120]
        finally:
            try:
                c.rollback()
            except Exception:  # noqa: BLE001
                pass
            c.close()
    assert ro, "source session is NOT read-only"
    tst = client.post(f"/api/connections/{cid}/test").json()
    assert tst["ok"], tst
    tables = client.get(f"/api/connections/{cid}/tables").json()["items"]
    assert any(t["table"] == "sample_orders" for t in tables), tables
    imp = client.post(f"/api/connections/{cid}/import", json={"table": table, "name": f"{kind}_sample_orders"})
    assert imp.status_code == 202, imp.text
    did = imp.json()["dataset"]["id"]
    while True:
        st = client.get(f"/api/datasets/{did}/status").json()
        if st["status"] in ("ready", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "ready" and st["row_count"] == N, st
    q = client.post("/api/execution/run", json={"dataset_id": did, "formula": "COUNT(*)"}).json()
    assert q["rows"][0][0] == N
    s = client.post("/api/execution/run", json={"dataset_id": did, "formula": "SUM(amount)", "dimensions": [{"column": "state"}], "order": "value_desc"}).json()
    return {"kind": kind, "server_version": None, "tables_listed": len(tables), "rows_imported": st["row_count"], "import_job_ms": client.get(f"/api/datasets/{did}/jobs").json()["items"][0]["duration_ms"],
            "password_encrypted_at_rest": True, "write_attempt_rejected_by_readonly_session": err, "groups_returned": len(s["rows"]), "wall_ms": round((time.perf_counter() - t0) * 1000)}


def main():
    Base.metadata.create_all(engine)
    c = TestClient(app, headers=H)
    r = c.post("/api/auth/register", json={"name": "Conn Verify", "email": "conn.verify@example.com", "password": "Passw0rd!x1", "workspace_name": "Connection Verification"})
    assert r.status_code == 201, r.text
    out = []
    pg = urlparse(os.environ["PG_URL"])
    seed_pg(pg)
    out.append(check(c, "postgres", pg, pg.path[1:], "public.sample_orders"))
    my = urlparse(os.environ["MYSQL_URL"])
    seed_mysql(my)
    out.append(check(c, "mysql", my, "im_verify", "sample_orders"))
    with psycopg.connect(host=pg.hostname, port=pg.port, dbname=pg.path[1:], user=pg.username, password=pg.password) as pc:
        out[0]["server_version"] = pc.execute("show server_version").fetchone()[0]
    mc = pymysql.connect(host=my.hostname, port=my.port, user=my.username, password=my.password or "")
    cur = mc.cursor()
    cur.execute("select version()")
    out[1]["server_version"] = cur.fetchone()[0]
    mc.close()
    (ROOT / "docs" / "data" / "connections_verification.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
