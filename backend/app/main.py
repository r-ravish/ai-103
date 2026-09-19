"""
Enterprise Knowledge Agent — FastAPI application entry point.

Endpoints:
  GET  /health  – liveness check
  POST /chat    – ask the persisted Foundry agent a question; returns a
                  grounded answer with citation metadata.

Run locally:
    cd backend
    uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.foundry_agent import FoundryAgentService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service instance — created once at startup, released at shutdown.
# ---------------------------------------------------------------------------
foundry_service: FoundryAgentService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise shared resources on startup; release them on shutdown."""
    global foundry_service

    logger.info("Startup: initialising FoundryAgentService")
    foundry_service = FoundryAgentService()

    yield

    if foundry_service is not None:
        logger.info("Shutdown: closing FoundryAgentService")
        foundry_service.close()
        foundry_service = None


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Enterprise Knowledge Agent API",
    description=(
        "Internal knowledge-base agent powered by Microsoft Foundry "
        "and Azure AI Search. Provides grounded, citation-backed answers "
        "to employee policy questions."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    """Body for POST /chat."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        examples=["What is the work-from-home policy?"],
        description="The employee's question to the knowledge-base agent.",
    )


class Citation(BaseModel):
    """Metadata for a single source document used in the answer."""

    document_id: str
    title: str
    source_file: str


class ChatResponse(BaseModel):
    """Response body for POST /chat."""

    answer: str = Field(description="Grounded plain-text answer from the agent.")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Source documents the agent retrieved to produce the answer.",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness check — returns 200 OK when the server is running."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    """
    Answer an employee question using the persisted Foundry agent.

    The agent searches the Azure AI Search knowledge base and synthesises a
    grounded answer. Source-document citations are included in the response.
    """
    if foundry_service is None:
        raise HTTPException(
            status_code=503,
            detail="Foundry agent service is not initialised.",
        )

    try:
        result = foundry_service.ask(request.question)

        return ChatResponse(
            answer=result["answer"],
            citations=[Citation(**c) for c in result.get("citations", [])],
        )

    except Exception as exc:
        logger.exception("Error calling Foundry agent")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {exc}",
        ) from exc
