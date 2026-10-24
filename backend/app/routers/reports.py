import re

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require
from ..errors import BadRequest, NotFound
from ..models import Dashboard, User
from ..services import reports as rp
from ..services.audit import audit

router = APIRouter(prefix="/reports", tags=["reports"])

MEDIA = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get("/{kind}")
def export(kind: str, request: Request, format: str = "csv", dashboard_id: str | None = None, user: User = Depends(require("report.export")), db: Session = Depends(get_db)):
    if format not in MEDIA:
        raise BadRequest("format must be csv, xlsx or pdf")
    if kind == "metrics":
        rep = rp.metrics_report(db, user)
    elif kind == "conflicts":
        rep = rp.conflicts_report(db, user)
    elif kind == "evaluation":
        if user.role == "business_user":
            raise BadRequest("Evaluation exports are not available for your role")
        rep = rp.evaluation_report(db, user)
    elif kind == "dashboard":
        d = db.get(Dashboard, dashboard_id or "")
        if not d or d.workspace_id != user.workspace_id:
            raise NotFound("Dashboard")
        rep = rp.dashboard_report(db, user, d)
    else:
        raise NotFound("Report")
    body = {"csv": rp.to_csv, "xlsx": rp.to_xlsx, "pdf": rp.to_pdf}[format](rep)
    audit(db, user, "report.export", "report", None, {"kind": kind, "format": format, "rows": len(rep[2])}, request)
    db.commit()
    fname = re.sub(r"[^A-Za-z0-9_-]+", "_", rep[0]).strip("_").lower()
    return Response(body, media_type=MEDIA[format], headers={"Content-Disposition": f'attachment; filename="{fname}.{format}"', "X-Row-Count": str(len(rep[2]))})
