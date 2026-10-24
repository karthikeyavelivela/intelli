from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..db import get_db
from ..deps import current_user
from ..errors import NotFound
from ..models import AuditLog, Notification, User

router = APIRouter(tags=["notifications"])


def _visible(user: User):
    return (Notification.workspace_id == user.workspace_id) & or_(Notification.user_id.is_(None), Notification.user_id == user.id)


def _out(n: Notification, uid: str) -> dict:
    return {"id": n.id, "title": n.title, "body": n.body, "kind": n.kind, "link": n.link, "read": uid in (n.read_by or []), "created_at": n.created_at.isoformat()}


@router.get("/notifications")
def list_notifications(limit: int = 50, unread_only: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(_visible(user)).order_by(Notification.created_at.desc()).limit(min(limit, 200))).all()
    items = [_out(n, user.id) for n in rows]
    if unread_only:
        items = [i for i in items if not i["read"]]
    return {"items": items, "unread": sum(1 for n in rows if user.id not in (n.read_by or []))}


@router.post("/notifications/{nid}/read")
def mark_read(nid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.workspace_id != user.workspace_id:
        raise NotFound("Notification")
    if user.id not in (n.read_by or []):
        n.read_by = [*(n.read_by or []), user.id]
        flag_modified(n, "read_by")
        db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(_visible(user))).all():
        if user.id not in (n.read_by or []):
            n.read_by = [*(n.read_by or []), user.id]
            flag_modified(n, "read_by")
    db.commit()
    return {"ok": True}


@router.get("/activity")
def activity(limit: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Workspace activity feed (non-sensitive audit subset) visible to all members."""
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.workspace_id == user.workspace_id, ~AuditLog.action.like("auth.%"))
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 100))
    ).all()
    return {"items": [{"id": r.id, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "user_email": r.user_email, "details": {k: v for k, v in (r.details or {}).items() if k in ("name", "key", "version", "severity", "status")}, "created_at": r.created_at.isoformat()} for r in rows]}
