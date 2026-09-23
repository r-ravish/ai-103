"""
onboarding/main.py
------------------
Standalone FastAPI application for the onboarding module.

This file exists so the onboarding service can be run **independently**:

    cd onboarding
    uvicorn main:app --reload --port 8002

It can also be mounted onto the main backend FastAPI app by importing the
router directly:

    from onboarding.router import router as onboarding_router
    app.include_router(onboarding_router)

The standalone app is primarily useful for:
  • Local development and testing of the onboarding module in isolation.
  • Independent deployment as a separate Azure Container App or service.
  • Running the test suite without starting the full backend.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `from onboarding.xxx import ...` works
# whether this file is run as `python main.py` or `uvicorn main:app`.
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from onboarding.router import router as onboarding_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title="Enterprise Knowledge Agent — Onboarding Service",
    description=(
        "Document ingestion service for the Enterprise Knowledge Agent.\n\n"
        "Accepts document uploads, parses them (Markdown, PDF, DOCX, TXT), "
        "chunks the content using the structure-first chunking policy, generates "
        "embeddings via Azure OpenAI text-embedding-3-small, and indexes all "
        "chunks into enterprise-knowledge-index using the 11-field contract "
        "defined in docs/ingestion-contract.md."
    ),
    version="1.0.0",
    contact={
        "name": "Rakshit — Onboarding Module",
    },
    license_info={
        "name": "Internal project — not for public distribution",
    },
)

# Allow the frontend (localhost:3000) and main backend to call this service
# during local development.  Restrict origins appropriately in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding_router)


@app.get("/", tags=["root"])
def root() -> dict:
    """Service root — redirects to /docs for the interactive API explorer."""
    return {
        "service": "onboarding",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/onboarding/health",
    }
