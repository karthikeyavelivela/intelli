"""Dataset ingestion: validate -> convert to Parquet (streamed by DuckDB/Polars) -> schema -> profile.
Runs in a Celery worker (or a background thread in single-process dev mode). Never inside an HTTP request."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path

import duckdb
import polars as pl

from ..config import settings
from ..db import SessionLocal
from ..models import Connection, Dataset, IngestionJob, utcnow
from ..security import decrypt_secret
from .audit import notify
from .formula import categorize

log = logging.getLogger("app.ingest")

ALLOWED_EXT = {".csv": "csv", ".tsv": "csv", ".xlsx": "excel", ".xls": "excel", ".json": "json", ".jsonl": "json", ".ndjson": "json", ".parquet": "parquet"}
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class IngestError(Exception):
    pass


def dataset_dir(workspace_id: str) -> Path:
    p = Path(settings.DATA_DIR) / workspace_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def detect_format(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise IngestError(f"Unsupported file type '{ext}'. Allowed: CSV, TSV, Excel (.xlsx), JSON/JSONL, Parquet")
    return ALLOWED_EXT[ext]


def sniff_file(path: Path, fmt: str) -> None:
    """Cheap magic-byte validation so a renamed binary cannot masquerade as data."""
    with open(path, "rb") as f:
        head = f.read(8192)
    if not head:
        raise IngestError("File is empty")
    if fmt == "parquet" and not head.startswith(b"PAR1"):
        raise IngestError("Not a valid Parquet file (missing PAR1 header)")
    if fmt == "excel" and not (head.startswith(b"PK") or head.startswith(b"\xd0\xcf\x11\xe0")):
        raise IngestError("Not a valid Excel workbook")
    if fmt in ("csv", "json"):
        if b"\x00" in head:
            raise IngestError("File contains binary data and is not valid text")
        if fmt == "json" and head.lstrip()[:1] not in (b"[", b"{"):
            raise IngestError("JSON file must start with '[' or '{'")


def normalize_name(name: str, used: set[str]) -> str:
    n = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip()).strip("_").lower() or "col"
    if n[0].isdigit():
        n = "c_" + n
    base, i = n, 2
    while n in used:
        n = f"{base}_{i}"
        i += 1
    used.add(n)
    return n


def _sql_path(p: Path | str) -> str:
    return str(p).replace("\\", "/").replace("'", "''")


def _set(db, ds: Dataset, job: IngestionJob, stage: str, pct: int, **kw):
    ds.stage, ds.progress, job.stage, job.progress = stage, pct, stage, pct
    ds.status = "processing"
    job.status = "running"
    for k, v in kw.items():
        setattr(ds, k, v)
    db.commit()


def _convert(ds: Dataset, out: Path, errors: dict) -> None:
    raw = Path(ds.raw_path)
    fmt = ds.file_format
    con = duckdb.connect(":memory:")
    try:
        if fmt == "excel":
            import pandas as pd

            df = pd.read_excel(raw, engine="openpyxl")
            used: set[str] = set()
            df.columns = [normalize_name(c, used) for c in df.columns]
            pl.from_pandas(df).write_parquet(out, compression="zstd")
            return
        if fmt == "csv":
            delim = "\t" if raw.suffix.lower() == ".tsv" else None
            opts = "header=true, sample_size=50000, ignore_errors=true, store_rejects=true"
            if delim:
                opts += ", delim='\\t'"
            src = f"read_csv('{_sql_path(raw)}', {opts})"
        elif fmt == "json":
            src = f"read_json_auto('{_sql_path(raw)}', sample_size=50000, ignore_errors=true)"
        else:
            src = f"read_parquet('{_sql_path(raw)}')"
        desc = con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()
        used = set()
        sel = ", ".join(f'"{d[0].replace(chr(34), chr(34) * 2)}" AS "{normalize_name(d[0], used)}"' for d in desc)
        con.execute(f"COPY (SELECT {sel} FROM {src}) TO '{_sql_path(out)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        if fmt == "csv":
            try:
                rej = con.execute(
                    "SELECT line, column_name, error_type, csv_line FROM reject_errors LIMIT 200"
                ).fetchall()
                total = con.execute("SELECT count(*) FROM reject_errors").fetchone()[0]
                if total:
                    errors["rejected_rows"] = total
                    errors["samples"] = [
                        {"line": r[0], "column": r[1], "error": r[2], "content": (r[3] or "")[:200]} for r in rej[:50]
                    ]
            except duckdb.Error:
                pass
    finally:
        con.close()


def profile_parquet(path: str, row_count_hint: int | None = None) -> tuple[list[dict], dict, int, str | None]:
    """Returns (schema, profile, rows, date_column)."""
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"CREATE VIEW d AS SELECT * FROM read_parquet('{_sql_path(path)}')")
        desc = con.execute("DESCRIBE d").fetchall()
        schema = [{"name": r[0], "type": r[1], "category": categorize(r[1])} for r in desc]
        rows = con.execute("SELECT count(*) FROM d").fetchone()[0]
        aggs, order = [], []
        for c in schema[:200]:
            q = '"' + c["name"].replace('"', '""') + '"'
            parts = [f"count(*) - count({q})", f"approx_count_distinct({q})", f"CAST(min({q}) AS VARCHAR)", f"CAST(max({q}) AS VARCHAR)"]
            if c["category"] == "numeric":
                parts += [f"avg({q})", f"stddev_samp({q})"]
            else:
                parts += ["NULL", "NULL"]
            aggs += parts
            order.append(c)
        vals = con.execute("SELECT " + ", ".join(aggs) + " FROM d").fetchone() if aggs else []
        cols = []
        for i, c in enumerate(order):
            o = i * 6
            nulls, distinct, mn, mx, avg, std = vals[o : o + 6]
            entry = {
                **c,
                "nulls": int(nulls or 0),
                "null_pct": round((nulls or 0) * 100 / rows, 2) if rows else 0,
                "distinct": int(distinct or 0),
                "min": mn,
                "max": mx,
                "mean": round(float(avg), 4) if avg is not None else None,
                "std": round(float(std), 4) if std is not None else None,
            }
            if c["category"] == "string" and 0 < entry["distinct"] <= 5000:
                q = '"' + c["name"].replace('"', '""') + '"'
                top = con.execute(f"SELECT {q}, count(*) c FROM d WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 40").fetchall()
                entry["top_values"] = [{"value": str(t[0]), "count": int(t[1])} for t in top]
            cols.append(entry)
        dup = 0
        if rows and rows <= 20_000_000:
            uniq = con.execute("SELECT count(*) FROM (SELECT DISTINCT * FROM d)").fetchone()[0]
            dup = rows - uniq
        profile = {
            "total_rows": rows,
            "columns": cols,
            "duplicate_rows": dup,
            "duplicate_pct": round(dup * 100 / rows, 2) if rows else 0,
            "total_nulls": sum(c["nulls"] for c in cols),
            "completeness_pct": round(100 - (sum(c["nulls"] for c in cols) * 100 / (rows * len(cols))), 2) if rows and cols else 100,
            "profiled_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        date_cols = [c["name"] for c in schema if c["category"] == "date"]
        pref = [c for c in date_cols if "date" in c.lower()]
        date_col = (pref or date_cols or [None])[0]
        return schema, profile, rows, date_col
    finally:
        con.close()


def process_dataset(dataset_id: str, job_id: str, runner: str = "thread") -> None:
    db = SessionLocal()
    t0 = time.perf_counter()
    ds = db.get(Dataset, dataset_id)
    job = db.get(IngestionJob, job_id)
    if not ds or not job:
        db.close()
        return
    job.runner = runner
    errors: dict = {}
    try:
        _set(db, ds, job, "validating", 10)
        if ds.source_type == "file":
            if not ds.raw_path or not Path(ds.raw_path).exists():
                raise IngestError("Uploaded file not found on server")
            sniff_file(Path(ds.raw_path), ds.file_format or "")
            out = dataset_dir(ds.workspace_id) / f"{ds.id}.parquet"
            _set(db, ds, job, "converting to columnar format", 30)
            _convert(ds, out, errors)
            ds.parquet_path = str(out)
            job.bytes = Path(ds.raw_path).stat().st_size
        elif ds.source_type in ("postgres", "mysql"):
            out = dataset_dir(ds.workspace_id) / f"{ds.id}.parquet"
            _set(db, ds, job, "importing from source (read-only)", 30)
            conn = db.get(Connection, ds.connection_id)
            if not conn:
                raise IngestError("Connection no longer exists")
            import_table(conn, ds.source_table or "", out, lambda pct: _set(db, ds, job, "importing from source (read-only)", 30 + int(pct * 0.3)))
            ds.parquet_path = str(out)
            job.bytes = out.stat().st_size
        if not ds.parquet_path or not Path(ds.parquet_path).exists():
            raise IngestError("Conversion produced no output")
        _set(db, ds, job, "detecting schema & profiling columns", 65)
        schema, profile, rows, date_col = profile_parquet(ds.parquet_path)
        if rows == 0:
            raise IngestError("Dataset contains no rows")
        ds.schema_json, ds.profile, ds.row_count, ds.column_count, ds.date_column = schema, profile, rows, len(schema), date_col
        ds.size_bytes = Path(ds.parquet_path).stat().st_size
        ds.status, ds.progress, ds.stage, ds.error = "ready", 100, "complete", None
        job.status, job.progress, job.stage, job.rows = "succeeded", 100, "complete", rows
        job.error_report = errors
        job.duration_ms = int((time.perf_counter() - t0) * 1000)
        job.finished_at = utcnow()
        notify(db, ds.workspace_id, f"Dataset ready: {ds.name}", f"{rows:,} rows, {len(schema)} columns processed in {job.duration_ms/1000:.1f}s", "success", f"/app/datasets/{ds.id}", user_id=ds.created_by)
        db.commit()
    except Exception as e:  # noqa: BLE001
        log.exception("ingestion failed")
        db.rollback()
        ds = db.get(Dataset, dataset_id)
        job = db.get(IngestionJob, job_id)
        msg = str(e) if isinstance(e, IngestError) else f"Processing failed: {str(e).splitlines()[0][:300]}"
        ds.status, ds.error, ds.stage = "failed", msg, "failed"
        job.status, job.stage = "failed", "failed"
        job.error_report = {**errors, "fatal": msg}
        job.duration_ms = int((time.perf_counter() - t0) * 1000)
        job.finished_at = utcnow()
        notify(db, ds.workspace_id, f"Dataset failed: {ds.name}", msg, "error", f"/app/datasets/{ds.id}", user_id=ds.created_by)
        db.commit()
    finally:
        db.close()


# ----------------------------------------------------------------------------- external connections (read-only)
def _open(conn: Connection):
    pw = decrypt_secret(conn.password_enc)
    if conn.kind == "postgres":
        import psycopg

        c = psycopg.connect(
            host=conn.host, port=conn.port, dbname=conn.database, user=conn.username, password=pw,
            connect_timeout=8, options="-c default_transaction_read_only=on -c statement_timeout=600000",
        )
        c.read_only = True
        return c
    if conn.kind == "mysql":
        import pymysql

        c = pymysql.connect(host=conn.host, port=conn.port, database=conn.database, user=conn.username, password=pw, connect_timeout=8, read_timeout=600)
        with c.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
        return c
    raise IngestError(f"Unsupported connection kind {conn.kind}")


def test_connection(conn: Connection) -> tuple[bool, str]:
    try:
        c = _open(conn)
        cur = c.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        c.close()
        return True, "Connection successful (read-only session)"
    except Exception as e:  # noqa: BLE001
        return False, str(e).splitlines()[0][:300]


def list_tables(conn: Connection) -> list[dict]:
    c = _open(conn)
    try:
        cur = c.cursor()
        if conn.kind == "postgres":
            cur.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema') AND table_type IN ('BASE TABLE','VIEW') "
                "ORDER BY 1,2 LIMIT 500"
            )
        else:
            cur.execute(
                "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY 2 LIMIT 500"
            )
        return [{"schema": r[0], "table": r[1]} for r in cur.fetchall()]
    finally:
        c.close()


def import_table(conn: Connection, table: str, out: Path, progress, chunk: int = 50_000) -> int:
    """Stream a table in chunks into Parquet via PyArrow. Table name must be schema.table of safe identifiers."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    parts = table.split(".")
    if not 1 <= len(parts) <= 2 or not all(IDENT_RE.match(p) for p in parts):
        raise IngestError("Invalid table identifier")
    q = ".".join(f'"{p}"' if conn.kind == "postgres" else f"`{p}`" for p in parts)
    c = _open(conn)
    total, writer = 0, None
    try:
        cur = c.cursor(name="im_stream") if conn.kind == "postgres" else c.cursor()
        cur.execute(f"SELECT * FROM {q}")
        names = None
        while True:
            rows = cur.fetchmany(chunk)
            if not rows:
                break
            if names is None:
                names = [d[0] if isinstance(d, tuple) else d.name for d in cur.description]
                used: set[str] = set()
                names = [normalize_name(n, used) for n in names]
            df = pl.DataFrame(rows, schema=names, orient="row", infer_schema_length=len(rows), strict=False)
            tbl = df.to_arrow()
            if writer is None:
                writer = pq.ParquetWriter(str(out), tbl.schema, compression="zstd")
            else:
                tbl = tbl.cast(writer.schema, safe=False)
            writer.write_table(tbl)
            total += len(rows)
            progress(min(99, total // chunk * 10))
    finally:
        if writer:
            writer.close()
        c.close()
    if writer is None:
        raise IngestError("Source table returned no rows")
    return total
