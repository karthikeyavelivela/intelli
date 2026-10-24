from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, Notification, User
from ..logging_setup import request_id_var


def audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
    request: Request | None = None,
    workspace_id: str | None = None,
) -> AuditLog:
    row = AuditLog(
        workspace_id=workspace_id or (user.workspace_id if user else None),
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip=(request.client.host if request and request.client else None),
        request_id=request_id_var.get(),
    )
    db.add(row)
    return row


def notify(
    db: Session,
    workspace_id: str,
    title: str,
    body: str | None = None,
    kind: str = "info",
    link: str | None = None,
    user_id: str | None = None,
) -> Notification:
    n = Notification(workspace_id=workspace_id, user_id=user_id, title=title[:200], body=body, kind=kind, link=(link or None) and link[:300], read_by=[])
    db.add(n)
    return n
