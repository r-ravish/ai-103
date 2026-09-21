"""
backend/app/security.py
------------------------
Password hashing and JWT session-token helpers for the auth layer.

Passwords are hashed with argon2 (via argon2-cffi) — the OWASP-recommended
default for new applications. Sessions are represented as short-lived JWTs
carried in an HttpOnly cookie (see routes/auth.py); tokens are never stored
in localStorage or returned in a JSON body.

Environment variables (see backend/.env.example):
    JWT_SECRET_KEY              -- HMAC signing secret (required in production)
    JWT_ALGORITHM                -- default "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES -- default 60 * 24 (24h)
    AUTH_COOKIE_SECURE           -- "true" to require HTTPS for the cookie
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from dotenv import load_dotenv

load_dotenv()

# ── Password hashing ─────────────────────────────────────────────────────────

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage in User.password_hash."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if *plain_password* matches the stored *password_hash*."""
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ── JWT session tokens ───────────────────────────────────────────────────────

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-insecure-secret-change-me")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))

AUTH_COOKIE_NAME = "access_token"
AUTH_COOKIE_SECURE: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"


def create_access_token(*, user_id: int, role: str, expires_minutes: int | None = None) -> str:
    """Create a signed JWT encoding the user's id and role."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes if expires_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT. Returns None if invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
