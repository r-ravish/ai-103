"""
onboarding/service.py
---------------------
High-level ingestion orchestrator.

This module ties together parsing → chunking → embedding → indexing and
provides the top-level ``ingest_document()`` function called by the router.

It is the only place in the onboarding module where the full pipeline is
assembled; individual stages (parsing, chunking, embedding, indexing) remain
independently testable.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from onboarding import config
from onboarding.chunking import chunk_document, RawChunk
from onboarding.embedding import generate_embeddings
from onboarding.indexing import build_index_records, upload_records
from onboarding.parsing import extract_text
from onboarding.schemas import UploadResponse, ChunkSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _derive_document_id(filename: str) -> str:
    """
    Derive a stable, URL-safe document_id from *filename*.

    Examples:
      "Leave Policy 2024.pdf" → "leave-policy-2024"
      "employee-benefits.md"  → "employee-benefits"
    """
    stem = Path(filename).stem
    slug = _SLUG_RE.sub("-", stem.lower()).strip("-")
    return slug or "document"


def _derive_title(filename: str) -> str:
    """Derive a human-readable title from *filename*."""
    stem = Path(filename).stem
    return stem.replace("-", " ").replace("_", " ").title()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_document(
    *,
    filename: str,
    content: bytes,
    document_type: str,
    permission_tags: list[str],
    document_id: str | None = None,
    title: str | None = None,
) -> UploadResponse:
    """
    Run the full ingestion pipeline for a single document.

    Pipeline:
        1. Parse / extract text (Markdown, PDF via Document Intelligence, txt, docx)
        2. Structure-first chunking (500 token max, 60 token overlap)
        3. Embed each chunk via Azure OpenAI text-embedding-3-small
        4. Build 11-field index records
        5. Upload to enterprise-knowledge-index

    Parameters
    ----------
    filename : str
        Original uploaded filename (used to derive document_id, source_file,
        source_path, and title when they are not explicitly provided).
    content : bytes
        Raw file bytes.
    document_type : str
        Logical source type (e.g. "policy", "faq").
    permission_tags : list[str]
        Access-control groups for all chunks of this document.
    document_id : str | None
        Explicit document_id override.  Derived from filename if None.
    title : str | None
        Human-readable title override.  Derived from filename if None.

    Returns
    -------
    UploadResponse
        Structured response ready to be returned by the FastAPI route.

    Raises
    ------
    ValueError
        Invalid/empty document, unsupported file type.
    RuntimeError
        Parsing failure, embedding failure, or Azure AI Search failure.
    """
    # ── Resolve identifiers ──────────────────────────────────────────────────
    doc_id = document_id or _derive_document_id(filename)
    doc_title = title or _derive_title(filename)
    ingested_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Starting ingestion: filename=%r doc_id=%r type=%r permissions=%s",
        filename,
        doc_id,
        document_type,
        permission_tags,
    )

    # ── Step 1: Parse ────────────────────────────────────────────────────────
    logger.info("Step 1/5 — Parsing document.")
    extracted_text = extract_text(filename, content)

    if not extracted_text.strip():
        raise ValueError(
            f"Document '{filename}' produced no extractable text. "
            "Verify that the file is not empty or image-only."
        )

    # ── Step 2: Chunk ────────────────────────────────────────────────────────
    logger.info("Step 2/5 — Chunking.")
    chunks: list[RawChunk] = chunk_document(
        text=extracted_text,
        fallback_title=doc_title,
        max_tokens=config.MAX_TOKENS_PER_CHUNK,
        overlap_tokens=config.OVERLAP_TOKENS,
    )

    if not chunks:
        raise ValueError(
            f"Chunking produced zero chunks for '{filename}'. "
            "The document may be empty after text extraction."
        )

    # ── Step 3: Embed ────────────────────────────────────────────────────────
    logger.info("Step 3/5 — Generating embeddings (%d chunks).", len(chunks))
    embeddings = generate_embeddings(
        chunks=chunks,
        endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
        deployment=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        batch_size=config.EMBED_BATCH_SIZE,
    )

    # ── Step 4: Build records ────────────────────────────────────────────────
    logger.info("Step 4/5 — Building index records.")
    records = build_index_records(
        document_id=doc_id,
        source_file=filename,
        source_path=f"onboarding/uploads/{filename}",
        document_type=document_type,
        permission_tags=permission_tags,
        chunks=chunks,
        embeddings=embeddings,
        ingested_at=ingested_at,
    )

    # ── Step 5: Upload ───────────────────────────────────────────────────────
    logger.info("Step 5/5 — Uploading to Azure AI Search.")
    indexed_count = upload_records(
        records=records,
        search_endpoint=config.AZURE_SEARCH_ENDPOINT,
        admin_key=config.AZURE_SEARCH_ADMIN_KEY,
        batch_size=config.UPLOAD_BATCH_SIZE,
    )

    logger.info(
        "Ingestion complete: doc_id=%r, %d/%d chunks indexed.",
        doc_id,
        indexed_count,
        len(chunks),
    )

    # ── Build response ───────────────────────────────────────────────────────
    chunk_summaries = [
        ChunkSummary(
            chunk_index=c.chunk_index,
            title=c.title,
            content_preview=c.content[:120],
        )
        for c in chunks
    ]

    status_msg = (
        f"Successfully ingested '{filename}' as document_id='{doc_id}'. "
        f"{indexed_count}/{len(chunks)} chunks indexed into enterprise-knowledge-index."
    )

    if indexed_count < len(chunks):
        status_msg = (
            f"Partial ingestion: '{filename}' — {indexed_count}/{len(chunks)} "
            "chunks indexed. Check server logs for failed upload details."
        )

    return UploadResponse(
        document_id=doc_id,
        source_file=filename,
        document_type=document_type,
        permission_tags=permission_tags,
        total_chunks=len(chunks),
        indexed_chunks=indexed_count,
        ingested_at=ingested_at,
        chunks=chunk_summaries,
        message=status_msg,
    )
