"""
onboarding/router.py
--------------------
FastAPI router exposing the document onboarding endpoints.

Endpoints
─────────
POST   /onboarding/upload                     — upload & ingest a document
GET    /onboarding/status/{document_id}       — ingestion status for one doc
GET    /onboarding/documents                  — list all ingested documents
DELETE /onboarding/documents/{document_id}    — remove a document from the index
GET    /onboarding/health                     — connectivity/configuration check

This router is designed to be mounted onto the existing FastAPI app
(backend/app/main.py) via:

    from onboarding.router import router as onboarding_router
    app.include_router(onboarding_router)

It never imports from backend/app/* — all coupling to the wider system is
strictly one-directional (backend mounts this router; this module does not
call back into backend code).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from onboarding import config
from onboarding.indexing import (
    delete_document_chunks,
    fetch_document_chunks,
    list_all_documents,
)
from onboarding.schemas import (
    DeleteResponse,
    DocumentRecord,
    IngestionStatus,
    ListResponse,
    OnboardingHealthResponse,
    StatusResponse,
    UploadResponse,
)
from onboarding.service import ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_upload(filename: str, size: int) -> None:
    """Raise HTTPException for invalid uploads before any processing begins."""
    suffix = Path(filename).suffix.lower()
    if suffix not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Accepted: {sorted(config.ALLOWED_EXTENSIONS)}"
            ),
        )
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if size > config.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds maximum upload size of {config.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload and ingest a document",
    description=(
        "Accepts a document file, parses it, chunks the content, generates "
        "embeddings, and indexes all chunks into enterprise-knowledge-index "
        "using the 11-field ingestion contract.\n\n"
        "Supported file types: `.pdf`, `.md`, `.txt`, `.docx`.\n\n"
        "PDFs are processed with Azure AI Document Intelligence when credentials "
        "are configured; pypdf is used as a fallback."
    ),
)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document to ingest.")],
    document_type: Annotated[
        str,
        Form(description="Logical type: 'policy', 'faq', 'ticket-data', etc."),
    ] = "policy",
    permission_tags: Annotated[
        str,
        Form(
            description=(
                "Comma-separated access groups, e.g. 'all-employees,hr'. "
                "Defaults to 'all-employees'."
            )
        ),
    ] = "all-employees",
    document_id: Annotated[
        str | None,
        Form(
            description=(
                "Optional stable document identifier.  Derived from filename if omitted."
            )
        ),
    ] = None,
    title: Annotated[
        str | None,
        Form(description="Optional human-readable title.  Derived from filename if omitted."),
    ] = None,
) -> UploadResponse:
    # ── Read file ────────────────────────────────────────────────────────────
    content = await file.read()
    filename = file.filename or "upload"

    _validate_upload(filename, len(content))

    # Parse permission_tags from comma-separated string
    tags: list[str] = [t.strip() for t in permission_tags.split(",") if t.strip()]
    if not tags:
        tags = ["all-employees"]

    logger.info(
        "Upload received: filename=%r size=%d bytes type=%r permissions=%s",
        filename,
        len(content),
        document_type,
        tags,
    )

    # ── Ingest ───────────────────────────────────────────────────────────────
    try:
        result = ingest_document(
            filename=filename,
            content=content,
            document_type=document_type,
            permission_tags=tags,
            document_id=document_id or None,
            title=title or None,
        )
    except ValueError as exc:
        logger.warning("Validation error during ingestion: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Ingestion pipeline error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during ingestion.")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during ingestion: {exc}",
        )

    return result


@router.get(
    "/status/{document_id}",
    response_model=StatusResponse,
    summary="Get ingestion status for a document",
    description=(
        "Returns the ingestion status and all indexed chunk metadata for the "
        "given document_id. Returns 404 if the document has not been ingested."
    ),
)
def get_status(document_id: str) -> StatusResponse:
    try:
        chunks = fetch_document_chunks(
            document_id=document_id,
            search_endpoint=config.AZURE_SEARCH_ENDPOINT,
            admin_key=config.AZURE_SEARCH_ADMIN_KEY,
        )
    except Exception as exc:
        logger.error("Error fetching status for %r: %s", document_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to query Azure AI Search: {exc}",
        )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail=f"No indexed chunks found for document_id='{document_id}'.",
        )

    first = chunks[0]
    return StatusResponse(
        document_id=document_id,
        status=IngestionStatus.COMPLETED,
        source_file=first.get("source_file"),
        document_type=first.get("document_type"),
        permission_tags=first.get("permission_tags", []),
        total_chunks=len(chunks),
        ingested_at=str(first.get("ingested_at", "")),
        chunks=[
            {
                "id": c["id"],
                "chunk_index": c["chunk_index"],
                "title": c["title"],
                "content_preview": c["content"][:120],
                "source_file": c.get("source_file", ""),
                "ingested_at": str(c.get("ingested_at", "")),
            }
            for c in chunks
        ],
    )


@router.get(
    "/documents",
    response_model=ListResponse,
    summary="List all ingested documents",
    description=(
        "Returns a de-duplicated list of all documents currently indexed in "
        "enterprise-knowledge-index, with per-document chunk counts and metadata."
    ),
)
def list_documents(
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum records to return.")] = 100,
) -> ListResponse:
    try:
        docs = list_all_documents(
            search_endpoint=config.AZURE_SEARCH_ENDPOINT,
            admin_key=config.AZURE_SEARCH_ADMIN_KEY,
            top=limit,
        )
    except Exception as exc:
        logger.error("Error listing documents: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to query Azure AI Search: {exc}",
        )

    records = [
        DocumentRecord(
            document_id=d["document_id"],
            source_file=d.get("source_file", ""),
            document_type=d.get("document_type", ""),
            permission_tags=d.get("permission_tags", []),
            total_chunks=d["total_chunks"],
            ingested_at=str(d.get("ingested_at", "")),
            status=IngestionStatus.COMPLETED,
        )
        for d in docs
    ]

    return ListResponse(total=len(records), documents=records)


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponse,
    summary="Remove a document from the index",
    description=(
        "Deletes all chunks for the given document_id from enterprise-knowledge-index. "
        "Returns 404 if no chunks are found for the document."
    ),
)
def delete_document(document_id: str) -> DeleteResponse:
    try:
        # Check existence first to return a clean 404
        chunks = fetch_document_chunks(
            document_id=document_id,
            search_endpoint=config.AZURE_SEARCH_ENDPOINT,
            admin_key=config.AZURE_SEARCH_ADMIN_KEY,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to query index: {exc}")

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail=f"No indexed chunks found for document_id='{document_id}'.",
        )

    try:
        deleted = delete_document_chunks(
            document_id=document_id,
            search_endpoint=config.AZURE_SEARCH_ENDPOINT,
            admin_key=config.AZURE_SEARCH_ADMIN_KEY,
        )
    except Exception as exc:
        logger.error("Error deleting document %r: %s", document_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to delete chunks from Azure AI Search: {exc}",
        )

    return DeleteResponse(
        document_id=document_id,
        deleted_chunks=deleted,
        message=f"Deleted {deleted} chunk(s) for document_id='{document_id}'.",
    )


@router.get(
    "/health",
    response_model=OnboardingHealthResponse,
    summary="Onboarding module health check",
    description=(
        "Verifies that the onboarding module can reach Azure AI Search and "
        "that all required environment variables are configured.\n\n"
        "Does NOT verify Azure OpenAI or Document Intelligence connectivity "
        "to keep the health check fast."
    ),
)
def health_check() -> OnboardingHealthResponse:
    # Check Azure Search connectivity
    search_status = "unconfigured"
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents.indexes import SearchIndexClient

        idx_client = SearchIndexClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            credential=AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY),
        )
        names = list(idx_client.list_index_names())
        if config.SEARCH_INDEX_NAME in names:
            search_status = "ok — index exists"
        else:
            search_status = f"warning — index '{config.SEARCH_INDEX_NAME}' not found"
    except Exception as exc:
        search_status = f"error — {exc}"

    # Azure OpenAI: just check env vars are set (avoid a token-billed call)
    openai_status = (
        "configured"
        if (config.AZURE_OPENAI_ENDPOINT and config.AZURE_OPENAI_API_KEY)
        else "unconfigured"
    )

    # Document Intelligence
    di_status = (
        "configured"
        if (
            config.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
            and config.AZURE_DOCUMENT_INTELLIGENCE_KEY
        )
        else "not configured (pypdf fallback active for PDFs)"
    )

    overall = "ok" if search_status.startswith("ok") else "degraded"

    return OnboardingHealthResponse(
        status=overall,
        azure_search=search_status,
        azure_openai=openai_status,
        azure_document_intelligence=di_status,
        index_name=config.SEARCH_INDEX_NAME,
    )
