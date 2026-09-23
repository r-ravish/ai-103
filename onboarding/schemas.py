"""
onboarding/schemas.py
---------------------
Pydantic models for the onboarding API.

These are the *API* shapes — the request bodies and response envelopes.
The *index* schema (the 11-field contract from ingestion-contract.md) lives
in indexing.py as a plain dict; we keep it out of Pydantic so the same
dict can be handed directly to the Azure Search SDK without a model dump.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IngestionStatus(str, Enum):
    """Lifecycle states of an ingestion job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ---------------------------------------------------------------------------
# Upload request body extras (form fields sent alongside the file)
# ---------------------------------------------------------------------------

class UploadMetadata(BaseModel):
    """
    Optional metadata the caller can supply with the upload.

    All fields are optional.  The onboarding module applies sensible defaults
    when they are absent.
    """

    document_type: str = Field(
        default="policy",
        description=(
            "Logical source type.  Examples: 'policy', 'faq', 'ticket-data'. "
            "Defaults to 'policy' when not supplied."
        ),
    )
    permission_tags: list[str] = Field(
        default_factory=lambda: ["all-employees"],
        description=(
            "Access-control groups that may see this document's chunks.  "
            "Defaults to ['all-employees']."
        ),
    )
    document_id: str | None = Field(
        default=None,
        description=(
            "Explicit stable identifier for the document.  "
            "If omitted, the module derives one from the filename stem."
        ),
    )
    title: str | None = Field(
        default=None,
        description=(
            "Human-readable document title.  "
            "If omitted, derived from the filename stem."
        ),
    )


# ---------------------------------------------------------------------------
# Upload response
# ---------------------------------------------------------------------------

class ChunkSummary(BaseModel):
    """Brief metadata about a single indexed chunk."""
    chunk_index: int
    title: str
    content_preview: str = Field(description="First 120 characters of the chunk content.")


class UploadResponse(BaseModel):
    """Response body for POST /onboarding/upload."""

    document_id: str
    source_file: str
    document_type: str
    permission_tags: list[str]
    total_chunks: int
    indexed_chunks: int
    ingested_at: str = Field(description="UTC ISO-8601 timestamp.")
    chunks: list[ChunkSummary] = Field(
        description="Summary of all generated chunks (index, title, preview)."
    )
    message: str = Field(description="Human-readable status message.")


# ---------------------------------------------------------------------------
# Status / list responses
# ---------------------------------------------------------------------------

class DocumentRecord(BaseModel):
    """Summary of a single ingested document returned by the status endpoint."""

    document_id: str
    source_file: str
    document_type: str
    permission_tags: list[str]
    total_chunks: int
    ingested_at: str
    status: IngestionStatus
    error: str | None = Field(
        default=None,
        description="Error message if ingestion failed or was only partial.",
    )


class StatusResponse(BaseModel):
    """Response body for GET /onboarding/status/{document_id}."""

    document_id: str
    status: IngestionStatus
    source_file: str | None = None
    document_type: str | None = None
    permission_tags: list[str] = Field(default_factory=list)
    total_chunks: int | None = None
    ingested_at: str | None = None
    chunks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="All chunks found in the index for this document_id.",
    )
    error: str | None = None


class ListResponse(BaseModel):
    """Response body for GET /onboarding/documents."""

    total: int
    documents: list[DocumentRecord]


# ---------------------------------------------------------------------------
# Delete response
# ---------------------------------------------------------------------------

class DeleteResponse(BaseModel):
    """Response body for DELETE /onboarding/documents/{document_id}."""

    document_id: str
    deleted_chunks: int
    message: str


# ---------------------------------------------------------------------------
# Health response
# ---------------------------------------------------------------------------

class OnboardingHealthResponse(BaseModel):
    """Response body for GET /onboarding/health."""

    status: str
    azure_search: str
    azure_openai: str
    azure_document_intelligence: str
    index_name: str
