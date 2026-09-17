"""
Enterprise Knowledge Agent — FastAPI application entry point.

Day 2 work (feature/agent-core) adds POST /chat here.
This stub exists so the project has a runnable FastAPI app foundation
to branch from before agent-core development begins.

Run locally:
    cd backend
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

app = FastAPI(
    title="Enterprise Knowledge Agent API",
    description=(
        "Internal knowledge-base agent powered by Azure AI Foundry and Azure AI Search. "
        "Provides grounded, citation-backed answers to employee policy questions."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness check. Returns 200 when the server is running."""
    return {"status": "ok"}
