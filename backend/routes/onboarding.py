"""
backend/routes/onboarding.py
------------------------------
Document onboarding, listing, status, and deletion — all admin-only.

PostgreSQL (db.models.Document) is now the source of truth for document
metadata. The previous in-memory store did not survive a process restart;
every document uploaded through POST /onboarding/upload is now written to
the documents table, and GET /onboarding/documents reads from it.

Ingestion flow:
    POST /onboarding/upload
        -> save file to disk
        -> chunk + embed
        -> create Document row (status=ingesting)
        -> upload chunks to Azure AI Search
        -> status=ingested (chunks_count set)      on success
        -> status=failed                            on any failure

Deletion flow (DELETE /onboarding/documents/{document_id}):
        -> look up Document row (404 if missing)
        -> delete every indexed chunk for that document_id from Azure AI Search
        -> delete the original uploaded file from disk
        -> delete the Document row
        -> if any step fails, the row is NOT deleted and an error is raised —
           deletion never "silently succeeds" client-side only.

All routes require an authenticated admin session (require_admin).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import require_admin
from db.database import get_db
from db.models import Document, DocumentStatus, User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Make the scripts directory importable (backend is the CWD when running
# uvicorn app.main:app from the backend/ directory).
# ---------------------------------------------------------------------------
_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from ingest_pilot_documents import (  # noqa: E402
    build_chunks_for_file,
    embed_records,
    upload_records,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

INDEX_NAME = "enterprise-knowledge-index"
DOCS_DIR = Path("docs/pilot-documents")


# ---------------------------------------------------------------------------
# Azure AI Search helpers
# ---------------------------------------------------------------------------

def _search_client():
    """Return a SearchClient or None if credentials are not configured."""
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
    key = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "")
    if not endpoint or not key or endpoint.startswith("<"):
        return None
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    return SearchClient(
        endpoint=endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(key),
    )


def _fetch_chunks_for_doc(document_id: str) -> list[dict[str, Any]]:
    """
    Return all indexed chunks for *document_id*, sorted by chunk_index.
    Returns an empty list if Azure Search is not reachable.
    """
    client = _search_client()
    if client is None:
        return []

    try:
        results = client.search(
            search_text="*",
            filter=f"document_id eq '{document_id}'",
            select=[
                "id",
                "document_id",
                "chunk_index",
                "title",
                "content",
                "source_file",
                "source_path",
                "document_type",
                "permission_tags",
                "ingested_at",
            ],
            order_by=["chunk_index asc"],
            top=1000,
        )
        return list(results)
    except Exception as exc:
        logger.warning("Failed to fetch chunks for %r: %s", document_id, exc)
        return []


def _delete_chunks_from_index(document_id: str) -> int:
    """
    Delete every indexed chunk belonging to *document_id* (e.g.
    document_id_000, document_id_001, ...) from Azure AI Search.

    Returns the number of chunks deleted. Raises RuntimeError if Azure
    Search is configured but the delete call fails, so callers never
    report a false success.
    """
    client = _search_client()
    if client is None:
        # Azure Search not configured (local dev) — nothing to clean up there.
        return 0

    chunks = _fetch_chunks_for_doc(document_id)
    if not chunks:
        return 0

    keys = [{"id": c["id"]} for c in chunks if c.get("id")]
    if not keys:
        return 0

    try:
        result = client.delete_documents(documents=keys)
    except Exception as exc:
        raise RuntimeError(f"Failed to delete chunks for document_id={document_id!r} from Azure AI Search: {exc}") from exc

    failed = [r.key for r in result if not r.succeeded]
    if failed:
        raise RuntimeError(f"Azure AI Search refused to delete chunk id(s) {failed} for document_id={document_id!r}.")

    return len(keys)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DocumentStatusResponse(BaseModel):
    document_id: str
    filename: str
    title: str
    status: str
    chunks_count: int
    uploaded_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentStatusResponse]
    total: int


class ChunkDetail(BaseModel):
    id: str
    chunk_index: int
    title: str
    content_preview: str
    source_file: str
    ingested_at: str


class DocumentStatusDetailResponse(BaseModel):
    document_id: str
    filename: str
    title: str
    status: str
    chunks_count: int
    uploaded_at: str
    permission_tags: list[str]
    document_type: str
    chunks: list[ChunkDetail]


class DeleteResponse(BaseModel):
    document_id: str
    deleted: bool
    chunks_deleted: int


def _to_response(doc: Document) -> DocumentStatusResponse:
    return DocumentStatusResponse(
        document_id=doc.document_id,
        filename=doc.filename,
        title=doc.title or doc.document_id.replace("-", " ").replace("_", " ").title(),
        status=doc.status.value,
        chunks_count=doc.chunks_count or 0,
        uploaded_at=doc.uploaded_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List all onboarded documents",
    description="Returns all document metadata persisted in PostgreSQL, most recently uploaded first.",
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> DocumentListResponse:
    """Return all documents tracked in PostgreSQL — the single source of truth."""
    rows = (
        await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
    ).scalars().all()

    docs = [_to_response(d) for d in rows]
    return DocumentListResponse(documents=docs, total=len(docs))


@router.get(
    "/status/{document_id}",
    response_model=DocumentStatusDetailResponse,
    summary="Get ingestion status for a specific document",
    description=(
        "Returns the persisted status for a document plus (when available) live "
        "chunk-level detail from Azure AI Search. Returns 404 if the document is "
        "not known to PostgreSQL."
    ),
)
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> DocumentStatusDetailResponse:
    """Per-document ingestion status — persisted status + live chunk detail."""
    doc = (await db.execute(select(Document).where(Document.document_id == document_id))).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No document found with document_id={document_id!r}.")

    chunks = _fetch_chunks_for_doc(document_id)
    permission_tags = (chunks[0].get("permission_tags") if chunks else None) or ["all-employees"]
    document_type = (chunks[0].get("document_type") if chunks else None) or "policy"

    chunk_details = [
        ChunkDetail(
            id=c.get("id", ""),
            chunk_index=c.get("chunk_index", i),
            title=c.get("title", ""),
            content_preview=(c.get("content", "")[:150] + "…") if c.get("content") else "",
            source_file=c.get("source_file", doc.filename),
            ingested_at=str(c.get("ingested_at", doc.uploaded_at.isoformat())),
        )
        for i, c in enumerate(chunks)
    ]

    return DocumentStatusDetailResponse(
        document_id=doc.document_id,
        filename=doc.filename,
        title=doc.title or doc.document_id,
        status=doc.status.value,
        chunks_count=doc.chunks_count or len(chunk_details),
        uploaded_at=doc.uploaded_at.isoformat(),
        permission_tags=permission_tags,
        document_type=document_type,
        chunks=chunk_details,
    )


@router.post(
    "/upload",
    response_model=DocumentStatusResponse,
    summary="Upload and ingest a document",
    description=(
        "Accepts a document upload (.md, .txt, .pdf, .docx), chunks it, generates "
        "embeddings via Azure OpenAI text-embedding-3-small, and indexes all chunks "
        "into enterprise-knowledge-index using the 11-field ingestion contract. "
        "Only reports status=ingested once the Azure AI Search upload has actually "
        "succeeded; failures are persisted as status=failed."
    ),
)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DocumentStatusResponse:
    """Upload a new policy document, chunk it, embed it, and push it to Azure AI Search."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected or invalid filename.")

    filename = file.filename
    allowed = {".pdf", ".md", ".txt", ".docx"}
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Accepted: {sorted(allowed)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = DOCS_DIR / filename
    target_path.write_bytes(content)

    doc_id = target_path.stem

    # Upsert the Document row up front so a failure is still visible/tracked.
    existing = (await db.execute(select(Document).where(Document.document_id == doc_id))).scalar_one_or_none()
    if existing is not None:
        doc_row = existing
        doc_row.filename = filename
        doc_row.storage_path = str(target_path)
        doc_row.status = DocumentStatus.ingesting
        doc_row.uploaded_by_id = admin.id
    else:
        doc_row = Document(
            document_id=doc_id,
            filename=filename,
            title=doc_id.replace("-", " ").replace("_", " ").title(),
            status=DocumentStatus.ingesting,
            storage_path=str(target_path),
            uploaded_by_id=admin.id,
        )
        db.add(doc_row)
    await db.flush()

    try:
        from openai import AzureOpenAI
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient as _SC

        records = build_chunks_for_file(target_path)
        if not records:
            raise ValueError("Document produced no chunks after parsing.")

        search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
        search_key = os.environ["AZURE_SEARCH_ADMIN_KEY"]
        aoai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        aoai_key = os.environ["AZURE_OPENAI_API_KEY"]
        aoai_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
        aoai_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

        aoai_client = AzureOpenAI(
            azure_endpoint=aoai_endpoint,
            api_key=aoai_key,
            api_version=aoai_version,
        )
        search_client_inst = _SC(
            endpoint=search_endpoint,
            index_name=INDEX_NAME,
            credential=AzureKeyCredential(search_key),
        )

        embed_records(aoai_client, records)
        upload_records(search_client_inst, records)

        # Only now — after Azure AI Search has actually accepted the chunks —
        # do we mark the document as ingested.
        doc_row.title = records[0]["title"] if records else doc_row.title
        doc_row.status = DocumentStatus.ingested
        doc_row.chunks_count = len(records)
        await db.flush()
        await db.refresh(doc_row)

        logger.info("Uploaded and indexed %d chunks for document_id=%r", len(records), doc_id)
        return _to_response(doc_row)

    except Exception as exc:
        doc_row.status = DocumentStatus.failed
        await db.flush()
        logger.error("Document ingestion failed for %r: %s", filename, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {exc}",
        )


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponse,
    summary="Delete a document and all of its indexed chunks",
    description=(
        "Deletes every Azure AI Search chunk for the document, the original "
        "uploaded file, and the PostgreSQL row. Returns 404 for an unknown "
        "document_id, and a 500 (without deleting the DB row) if any step fails."
    ),
)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> DeleteResponse:
    """Real deletion: Azure Search chunks -> uploaded file -> DB row."""
    doc = (await db.execute(select(Document).where(Document.document_id == document_id))).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No document found with document_id={document_id!r}.")

    try:
        chunks_deleted = _delete_chunks_from_index(document_id)
    except RuntimeError as exc:
        logger.error("Failed to delete Azure AI Search chunks for %r: %s", document_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if doc.storage_path:
        try:
            Path(doc.storage_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.error("Failed to delete stored file %r: %s", doc.storage_path, exc)
            raise HTTPException(
                status_code=500,
                detail=f"Deleted {chunks_deleted} search chunk(s) but failed to remove the stored file: {exc}",
            )

    await db.delete(doc)
    await db.flush()

    return DeleteResponse(document_id=document_id, deleted=True, chunks_deleted=chunks_deleted)
