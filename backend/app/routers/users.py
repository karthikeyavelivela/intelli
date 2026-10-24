import secrets

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require
from ..errors import BadRequest, Conflict, Forbidden, NotFound
from ..models import RefreshToken, User
from ..permissions import ROLES, ROLE_LABELS
from ..security import hash_password
from ..services.audit import audit, notify

router = APIRouter(prefix="/users", tags=["users"])


class UserIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    role: str
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: str | None = None
    is_active: bool | None = None


def out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "role": u.role, "role_label": ROLE_LABELS[u.role],
        "is_active": u.is_active, "is_demo": u.is_demo, "title": u.title,
        "last_login": u.last_login.isoformat() if u.last_login else None, "created_at": u.created_at.isoformat(),
    }


@router.get("")
def list_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Any member can see teammates (needed for owner/assignee pickers); mutations are admin-only."""
    rows = db.scalars(select(User).where(User.workspace_id == user.workspace_id).order_by(User.created_at)).all()
    return {"items": [out(u) for u in rows]}


@router.post("", status_code=201)
def invite_user(body: UserIn, request: Request, admin: User = Depends(require("user.manage")), db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise BadRequest(f"Role must be one of {', '.join(ROLES)}")
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise Conflict("A user with this email already exists")
    temp = body.password or secrets.token_urlsafe(9) + "a1"
    u = User(workspace_id=admin.workspace_id, email=body.email.lower(), name=body.name.strip(), role=body.role, password_hash=hash_password(temp))
    db.add(u)
    db.flush()
    audit(db, admin, "user.invite", "user", u.id, {"email": u.email, "role": u.role}, request)
    notify(db, admin.workspace_id, f"{u.name} joined as {ROLE_LABELS[u.role]}", None, "info", "/app/admin/users")
    db.commit()
    return {"user": out(u), "temporary_password": None if body.password else temp}


@router.patch("/{user_id}")
def patch_user(user_id: str, body: UserPatch, request: Request, admin: User = Depends(require("user.manage")), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.workspace_id != admin.workspace_id:
        raise NotFound("User")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in ROLES:
        raise BadRequest("Invalid role")
    if u.id == admin.id and (data.get("role", "admin") != "admin" or data.get("is_active") is False):
        raise Forbidden("You cannot demote or deactivate yourself")
    for k, v in data.items():
        setattr(u, k, v)
    if data.get("is_active") is False:
        for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == u.id)).all():
            t.revoked = True
    audit(db, admin, "user.update", "user", u.id, data, request)
    db.commit()
    return {"user": out(u)}


@router.delete("/{user_id}")
def remove_user(user_id: str, request: Request, admin: User = Depends(require("user.manage")), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.workspace_id != admin.workspace_id:
        raise NotFound("User")
    if u.id == admin.id:
        raise Forbidden("You cannot remove yourself")
    # soft remove: keeps audit/ownership references intact
    u.is_active = False
    u.email = f"removed+{u.id[:8]}@removed.invalid"
    for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == u.id)).all():
        t.revoked = True
    audit(db, admin, "user.remove", "user", u.id, {}, request)
    db.commit()
    return {"ok": True}
