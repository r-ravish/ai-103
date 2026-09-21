"""
# backend/db/seed.py
-------------------
Connectivity check and table-creation script.

Run from the backend/ directory with the venv active:
    python db/seed.py

This script:
    1. Connects to the database using DATABASE_URL from .env.
    2. Creates all ORM-declared tables (idempotent — safe to re-run).
    3. Prints a summary of tables found in the database.

NOT a substitute for Alembic migrations in production.
Use `alembic upgrade head` to apply proper versioned migrations.
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

# Resolve backend/ as sys.path root so db imports work
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

load_dotenv(os.path.join(_BACKEND, ".env"))


async def main() -> None:
    from db.database import create_all_tables, sync_engine
    from db.models import Base  # noqa: F401 — ensure models are registered

    print("[seed] Connecting to database …")
    print(f"[seed] URL: {sync_engine.url!r}")

    # ── Create tables ─────────────────────────────────────────────────────────
    print("[seed] Creating tables (create_all — idempotent) …")
    await create_all_tables()
    print("[seed] Tables created OK.")

    # ── Verify using sync engine ───────────────────────────────────────────────
    from sqlalchemy import inspect, text

    with sync_engine.connect() as conn:
        inspector = inspect(conn)
        tables = sorted(inspector.get_table_names())
        print(f"[seed] Tables found in database ({len(tables)}):" )
        for t in tables:
            cols = [c["name"] for c in inspector.get_columns(t)]
            print(f"  {t}: {cols}")

        # Quick sanity query
        for table in ["users", "documents", "tickets", "feedback", "escalation_events"]:
            if table in tables:
                row = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table}: {row} rows")
            else:
                print(f"  WARNING: {table!r} not found!")

    print("[seed] Done — database is ready.")


if __name__ == "__main__":
    asyncio.run(main())
