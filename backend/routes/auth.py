"""
backend/routes/auth.py
------------------------
Authentication endpoints backed by the PostgreSQL User model.

Endpoints
─────────
POST /auth/signup  — create a new employee account (role is always "employee")
POST /auth/login   — verify credentials, set an HttpOnly session cookie
POST /auth/logout  — clear the session cookie
GET  /auth/me       — return the currently authenticated user

Sessions are JWTs carried in an HttpOnly cookie (see app/security.py). Tokens
are never returned in a JSON body and never stored in localStorage, so a
compromised XSS payload cannot exfiltrate the session.

Every account created through /auth/signup defaults to the "employee" role.
There is intentionally no way to request "admin" through this endpoint —
admin accounts are provisioned out-of-band via scripts/create_admin.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user
from app.security import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SECURE,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)
from db.database import get_db
from db.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    """Payload for POST /auth/signup. Role is never accepted here."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_session_cookie(response: Response, user: User) -> None:
    token = create_access_token(user_id=user.id, role=user.role.value)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new employee account",
)
async def signup(payload: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)) -> UserResponse:
    """
    Register a new user.

    Always creates the account with role="employee" — there is no field a
    caller can set to request "admin". Returns 400 if the email is already
    registered. On success, also logs the user in (sets the session cookie).
    """
    existing = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.employee,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    _set_session_cookie(response, user)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Authenticate and start a session",
)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> UserResponse:
    """Verify credentials and set an HttpOnly session cookie. Returns 401 on failure."""
    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()

    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This account has been deactivated.")

    _set_session_cookie(response, user)
    return UserResponse.model_validate(user)


@router.post("/logout", response_model=MessageResponse, summary="End the current session")
async def logout(response: Response) -> MessageResponse:
    """Clear the session cookie. Always succeeds, even if not logged in."""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserResponse, summary="Get the current authenticated user")
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the profile of the currently authenticated user. Returns 401 if not logged in."""
    return UserResponse.model_validate(user)
