import time
from collections import defaultdict, deque

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .errors import AppError, Forbidden
from .models import User
from .permissions import role_can
from .security import decode_access_token

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "IntelliMetrics"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if not token:
        raise AppError(401, "unauthorized", "Not authenticated")
    data = decode_access_token(token)
    if not data:
        raise AppError(401, "token_expired", "Session expired")
    # CSRF defence for cookie-authenticated mutating requests (SameSite=Lax + custom header)
    if (
        request.method not in SAFE_METHODS
        and request.cookies.get("access_token")
        and request.headers.get(CSRF_HEADER) != CSRF_VALUE
    ):
        raise AppError(403, "csrf", "Missing CSRF header")
    user = db.get(User, data["sub"])
    if not user or not user.is_active:
        raise AppError(401, "unauthorized", "Account disabled or missing")
    request.state.user = user
    return user


def require(cap: str):
    """Dependency factory: enforce a capability. Every router endpoint depends on current_user or require()."""

    def _dep(user: User = Depends(current_user)) -> User:
        if not role_can(user.role, cap):
            raise Forbidden(f"Role '{user.role}' lacks capability '{cap}'")
        return user

    _dep.required_cap = cap  # introspected by docs/tools/api_reference.py to document who may call each endpoint
    return _dep


# ---- naive in-memory sliding-window rate limiter (per process; use Redis/Nginx limits in multi-instance prod)
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(bucket: str, limit: int | None = None, window: int = 60):
    def _dep(request: Request):
        if not settings.RATE_LIMIT_ENABLED or settings.ENV == "test":
            return
        lim = limit or settings.AUTH_RATE_LIMIT
        ip = request.client.host if request.client else "?"
        key = f"{bucket}:{ip}"
        now = time.monotonic()
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= lim:
            raise AppError(429, "rate_limited", "Too many requests, slow down")
        q.append(now)

    return _dep


def paginate(page: int, page_size: int, max_size: int = 200) -> tuple[int, int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), max_size)
    return page, page_size, (page - 1) * page_size
