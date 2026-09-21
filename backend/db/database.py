"""
backend/db/database.py
-----------------------
Async SQLAlchemy 2.0 engine and session configuration.

Environment variables (add to backend/.env):
    DATABASE_URL -- async connection string (asyncpg driver)
    SYNC_DATABASE_URL -- sync string for Alembic/scripts (psycopg2, auto-derived if omitted)
    SQLALCHEMY_ECHO  -- set to true to log all SQL
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

load_dotenv()

# ── Connection URLs ───────────────────────────────────────────────────────────

_ASYNC_DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ai103:ai103dev@localhost:5432/ai103_enterprise",
)

# Alembic and seed scripts need a sync driver. Auto-derive if not set.
_SYNC_DATABASE_URL: str = os.getenv(
    "SYNC_DATABASE_URL",
    _ASYNC_DATABASE_URL
    .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    .replace("postgresql://", "postgresql+psycopg2://"),
)

_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"

# ── Async engine (FastAPI) ───────────────────────────────────────────────────

engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=_ECHO,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── Sync engine (Alembic / scripts only) ────────────────────────────────────

sync_engine = create_engine(
    _SYNC_DATABASE_URL,
    pool_pre_ping=True,
    echo=_ECHO,
)


# ── FastAPI dependency ───────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a transactional async session.

    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)):
            db.add(MyModel(...))
            await db.commit()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Table creation helper (tests / seed script) ──────────────────────────────

async def create_all_tables() -> None:
    """Create all ORM tables. Supplement to Alembic; use for tests/dev only."""
    from db.models import Base  # noqa: PLC0415 (local import avoids circular deps)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
