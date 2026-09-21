"""
backend/routes/onboarding.py
------------------------------
Document onboarding and ingestion-status endpoints.

Day 4 upgrade: the document list and per-document status are now backed
by a live query to Azure AI Search (enterprise-knowledge-index) rather
than an in-memory dictionary.  This means:

  • Pilot documents ingested by the Day 1 script appear immediately.
  • Any document uploaded through POST /onboarding/upload appears in
    GET /onboarding/documents as soon as it is indexed.
  • GET /onboarding/status/{document_id} shows real chunk-level metadata.

The in-memory store is kept only as a fallback for the case where Azure AI
Search credentials are not configured (local development without .env).

Endpoints
─────────
POST /onboarding/upload                  — upload + ingest a document
GET  /onboarding/documents               — list all indexed documents (live)
GET  /onboarding/status/{document_id}    — per-document ingestion status (live)
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

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

# ---------------------------------------------------------------------------
# Fallback in-memory store (used when Azure Search is not reachable or
# when the pilot documents have not been ingested yet).
# ---------------------------------------------------------------------------
_PILOT_DOCS_FALLBACK: dict[str, dict[str, Any]] = {
    "employee-benefits.md": {
        "document_id": "employee-benefits",
        "filename": "employee-benefits.md",
        "title": "Retirement & Employee Benefits",
        "status": "ingested",
        "chunks_count": 4,
        "uploaded_at": "2026-09-20T10:00:00Z",
    },
    "leave-policy.md": {
        "document_id": "leave-policy",
        "filename": "leave-policy.md",
        "title": "Employee Leave Policy",
        "status": "ingested",
        "chunks_count": 4,
        "uploaded_at": "2026-09-20T10:00:00Z",
    },
    "reimbursement-policy.md": {
        "document_id": "reimbursement-policy",
        "filename": "reimbursement-policy.md",
        "title": "Employee Expense Reimbursement Policy",
        "status": "ingested",
        "chunks_count": 4,
        "uploaded_at": "2026-09-20T10:00:00Z",
    },
    "work-from-home-policy.md": {
        "document_id": "work-from-home-policy",
        "filename": "work-from-home-policy.md",
        "title": "Work From Home Policy",
        "status": "ingested",
        "chunks_count": 3,
        "uploaded_at": "2026-09-20T10:00:00Z",
    },
    "it-security-policy.md": {
        "document_id": "it-security-policy",
        "filename": "it-security-policy.md",
        "title": "Information Technology Security Policy",
        "status": "ingested",
        "chunks_count": 4,
        "uploaded_at": "2026-09-20T10:00:00Z",
    },
}

# Runtime upload store (tracks documents uploaded in the current process
# session, used as a merge source when Azure Search is unreachable).
_session_uploads: dict[str, dict[str, Any]] = {}

INDEX_NAME = "enterprise-knowledge-index"


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


def _list_documents_from_index() -> list[dict[str, Any]]:
    """
    Query enterprise-knowledge-index and return one summary dict per
    distinct document_id, ordered by first ingested_at descending.

    Returns an empty list if Azure Search is not reachable.
    """
    client = _search_client()
    if client is None:
        return []

    try:
        results = client.search(
            search_text="*",
            select=[
                "document_id",
                "source_file",
                "title",
                "document_type",
                "ingested_at",
                "chunk_index",
            ],
            order_by=["document_id asc", "chunk_index asc"],
            top=1000,
        )

        docs: dict[str, dict[str, Any]] = {}
        for item in results:
            doc_id = item.get("document_id", "")
            if not doc_id:
                continue
            if doc_id not in docs:
                docs[doc_id] = {
                    "document_id": doc_id,
                    "filename": item.get("source_file", f"{doc_id}.md"),
                    "title": item.get("title", doc_id.replace("-", " ").title()),
                    "status": "ingested",
                    "chunks_count": 0,
                    "uploaded_at": str(item.get("ingested_at", "")),
                }
            docs[doc_id]["chunks_count"] += 1

        return list(docs.values())

    except Exception as exc:
        logger.warning("Failed to query Azure AI Search: %s", exc)
        return []


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


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DocumentStatus(BaseModel):
    document_id: str
    filename: str
    title: str
    status: str
    chunks_count: int
    uploaded_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentStatus]
    total: int
    source: str  # "live" | "fallback"


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
    source: str  # "live" | "fallback"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List all ingested documents",
    description=(
        "Returns all documents currently indexed in enterprise-knowledge-index "
        "with real chunk counts pulled live from Azure AI Search. Falls back to "
        "a static list of pilot documents when Azure credentials are not available."
    ),
)
def list_documents() -> DocumentListResponse:
    """Return all ingested documents — live from Azure AI Search."""
    live_docs = _list_documents_from_index()

    if live_docs:
        # Merge session uploads so newly uploaded docs appear even before
        # a full Azure Search query cycle completes.
        existing_ids = {d["document_id"] for d in live_docs}
        for doc in _session_uploads.values():
            if doc["document_id"] not in existing_ids:
                live_docs.append(doc)

        return DocumentListResponse(
            documents=[DocumentStatus(**d) for d in live_docs],
            total=len(live_docs),
            source="live",
        )

    # Fallback: merge pilot defaults + session uploads
    merged = {**_PILOT_DOCS_FALLBACK}
    for key, doc in _session_uploads.items():
        merged[doc["filename"]] = doc

    docs = list(merged.values())
    return DocumentListResponse(
        documents=[DocumentStatus(**d) for d in docs],
        total=len(docs),
        source="fallback",
    )


@router.get(
    "/status/{document_id}",
    response_model=DocumentStatusDetailResponse,
    summary="Get ingestion status for a specific document",
    description=(
        "Returns detailed ingestion status for a single document by its document_id, "
        "including all indexed chunks with their titles, content previews, and metadata. "
        "Queries enterprise-knowledge-index live. Returns 404 if the document is not found."
    ),
)
def get_document_status(document_id: str) -> DocumentStatusDetailResponse:
    """Per-document ingestion status — live chunk-level detail from Azure AI Search."""
    chunks = _fetch_chunks_for_doc(document_id)

    if not chunks:
        # Check session uploads as a last resort
        for doc in _session_uploads.values():
            if doc["document_id"] == document_id:
                return DocumentStatusDetailResponse(
                    document_id=document_id,
                    filename=doc["filename"],
                    title=doc["title"],
                    status=doc["status"],
                    chunks_count=doc["chunks_count"],
                    uploaded_at=doc["uploaded_at"],
                    permission_tags=["all-employees"],
                    document_type="policy",
                    chunks=[],
                    source="session",
                )
        raise HTTPException(
            status_code=404,
            detail=(
                f"No indexed chunks found for document_id='{document_id}'. "
                "The document may not have been ingested yet, or Azure AI Search "
                "may not be reachable."
            ),
        )

    first = chunks[0]
    title = first.get("title", document_id.replace("-", " ").title())
    source_file = first.get("source_file", f"{document_id}.md")
    ingested_at = str(first.get("ingested_at", ""))
    permission_tags = first.get("permission_tags") or ["all-employees"]
    document_type = first.get("document_type", "policy")

    chunk_details = [
        ChunkDetail(
            id=c.get("id", ""),
            chunk_index=c.get("chunk_index", i),
            title=c.get("title", ""),
            content_preview=(c.get("content", "")[:150] + "…") if c.get("content") else "",
            source_file=c.get("source_file", source_file),
            ingested_at=str(c.get("ingested_at", ingested_at)),
        )
        for i, c in enumerate(chunks)
    ]

    return DocumentStatusDetailResponse(
        document_id=document_id,
        filename=source_file,
        title=title,
        status="ingested",
        chunks_count=len(chunks),
        uploaded_at=ingested_at,
        permission_tags=permission_tags,
        document_type=document_type,
        chunks=chunk_details,
        source="live",
    )


@router.post(
    "/upload",
    response_model=DocumentStatus,
    summary="Upload and ingest a document",
    description=(
        "Accepts a document upload (.md, .txt, .pdf, .docx), chunks it, generates "
        "embeddings via Azure OpenAI text-embedding-3-small, and indexes all chunks "
        "into enterprise-knowledge-index using the 11-field ingestion contract."
    ),
)
async def upload_document(file: UploadFile = File(...)) -> DocumentStatus:
    """Upload a new policy document, chunk it, embed it, and push to Azure AI Search."""
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

    # Write to a temp location for the script-based chunker
    dest_dir = Path("docs/pilot-documents")
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = dest_dir / filename
    target_path.write_bytes(content)

    doc_id = target_path.stem

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

        uploaded_at = datetime.now(timezone.utc).isoformat()
        status_info: dict[str, Any] = {
            "document_id": doc_id,
            "filename": filename,
            "title": records[0]["title"] if records else doc_id.replace("-", " ").title(),
            "status": "ingested",
            "chunks_count": len(records),
            "uploaded_at": uploaded_at,
        }
        # Track in session store so the document appears immediately in list
        _session_uploads[filename] = status_info

        logger.info(
            "Uploaded and indexed %d chunks for document_id=%r", len(records), doc_id
        )
        return DocumentStatus(**status_info)

    except Exception as exc:
        logger.error("Document ingestion failed for %r: %s", filename, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {exc}",
        )
