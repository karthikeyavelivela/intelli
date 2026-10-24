import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user, paginate, require
from ..errors import AppError, BadRequest, Conflict, NotFound
from ..models import Connection, Dataset, IngestionJob, Metric, User
from ..security import encrypt_secret
from ..services import ingest as ing
from ..services.audit import audit
from ..services.engine import connect_parquet, to_jsonable
from ..services.jobs import enqueue_ingestion

router = APIRouter(tags=["datasets"])


def ds_out(d: Dataset, detail: bool = False) -> dict:
    o = {
        "id": d.id, "name": d.name, "description": d.description, "source_type": d.source_type, "file_format": d.file_format,
        "original_filename": d.original_filename, "size_bytes": d.size_bytes, "row_count": d.row_count, "column_count": d.column_count,
        "status": d.status, "progress": d.progress, "stage": d.stage, "error": d.error, "date_column": d.date_column,
        "is_demo": d.is_demo, "source_table": d.source_table, "connection_id": d.connection_id,
        "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat(),
        "completeness_pct": (d.profile or {}).get("completeness_pct"), "duplicate_rows": (d.profile or {}).get("duplicate_rows"),
    }
    if detail:
        o["schema"] = d.schema_json
        o["profile"] = d.profile
    return o


def _get(db: Session, user: User, dataset_id: str) -> Dataset:
    d = db.get(Dataset, dataset_id)
    if not d or d.workspace_id != user.workspace_id:  # workspace isolation: 404, never 403, to avoid leaking existence
        raise NotFound("Dataset")
    return d


def _start_job(db: Session, d: Dataset, user: User) -> IngestionJob:
    job = IngestionJob(workspace_id=d.workspace_id, dataset_id=d.id, status="queued", stage="queued", progress=0)
    d.status, d.progress, d.stage, d.error = "pending", 0, "queued", None
    db.add(job)
    db.commit()
    runner = enqueue_ingestion(d.id, job.id)
    job.runner = runner.split(":")[0]
    db.commit()
    return job


@router.get("/datasets")
def list_datasets(
    q: str | None = None, status: str | None = None, source_type: str | None = None, sort: str = "-created_at",
    page: int = 1, page_size: int = 24, user: User = Depends(current_user), db: Session = Depends(get_db),
):
    page, page_size, off = paginate(page, page_size)
    stmt = select(Dataset).where(Dataset.workspace_id == user.workspace_id)
    if q:
        stmt = stmt.where(Dataset.name.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Dataset.status == status)
    if source_type:
        stmt = stmt.where(Dataset.source_type == source_type)
    col = {"created_at": Dataset.created_at, "name": Dataset.name, "row_count": Dataset.row_count, "size": Dataset.size_bytes}.get(sort.lstrip("-"), Dataset.created_at)
    stmt = stmt.order_by(col.desc() if sort.startswith("-") else col.asc())
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset(off).limit(page_size)).all()
    return {"items": [ds_out(d) for d in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/datasets/upload", status_code=202)
async def upload_dataset(
    request: Request, file: UploadFile = File(...), name: str | None = Form(None), description: str | None = Form(None),
    user: User = Depends(require("dataset.write")), db: Session = Depends(get_db),
):
    try:
        fmt = ing.detect_format(file.filename or "")
    except ing.IngestError as e:
        raise BadRequest(str(e))
    ds_id = uuid.uuid4().hex
    raw_dir = ing.dataset_dir(user.workspace_id) / "raw"
    raw_dir.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "upload").name)[:120]
    raw_path = raw_dir / f"{ds_id}_{safe}"
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    with open(raw_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):  # streamed to disk in 1 MiB chunks, never fully in memory
            size += len(chunk)
            if size > limit:
                out.close()
                raw_path.unlink(missing_ok=True)
                raise AppError(413, "file_too_large", f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit")
            out.write(chunk)
    try:
        ing.sniff_file(raw_path, fmt)
    except ing.IngestError as e:
        raw_path.unlink(missing_ok=True)
        raise BadRequest(str(e))
    d = Dataset(
        id=ds_id, workspace_id=user.workspace_id, name=(name or Path(safe).stem).strip()[:200], description=description,
        source_type="file", file_format=fmt, original_filename=file.filename, raw_path=str(raw_path), size_bytes=size,
        status="pending", created_by=user.id,
    )
    db.add(d)
    audit(db, user, "dataset.upload", "dataset", d.id, {"name": d.name, "format": fmt, "bytes": size}, request)
    db.flush()
    job = _start_job(db, d, user)
    return {"dataset": ds_out(d), "job_id": job.id}


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, dataset_id)
    used = db.scalars(select(Metric).where(Metric.workspace_id == user.workspace_id, Metric.dataset_id == d.id)).all()
    return {**ds_out(d, True), "metrics": [{"id": m.id, "name": m.name, "status": m.status} for m in used]}


@router.get("/datasets/{dataset_id}/status")
def dataset_status(dataset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, dataset_id)
    return {"id": d.id, "status": d.status, "progress": d.progress, "stage": d.stage, "error": d.error, "row_count": d.row_count}


@router.get("/datasets/{dataset_id}/preview")
def preview(dataset_id: str, page: int = 1, page_size: int = 25, sort: str | None = None, desc: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, dataset_id)
    if d.status != "ready":
        raise Conflict("Dataset is not ready yet")
    page, page_size, off = paginate(page, page_size, 200)
    names = {c["name"] for c in d.schema_json}
    con = connect_parquet(d.parquet_path)
    try:
        order = ""
        if sort:
            if sort not in names:
                raise BadRequest("Unknown sort column")
            order = f' ORDER BY "{sort}" {"DESC" if desc else "ASC"} NULLS LAST'
        cur = con.execute(f"SELECT * FROM data{order} LIMIT {page_size} OFFSET {off}")
        cols = [c[0] for c in cur.description]
        rows = [[to_jsonable(v) for v in r] for r in cur.fetchall()]
    finally:
        con.close()
    return {"columns": cols, "rows": rows, "total": d.row_count, "page": page, "page_size": page_size}


@router.get("/datasets/{dataset_id}/jobs")
def dataset_jobs(dataset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, user, dataset_id)
    jobs = db.scalars(select(IngestionJob).where(IngestionJob.dataset_id == d.id).order_by(IngestionJob.created_at.desc()).limit(20)).all()
    return {"items": [
        {"id": j.id, "status": j.status, "stage": j.stage, "progress": j.progress, "rows": j.rows, "bytes": j.bytes, "duration_ms": j.duration_ms,
         "runner": j.runner, "error_report": j.error_report, "created_at": j.created_at.isoformat(), "finished_at": j.finished_at.isoformat() if j.finished_at else None}
        for j in jobs
    ]}


@router.post("/datasets/{dataset_id}/reprocess", status_code=202)
def reprocess(dataset_id: str, request: Request, user: User = Depends(require("dataset.write")), db: Session = Depends(get_db)):
    d = _get(db, user, dataset_id)
    if d.source_type == "seed":
        raise Conflict("Seeded demo datasets cannot be reprocessed")
    job = _start_job(db, d, user)
    audit(db, user, "dataset.reprocess", "dataset", d.id, {}, request)
    db.commit()
    return {"job_id": job.id}


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, request: Request, user: User = Depends(require("dataset.delete")), db: Session = Depends(get_db)):
    d = _get(db, user, dataset_id)
    in_use = db.scalar(select(func.count()).select_from(Metric).where(Metric.dataset_id == d.id, Metric.status != "deprecated"))
    if in_use:
        raise Conflict(f"{in_use} active metric(s) use this dataset; deprecate them first")
    for p in (d.parquet_path, d.raw_path):
        if p:
            Path(p).unlink(missing_ok=True)
    for j in db.scalars(select(IngestionJob).where(IngestionJob.dataset_id == d.id)).all():
        db.delete(j)
    audit(db, user, "dataset.delete", "dataset", d.id, {"name": d.name}, request)
    db.delete(d)
    db.commit()
    return {"ok": True}


# ----------------------------------------------------------------------------- connections
class ConnIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: str = Field(pattern="^(postgres|mysql)$")
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1, max_length=160)
    username: str = Field(min_length=1, max_length=160)
    password: str = Field(max_length=300)


class ImportIn(BaseModel):
    table: str = Field(min_length=1, max_length=200)
    name: str | None = None


def conn_out(c: Connection) -> dict:
    return {"id": c.id, "name": c.name, "kind": c.kind, "host": c.host, "port": c.port, "database": c.database, "username": c.username,
            "last_status": c.last_status, "last_error": c.last_error, "last_tested_at": c.last_tested_at.isoformat() if c.last_tested_at else None,
            "created_at": c.created_at.isoformat(), "password": "********"}


def _conn(db: Session, user: User, cid: str) -> Connection:
    c = db.get(Connection, cid)
    if not c or c.workspace_id != user.workspace_id:
        raise NotFound("Connection")
    return c


@router.get("/connections")
def list_connections(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Connection).where(Connection.workspace_id == user.workspace_id).order_by(Connection.created_at.desc())).all()
    return {"items": [conn_out(c) for c in rows]}


@router.post("/connections", status_code=201)
def create_connection(body: ConnIn, request: Request, user: User = Depends(require("dataset.write")), db: Session = Depends(get_db)):
    c = Connection(
        workspace_id=user.workspace_id, name=body.name, kind=body.kind, host=body.host, port=body.port, database=body.database,
        username=body.username, password_enc=encrypt_secret(body.password), created_by=user.id,
    )
    db.add(c)
    db.flush()
    audit(db, user, "connection.create", "connection", c.id, {"name": c.name, "kind": c.kind, "host": c.host}, request)  # never log the password
    db.commit()
    return conn_out(c)


@router.post("/connections/{cid}/test")
def test_conn(cid: str, user: User = Depends(require("dataset.write")), db: Session = Depends(get_db)):
    from ..models import utcnow

    c = _conn(db, user, cid)
    ok, msg = ing.test_connection(c)
    c.last_status, c.last_error, c.last_tested_at = ("ok" if ok else "failed"), (None if ok else msg), utcnow()
    db.commit()
    return {"ok": ok, "message": msg}


@router.get("/connections/{cid}/tables")
def conn_tables(cid: str, user: User = Depends(require("dataset.write")), db: Session = Depends(get_db)):
    c = _conn(db, user, cid)
    try:
        return {"items": ing.list_tables(c)}
    except Exception as e:  # noqa: BLE001
        raise AppError(502, "connection_failed", f"Could not list tables: {str(e).splitlines()[0][:200]}")


@router.post("/connections/{cid}/import", status_code=202)
def conn_import(cid: str, body: ImportIn, request: Request, user: User = Depends(require("dataset.write")), db: Session = Depends(get_db)):
    c = _conn(db, user, cid)
    parts = body.table.split(".")
    if not 1 <= len(parts) <= 2 or not all(ing.IDENT_RE.match(p) for p in parts):
        raise BadRequest("Invalid table name")
    d = Dataset(
        workspace_id=user.workspace_id, name=(body.name or body.table)[:200], source_type=c.kind, file_format=c.kind, connection_id=c.id,
        source_table=body.table, created_by=user.id, description=f"Imported read-only from {c.name}",
    )
    db.add(d)
    audit(db, user, "connection.import", "dataset", d.id, {"connection": c.name, "table": body.table}, request)
    db.flush()
    job = _start_job(db, d, user)
    return {"dataset": ds_out(d), "job_id": job.id}


@router.delete("/connections/{cid}")
def delete_conn(cid: str, request: Request, user: User = Depends(require("dataset.delete")), db: Session = Depends(get_db)):
    c = _conn(db, user, cid)
    for d in db.scalars(select(Dataset).where(Dataset.connection_id == c.id)).all():
        d.connection_id = None
    audit(db, user, "connection.delete", "connection", c.id, {"name": c.name}, request)
    db.delete(c)
    db.commit()
    return {"ok": True}
