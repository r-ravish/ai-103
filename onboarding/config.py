"""
onboarding/config.py
--------------------
Centralised configuration for the onboarding module.

All values are read from environment variables (or a .env file via python-dotenv).
No secrets are stored in source code.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the onboarding directory first, then fall back to
# the backend/.env so a single .env file covers the whole project.
_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env", override=False)
load_dotenv(_here.parent / "backend" / ".env", override=False)


def _require(name: str) -> str:
    """Return env var *name* or raise a clear RuntimeError if it is missing."""
    val = os.getenv(name)
    if not val or val.startswith("<"):
        raise RuntimeError(
            f"Required environment variable '{name}' is missing or still contains "
            "a placeholder.  Copy onboarding/.env.example to onboarding/.env and "
            "fill in your values."
        )
    return val


# ── Azure AI Search ──────────────────────────────────────────────────────────
AZURE_SEARCH_ENDPOINT: str = _require("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_ADMIN_KEY: str = _require("AZURE_SEARCH_ADMIN_KEY")
SEARCH_INDEX_NAME: str = os.getenv("SEARCH_INDEX_NAME", "enterprise-knowledge-index")

# ── Azure OpenAI (embedding) — Korea Central ─────────────────────────────────
AZURE_OPENAI_ENDPOINT: str = _require("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY: str = _require("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
)
EMBEDDING_DIMENSIONS: int = 1536  # fixed by text-embedding-3-small

# ── Azure AI Document Intelligence ───────────────────────────────────────────
# Optional: only required when uploading PDFs.
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str | None = os.getenv(
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
)
AZURE_DOCUMENT_INTELLIGENCE_KEY: str | None = os.getenv(
    "AZURE_DOCUMENT_INTELLIGENCE_KEY"
)

# ── Chunking policy (mirrors ingestion-contract.md) ─────────────────────────
MAX_TOKENS_PER_CHUNK: int = int(os.getenv("MAX_TOKENS_PER_CHUNK", "500"))
OVERLAP_TOKENS: int = int(os.getenv("OVERLAP_TOKENS", "60"))
EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "16"))
UPLOAD_BATCH_SIZE: int = int(os.getenv("UPLOAD_BATCH_SIZE", "100"))

# ── Allowed upload file types ────────────────────────────────────────────────
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".md", ".txt", ".docx"}
)
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
