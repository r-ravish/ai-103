"""
backend/routes/onboarding.py
-----------------------------
Document onboarding and ingestion status endpoints for Day 4.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from scripts.ingest_pilot_documents import (
    build_chunks_for_file,
    embed_records,
    upload_records,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_uploaded_docs_store: dict[str, dict[str, Any]] = {
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


class DocumentStatus(BaseModel):
    document_id: str
    filename: str
    title: str
    status: str
    chunks_count: int
    uploaded_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentStatus]


@router.get("/documents", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    """Return all ingested documents and their status."""
    return DocumentListResponse(documents=list(_uploaded_docs_store.values()))


@router.post("/upload", response_model=DocumentStatus)
async def upload_document(file: UploadFile = File(...)) -> DocumentStatus:
    """Upload a new policy document, chunk it, embed it, and upload to Azure AI Search."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected or invalid filename.")

    filename = file.filename
    dest_dir = Path("docs/pilot-documents")
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = dest_dir / filename

    content = await file.read()
    target_path.write_bytes(content)

    doc_id = target_path.stem

    try:
        records = build_chunks_for_file(target_path)

        search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
        search_key = os.environ["AZURE_SEARCH_ADMIN_KEY"]
        aoai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        aoai_key = os.environ["AZURE_OPENAI_API_KEY"]
        aoai_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")

        aoai_client = AzureOpenAI(
            azure_endpoint=aoai_endpoint,
            api_key=aoai_key,
            api_version=aoai_version,
        )
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name="enterprise-knowledge-index",
            credential=AzureKeyCredential(search_key),
        )

        embed_records(aoai_client, records)
        upload_records(search_client, records)

        status_info = {
            "document_id": doc_id,
            "filename": filename,
            "title": records[0]["title"] if records else doc_id.replace("-", " ").title(),
            "status": "ingested",
            "chunks_count": len(records),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        _uploaded_docs_store[filename] = status_info
        return DocumentStatus(**status_info)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {exc}")
