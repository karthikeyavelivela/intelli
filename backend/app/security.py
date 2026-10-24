import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet
from fastapi import Response

from .config import settings

_ph = PasswordHasher()


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(pw: str) -> str | None:
    if len(pw) < 8:
        return "Password must be at least 8 characters"
    if not any(c.isdigit() for c in pw) or not any(c.isalpha() for c in pw):
        return "Password must contain letters and digits"
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, workspace_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "ws": workspace_id,
        "role": role,
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.ACCESS_TTL_MIN),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data if data.get("type") == "access" else None


def new_opaque_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def set_auth_cookies(resp: Response, access: str, refresh: str) -> None:
    common = dict(httponly=True, secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE)
    resp.set_cookie("access_token", access, max_age=settings.ACCESS_TTL_MIN * 60, path="/", **common)
    resp.set_cookie("refresh_token", refresh, max_age=settings.REFRESH_TTL_DAYS * 86400, path="/api/auth", **common)


def clear_auth_cookies(resp: Response) -> None:
    resp.delete_cookie("access_token", path="/")
    resp.delete_cookie("refresh_token", path="/api/auth")


def _fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
