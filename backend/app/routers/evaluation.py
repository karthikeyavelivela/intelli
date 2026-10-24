from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require
from ..errors import NotFound
from ..models import EvaluationRun, User
from ..services.audit import audit
from ..services.evaluation import load_cases, run_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def r_out(r: EvaluationRun) -> dict:
    return {"id": r.id, "results": r.results, "duration_ms": r.duration_ms, "created_at": r.created_at.isoformat()}


@router.post("/run")
def run(request: Request, user: User = Depends(require("evaluation.run")), db: Session = Depends(get_db)):
    r = run_evaluation(db, user)
    audit(db, user, "evaluation.run", "evaluation", r.id, {"ms": r.duration_ms}, request)
    db.commit()
    return r_out(r)


@router.get("/runs")
def runs(user: User = Depends(require("evaluation.view")), db: Session = Depends(get_db)):
    rows = db.scalars(select(EvaluationRun).where(EvaluationRun.workspace_id == user.workspace_id).order_by(EvaluationRun.created_at.desc()).limit(30)).all()
    out = []
    for r in rows:
        x = r.results
        out.append({
            "id": r.id, "created_at": r.created_at.isoformat(), "duration_ms": r.duration_ms,
            "precision": x["conflict_detection"]["automated"]["precision"], "recall": x["conflict_detection"]["automated"]["recall"],
            "validation_pass_rate": x["validation"]["pass_rate"], "query_success_rate": x["query_success"]["success_rate"],
            "dashboard_avg_ms": x["dashboard_load"]["avg_ms"], "query_avg_ms": x["query_latency"]["benchmark_avg_ms"],
            "ai_acceptance": x["ai_acceptance"]["acceptance_rate"], "processing_avg_ms": x["dataset_processing"]["avg_ms"],
        })
    return {"items": list(reversed(out))}


@router.get("/latest")
def latest(user: User = Depends(require("evaluation.view")), db: Session = Depends(get_db)):
    r = db.scalar(select(EvaluationRun).where(EvaluationRun.workspace_id == user.workspace_id).order_by(EvaluationRun.created_at.desc()).limit(1))
    return {"run": r_out(r) if r else None}


@router.get("/runs/{rid}")
def get_run(rid: str, user: User = Depends(require("evaluation.view")), db: Session = Depends(get_db)):
    r = db.get(EvaluationRun, rid)
    if not r or r.workspace_id != user.workspace_id:
        raise NotFound("Evaluation run")
    return r_out(r)


@router.get("/cases")
def cases(user: User = Depends(require("evaluation.view"))):
    return {"items": load_cases()}
