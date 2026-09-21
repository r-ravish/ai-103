"""
backend/scripts/create_admin.py
---------------------------------
Controlled, out-of-band way to create the initial admin account(s).

There is intentionally NO way to self-register as admin through
POST /auth/signup — every signup defaults to role="employee". Admin
accounts must be provisioned by someone with direct database/shell access
running this script.

Usage (from backend/, with the venv active and .env configured):

    python scripts/create_admin.py --name "Jane Admin" --email jane@company.com

    # Password can be passed via --password, or omitted to prompt securely,
    # or provided via the ADMIN_PASSWORD environment variable (useful for
    # non-interactive provisioning, e.g. a deployment script / CI job).

If a user with the given email already exists, this script promotes them
to role="admin" instead of creating a duplicate account.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv

load_dotenv(os.path.join(_BACKEND, ".env"))


async def create_admin(name: str, email: str, password: str) -> None:
    from sqlalchemy import select

    from app.security import hash_password
    from db.database import AsyncSessionLocal
    from db.models import User, UserRole

    async with AsyncSessionLocal() as session:
        existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

        if existing is not None:
            existing.role = UserRole.admin
            existing.password_hash = hash_password(password)
            existing.is_active = True
            await session.commit()
            print(f"[create_admin] Existing user {email!r} promoted to admin.")
            return

        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.admin,
        )
        session.add(user)
        await session.commit()
        print(f"[create_admin] Admin account created for {email!r} (id={user.id}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an admin account.")
    parser.add_argument("--name", required=True, help="Display name for the admin account.")
    parser.add_argument("--email", required=True, help="Login email for the admin account.")
    parser.add_argument(
        "--password",
        default=None,
        help="Password (avoid passing on the CLI in shared shells; prefer the prompt or ADMIN_PASSWORD env var).",
    )
    args = parser.parse_args()

    password = args.password or os.getenv("ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("[create_admin] Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(create_admin(args.name, args.email, password))


if __name__ == "__main__":
    main()
