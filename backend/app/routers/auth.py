import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user, rate_limit
from ..errors import AppError, BadRequest, Conflict
from ..models import PasswordReset, RefreshToken, User, Workspace, utcnow
from ..permissions import ROLE_LABELS, capabilities_for
from ..security import (
    clear_auth_cookies, create_access_token, hash_password, hash_token, new_opaque_token, set_auth_cookies,
    validate_password_strength, verify_password,
)
from ..services.audit import audit, notify
from ..services.engine import slugify

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("app.auth")


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    workspace_name: str = Field(min_length=2, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    title: str | None = Field(default=None, max_length=160)
    avatar_url: str | None = Field(default=None, max_length=500)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


def user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "role": u.role, "role_label": ROLE_LABELS[u.role],
        "workspace": {"id": u.workspace.id, "name": u.workspace.name, "is_demo": u.workspace.is_demo, "slug": u.workspace.slug},
        "capabilities": capabilities_for(u.role), "is_demo": u.is_demo, "title": u.title, "avatar_url": u.avatar_url,
        "created_at": u.created_at.isoformat(), "last_login": u.last_login.isoformat() if u.last_login else None,
    }


def _issue(db: Session, resp: Response, u: User) -> None:
    raw, hashed = new_opaque_token()
    db.add(RefreshToken(user_id=u.id, token_hash=hashed, expires_at=utcnow() + timedelta(days=settings.REFRESH_TTL_DAYS)))
    set_auth_cookies(resp, create_access_token(u.id, u.workspace_id, u.role), raw)


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit("register", 10))])
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    err = validate_password_strength(body.password)
    if err:
        raise BadRequest(err)
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise Conflict("An account with this email already exists")
    base = slugify(body.workspace_name)
    slug, i = base, 2
    while db.scalar(select(Workspace).where(Workspace.slug == slug)):
        slug, i = f"{base}-{i}", i + 1
    ws = Workspace(name=body.workspace_name.strip(), slug=slug, settings={})
    db.add(ws)
    db.flush()
    u = User(workspace_id=ws.id, email=body.email.lower(), name=body.name.strip(), password_hash=hash_password(body.password), role="admin")
    db.add(u)
    db.flush()
    u.workspace = ws
    audit(db, u, "auth.register", "user", u.id, {"workspace": ws.name}, request)
    notify(db, ws.id, "Welcome to IntelliMetrics AI", "TARA is ready. Upload a dataset to get started.", "info", "/app/datasets", user_id=u.id)
    _issue(db, response, u)
    db.commit()
    return {"user": user_out(u)}


@router.post("/login", dependencies=[Depends(rate_limit("login"))])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        audit(db, None, "auth.login_failed", "user", None, {"email": body.email.lower()}, request, workspace_id=u.workspace_id if u else None)
        db.commit()
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    u.last_login = utcnow()
    audit(db, u, "auth.login", "user", u.id, {}, request)
    _issue(db, response, u)
    db.commit()
    return {"user": user_out(u)}


@router.post("/refresh", dependencies=[Depends(rate_limit("refresh", 60))])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise AppError(401, "unauthorized", "No refresh token")
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if not row or row.revoked or row.expires_at < utcnow():
        clear_auth_cookies(response)
        raise AppError(401, "unauthorized", "Refresh token invalid or expired")
    u = db.get(User, row.user_id)
    if not u or not u.is_active:
        raise AppError(401, "unauthorized", "Account disabled")
    row.revoked = True  # rotation
    _issue(db, response, u)
    db.commit()
    return {"user": user_out(u)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get("refresh_token")
    if raw:
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
        if row:
            row.revoked = True
            db.commit()
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"user": user_out(user)}


@router.patch("/me")
def update_me(body: ProfileIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    audit(db, user, "user.update_profile", "user", user.id, body.model_dump(exclude_unset=True), request)
    db.commit()
    return {"user": user_out(user)}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.is_demo:
        raise AppError(403, "demo_locked", "Demo account passwords cannot be changed")
    if not verify_password(body.current_password, user.password_hash):
        raise BadRequest("Current password is incorrect")
    err = validate_password_strength(body.new_password)
    if err:
        raise BadRequest(err)
    user.password_hash = hash_password(body.new_password)
    for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))).all():
        t.revoked = True
    audit(db, user, "auth.change_password", "user", user.id, {}, request)
    db.commit()
    return {"ok": True}


@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot", 5))])
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Always returns 200 (no account enumeration). In development the reset link is logged and returned."""
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    out: dict = {"ok": True, "message": "If that email exists, a reset link has been sent."}
    if u and u.is_active:
        raw, hashed = new_opaque_token()
        db.add(PasswordReset(user_id=u.id, token_hash=hashed, expires_at=utcnow() + timedelta(hours=1)))
        audit(db, u, "auth.forgot_password", "user", u.id, {}, request)
        db.commit()
        link = f"{settings.FRONTEND_URL}/reset-password?token={raw}"
        log.warning("PASSWORD RESET LINK (dev only, no email provider configured): %s", link)
        if settings.is_dev:
            out["dev_reset_link"] = link
    return out


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset", 10))])
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    row = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_token(body.token)))
    if not row or row.used or row.expires_at < utcnow():
        raise BadRequest("Reset link is invalid or has expired")
    err = validate_password_strength(body.password)
    if err:
        raise BadRequest(err)
    u = db.get(User, row.user_id)
    if u.is_demo:
        raise AppError(403, "demo_locked", "Demo account passwords cannot be reset")
    u.password_hash = hash_password(body.password)
    row.used = True
    for t in db.scalars(select(RefreshToken).where(RefreshToken.user_id == u.id)).all():
        t.revoked = True
    audit(db, u, "auth.reset_password", "user", u.id, {}, request)
    db.commit()
    return {"ok": True}
