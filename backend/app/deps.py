"""
backend/app/deps.py
---------------------
Reusable FastAPI dependencies for authentication and role-based access
control (RBAC).

Usage:
    @router.post("/chat")
    def chat(..., user: User = Depends(require_employee)):
        ...

    @router.post("/onboarding/upload")
    def upload(..., user: User = Depends(require_admin)):
        ...

Behavior (enforced here, never assumed from the frontend):
    * No/invalid/expired session cookie      -> 401 Unauthorized
    * Authenticated but wrong role for route -> 403 Forbidden
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import AUTH_COOKIE_NAME, decode_access_token
from db.database import get_db
from db.models import User, UserRole


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the authenticated user from the HttpOnly session cookie.

    Raises 401 when there is no session, the token is invalid/expired, or
    the user no longer exists / has been deactivated.
    """
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")

    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user, but returns None instead of raising 401."""
    if not request.cookies.get(AUTH_COOKIE_NAME):
        return None
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


def require_roles(*allowed_roles: UserRole):
    """
    Dependency factory: build a dependency that allows only the given roles.

    Always resolves the current user first (401 if unauthenticated), then
    checks the role (403 if authenticated but not permitted).
    """

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return user

    return _dependency


# Employees and admins may access employee-level routes (e.g. /chat).
require_employee = require_roles(UserRole.employee, UserRole.admin)

# Only admins may access admin-only routes (onboarding, dashboard/admin APIs).
require_admin = require_roles(UserRole.admin)
