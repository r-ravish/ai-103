"""
Enterprise Knowledge Agent — FastAPI application entry point.

Endpoints:
  GET  /health  – liveness check
  POST /chat    – ask the persisted Foundry agent a question; returns a
                  grounded answer with citation metadata.
                  Both the user question and the agent answer are screened
                  by Azure AI Content Safety before any data leaves this
                  service (when credentials are configured).

Run locally:
    cd backend
    uvicorn app.main:app --reload

Content Safety configuration (optional — see backend/.env.example):
    AZURE_CONTENT_SAFETY_ENDPOINT           — enables live screening
    AZURE_CONTENT_SAFETY_API_KEY            — API key (never commit)
    AZURE_CONTENT_SAFETY_SEVERITY_THRESHOLD — default 2 (Low/strict)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.content_safety import ContentSafetyClient
from app.foundry_agent import FoundryAgentService
from routes.tickets import router as tickets_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service instances — created once at startup, released at shutdown.
# ---------------------------------------------------------------------------
foundry_service: FoundryAgentService | None = None
content_safety_client: ContentSafetyClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise shared resources on startup; release them on shutdown."""
    global foundry_service, content_safety_client

    logger.info("Startup: initialising ContentSafetyClient")
    content_safety_client = ContentSafetyClient()

    logger.info("Startup: initialising FoundryAgentService")
    foundry_service = FoundryAgentService()

    yield

    if foundry_service is not None:
        logger.info("Shutdown: closing FoundryAgentService")
        foundry_service.close()
        foundry_service = None

    content_safety_client = None
    logger.info("Shutdown: ContentSafetyClient released")


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

app.include_router(tickets_router)


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
    escalation_required: bool = Field(
        default=False,
        description=(
            "True when the agent could not find sufficient grounded evidence and the "
            "question should be escalated to a human reviewer."
        ),
    )
    escalation_reason: str | None = Field(
        default=None,
        description="Machine-readable reason for escalation (e.g. 'knowledge_gap'), or None.",
    )
    action_taken: bool = Field(
        default=False,
        description="True when a backend action (e.g. ticket creation) was successfully performed.",
    )
    action_type: str | None = Field(
        default=None,
        description="Type of backend action performed (e.g. 'escalation'), or None.",
    )
    ticket_id: str | None = Field(
        default=None,
        description="Support ticket ID created during escalation, or None.",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness check — returns 200 OK when the server is running."""
    cs_mode = "live" if (content_safety_client and content_safety_client.is_live) else "passthrough"
    return {"status": "ok", "content_safety": cs_mode}


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    """
    Answer an employee question using the persisted Foundry agent.

    The agent searches the Azure AI Search knowledge base and synthesises a
    grounded answer. Source-document citations are included in the response.

    Content Safety screening:
      1. User input is screened before being sent to Foundry.
         Blocked inputs receive a 400 response with a safe refusal message.
      2. The agent's answer is screened before being returned to the user.
         Blocked outputs are replaced with a safe refusal message.
    """
    if foundry_service is None:
        raise HTTPException(
            status_code=503,
            detail="Foundry agent service is not initialised.",
        )

    # ── Step 1: Screen the user's input ─────────────────────────────────────
    if content_safety_client is not None:
        input_result = content_safety_client.screen_text(request.question)
        if input_result.blocked:
            logger.warning(
                "Content Safety blocked user input: %s", input_result.reason
            )
            raise HTTPException(
                status_code=400,
                detail=input_result.safe_response,
            )

    # ── Step 2: Call the Foundry agent ───────────────────────────────────────
    try:
        result = foundry_service.ask(request.question)
    except Exception as exc:
        logger.exception("Error calling Foundry agent")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {exc}",
        ) from exc

    # ── Step 3: Screen the agent's output ────────────────────────────────────
    if content_safety_client is not None:
        output_result = content_safety_client.screen_text(result["answer"])
        if output_result.blocked:
            logger.warning(
                "Content Safety blocked agent output: %s", output_result.reason
            )
            # Return the safe refusal message; suppress the raw LLM output.
            return ChatResponse(
                answer=output_result.safe_response,
                citations=[],
                escalation_required=False,
                escalation_reason=None,
                action_taken=False,
                action_type=None,
                ticket_id=None,
            )

    return ChatResponse(
        answer=result["answer"],
        citations=[Citation(**c) for c in result.get("citations", [])],
        escalation_required=result.get("escalation_required", False),
        escalation_reason=result.get("escalation_reason"),
        action_taken=result.get("action_taken", False),
        action_type=result.get("action_type"),
        ticket_id=result.get("ticket_id"),
    )
