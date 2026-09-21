"""
backend/tests/conftest.py
---------------------------
Shared pytest fixtures for the FastAPI test suite.

* Sets dummy environment variables *before* anything under app/ or
  routes/ is imported, since a couple of modules (ingest_pilot_documents.py)
  read required Azure env vars at import time.
* Swaps the production PostgreSQL engine for an in-memory async SQLite
  engine (aiosqlite) via a `get_db` dependency override, so tests never
  need a real database.
* Provides a `client` fixture (a plain, non-lifespan TestClient) plus a
  couple of small helpers for creating users and logging in.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# ── Dummy env vars needed at import time (must run before any app import) ──
os.environ.setdefault("AZURE_SEARCH_ENDPOINT", "https://example-search.search.windows.net")
os.environ.setdefault("AZURE_SEARCH_ADMIN_KEY", "test-search-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://example-openai.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("AUTH_COOKIE_SECURE", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from db.database import get_db
from db.models import Base

# ── In-memory async SQLite engine shared across a test session ─────────────
_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = async_sessionmaker(bind=_test_engine, class_=AsyncSession, expire_on_commit=False)


def run_async(coro):
    """Run an async coroutine to completion from sync test code."""
    import asyncio

    return asyncio.run(coro)


async def _override_get_db():
    async with _TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Create all tables once for the test session (SQLite in-memory)."""

    async def _create():
        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    run_async(_create())
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all tables between tests so they stay isolated."""

    async def _wipe():
        async with _test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())

    yield
    run_async(_wipe())


@pytest.fixture()
def app():
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def db_sessionmaker():
    """Expose the test session factory so tests can set up/inspect rows directly."""
    return _TestSessionLocal


@pytest.fixture()
def client(app):
    # Plain TestClient (no `with`) -> lifespan is never triggered, so
    # FoundryAgentService (which requires real Azure Foundry credentials)
    # is never constructed.
    return TestClient(app)
