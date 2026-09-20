"""
onboarding/indexing.py
----------------------
Azure AI Search integration for the onboarding module.

Responsibilities:
  • Build index records conforming exactly to the 11-field contract
    (docs/ingestion-contract.md).
  • Upload records to enterprise-knowledge-index in batches.
  • Query the index to retrieve ingestion status for a document.
  • List all ingested documents via a faceted search.
  • Delete all chunks for a given document_id.

This module never touches Ravish's or Radhika's code — it speaks directly
to the Azure AI Search SDK using its own client instance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

logger = logging.getLogger(__name__)

INDEX_NAME = "enterprise-knowledge-index"


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------

def build_index_records(
    *,
    document_id: str,
    source_file: str,
    source_path: str,
    document_type: str,
    permission_tags: list[str],
    chunks,  # list[RawChunk]
    embeddings: list[list[float]],
    ingested_at: str,
) -> list[dict[str, Any]]:
    """
    Combine chunk text, metadata, and embeddings into the 11-field contract
    records expected by enterprise-knowledge-index.

    Field mapping (from ingestion-contract.md):
    ─────────────────────────────────────────────────────────────────────────
    id              → "{document_id}_{chunk_index:03d}"
    document_id     → supplied
    chunk_index     → zero-based integer from RawChunk
    title           → RawChunk.title
    content         → RawChunk.content
    embedding       → 1536-dim float list from Azure OpenAI
    source_file     → supplied (original filename)
    source_path     → supplied
    document_type   → supplied
    permission_tags → supplied (list[str])
    ingested_at     → UTC ISO-8601 timestamp
    ─────────────────────────────────────────────────────────────────────────
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunk count ({len(chunks)}) != embedding count ({len(embeddings)}). "
            "Ensure embeddings were generated for all chunks."
        )

    records: list[dict[str, Any]] = []
    for chunk, embedding in zip(chunks, embeddings):
        record_id = f"{document_id}_{chunk.chunk_index:03d}"
        records.append(
            {
                "id": record_id,
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "title": chunk.title,
                "content": chunk.content,
                "embedding": embedding,
                "source_file": source_file,
                "source_path": source_path,
                "document_type": document_type,
                "permission_tags": permission_tags,
                "ingested_at": ingested_at,
            }
        )

    return records


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_records(
    records: list[dict[str, Any]],
    search_endpoint: str,
    admin_key: str,
    batch_size: int = 100,
) -> int:
    """
    Upload *records* to enterprise-knowledge-index.

    Parameters
    ----------
    records :
        Index records built by :func:`build_index_records`.
    search_endpoint :
        Azure AI Search service endpoint URL.
    admin_key :
        Admin API key (write access required).
    batch_size :
        Upload batch size (default: 100).

    Returns
    -------
    int
        Number of successfully indexed records.

    Raises
    ------
    RuntimeError
        If any records fail to upload.
    """
    client = SearchClient(
        endpoint=search_endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(admin_key),
    )

    total_success = 0
    total_failed = 0

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        results = client.upload_documents(documents=batch)
        failed = [r for r in results if not r.succeeded]
        success = len(batch) - len(failed)
        total_success += success
        total_failed += len(failed)

        if failed:
            failed_keys = [f.key for f in failed]
            logger.error(
                "Upload batch %d–%d: %d failed records: %s",
                start,
                start + len(batch) - 1,
                len(failed),
                failed_keys,
            )

    if total_failed > 0:
        raise RuntimeError(
            f"{total_failed} record(s) failed to upload to Azure AI Search. "
            f"Successfully uploaded: {total_success}."
        )

    logger.info("Uploaded %d records to %s.", total_success, INDEX_NAME)
    return total_success


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------

def fetch_document_chunks(
    document_id: str,
    search_endpoint: str,
    admin_key: str,
) -> list[dict[str, Any]]:
    """
    Return all indexed chunks for *document_id*, ordered by chunk_index.

    Uses a filter query (not vector search) so results are exact and complete.
    Returns an empty list if the document has not been indexed.
    """
    client = SearchClient(
        endpoint=search_endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(admin_key),
    )

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
        top=1000,  # practical maximum; documents should not exceed this
    )

    chunks = list(results)
    logger.info(
        "fetch_document_chunks(%r): found %d chunks.", document_id, len(chunks)
    )
    return chunks


# ---------------------------------------------------------------------------
# List all documents
# ---------------------------------------------------------------------------

def list_all_documents(
    search_endpoint: str,
    admin_key: str,
    top: int = 1000,
) -> list[dict[str, Any]]:
    """
    Return a de-duplicated list of ingested documents (one entry per document_id).

    Retrieves all chunks, then groups by document_id to produce a summary.
    Works within Azure AI Search's capabilities (no facet aggregation needed).
    """
    client = SearchClient(
        endpoint=search_endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(admin_key),
    )

    results = client.search(
        search_text="*",
        select=[
            "document_id",
            "source_file",
            "document_type",
            "permission_tags",
            "ingested_at",
            "chunk_index",
        ],
        order_by=["document_id asc", "chunk_index asc"],
        top=top,
    )

    # Group by document_id
    docs: dict[str, dict[str, Any]] = {}
    for item in results:
        doc_id = item["document_id"]
        if doc_id not in docs:
            docs[doc_id] = {
                "document_id": doc_id,
                "source_file": item.get("source_file", ""),
                "document_type": item.get("document_type", ""),
                "permission_tags": item.get("permission_tags", []),
                "ingested_at": item.get("ingested_at", ""),
                "total_chunks": 0,
            }
        docs[doc_id]["total_chunks"] += 1

    result_list = list(docs.values())
    logger.info("list_all_documents: found %d distinct documents.", len(result_list))
    return result_list


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_document_chunks(
    document_id: str,
    search_endpoint: str,
    admin_key: str,
) -> int:
    """
    Delete all indexed chunks for *document_id*.

    Returns the number of chunks deleted.
    """
    chunks = fetch_document_chunks(document_id, search_endpoint, admin_key)
    if not chunks:
        logger.info("delete_document_chunks(%r): no chunks found.", document_id)
        return 0

    client = SearchClient(
        endpoint=search_endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(admin_key),
    )

    # Delete by key
    keys_to_delete = [{"id": c["id"]} for c in chunks]
    results = client.delete_documents(documents=keys_to_delete)
    failed = [r for r in results if not r.succeeded]

    deleted_count = len(chunks) - len(failed)

    if failed:
        logger.error(
            "delete_document_chunks(%r): %d deletions failed.", document_id, len(failed)
        )

    logger.info(
        "delete_document_chunks(%r): deleted %d chunks.", document_id, deleted_count
    )
    return deleted_count
