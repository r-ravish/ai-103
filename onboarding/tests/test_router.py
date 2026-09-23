"""
onboarding/tests/test_router.py
---------------------------------
Integration tests for the FastAPI router using TestClient.

These tests mock the Azure services so no real network calls are made.
They verify HTTP status codes, response shapes, and error handling.

Run with: pytest onboarding/tests/test_router.py -v
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ---------------------------------------------------------------------------
# Patch os.environ BEFORE any onboarding module is imported so that
# config._require() sees real-looking values and does not raise.
# ---------------------------------------------------------------------------
_ENV_OVERRIDES = {
    "AZURE_SEARCH_ENDPOINT": "https://mock-search.search.windows.net",
    "AZURE_SEARCH_ADMIN_KEY": "mock-admin-key",
    "SEARCH_INDEX_NAME": "enterprise-knowledge-index",
    "AZURE_OPENAI_ENDPOINT": "https://mock-openai.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "mock-openai-key",
    "AZURE_OPENAI_API_VERSION": "2024-10-21",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
}
os.environ.update(_ENV_OVERRIDES)


# env vars are already set at module level above; no autouse fixture needed.


# ---------------------------------------------------------------------------
# Build test app
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    from onboarding.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper — mock for ingest_document
# ---------------------------------------------------------------------------

def _mock_ingest_result():
    from onboarding.schemas import ChunkSummary, UploadResponse

    return UploadResponse(
        document_id="test-doc",
        source_file="test-doc.md",
        document_type="policy",
        permission_tags=["all-employees"],
        total_chunks=3,
        indexed_chunks=3,
        ingested_at="2026-09-21T00:00:00+00:00",
        chunks=[
            ChunkSummary(chunk_index=i, title=f"Section {i}", content_preview=f"Content {i}...")
            for i in range(3)
        ],
        message="Successfully ingested 'test-doc.md'.",
    )


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "onboarding"


# ---------------------------------------------------------------------------
# POST /onboarding/upload
# ---------------------------------------------------------------------------

def test_upload_md_success(client):
    md_content = b"# Policy\nThis is policy content."
    with patch("onboarding.router.ingest_document", return_value=_mock_ingest_result()):
        resp = client.post(
            "/onboarding/upload",
            files={"file": ("test-doc.md", io.BytesIO(md_content), "text/markdown")},
            data={"document_type": "policy", "permission_tags": "all-employees"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == "test-doc"
    assert body["total_chunks"] == 3
    assert body["indexed_chunks"] == 3


def test_upload_unsupported_extension(client):
    resp = client.post(
        "/onboarding/upload",
        files={"file": ("file.xyz", io.BytesIO(b"data"), "application/octet-stream")},
        data={"document_type": "policy"},
    )
    assert resp.status_code == 415


def test_upload_empty_file(client):
    resp = client.post(
        "/onboarding/upload",
        files={"file": ("empty.md", io.BytesIO(b""), "text/markdown")},
        data={"document_type": "policy"},
    )
    assert resp.status_code == 400


def test_upload_custom_document_id(client):
    md_content = b"# Policy\nContent."
    mock_result = _mock_ingest_result()
    mock_result.document_id = "custom-id"

    with patch("onboarding.router.ingest_document", return_value=mock_result):
        resp = client.post(
            "/onboarding/upload",
            files={"file": ("test.md", io.BytesIO(md_content), "text/markdown")},
            data={"document_type": "policy", "document_id": "custom-id"},
        )
    assert resp.status_code == 200
    assert resp.json()["document_id"] == "custom-id"


def test_upload_multiple_permission_tags(client):
    md_content = b"# HR Policy\nContent."
    with patch("onboarding.router.ingest_document", return_value=_mock_ingest_result()):
        resp = client.post(
            "/onboarding/upload",
            files={"file": ("hr.md", io.BytesIO(md_content), "text/markdown")},
            data={
                "document_type": "policy",
                "permission_tags": "all-employees,hr",
            },
        )
    assert resp.status_code == 200


def test_upload_value_error_returns_422(client):
    with patch(
        "onboarding.router.ingest_document",
        side_effect=ValueError("No extractable text"),
    ):
        resp = client.post(
            "/onboarding/upload",
            files={"file": ("bad.md", io.BytesIO(b"content"), "text/markdown")},
            data={"document_type": "policy"},
        )
    assert resp.status_code == 422


def test_upload_runtime_error_returns_502(client):
    with patch(
        "onboarding.router.ingest_document",
        side_effect=RuntimeError("Azure Search unreachable"),
    ):
        resp = client.post(
            "/onboarding/upload",
            files={"file": ("bad.md", io.BytesIO(b"content"), "text/markdown")},
            data={"document_type": "policy"},
        )
    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# GET /onboarding/status/{document_id}
# ---------------------------------------------------------------------------

def test_status_found(client):
    mock_chunks = [
        {
            "id": f"test-doc_{i:03d}",
            "document_id": "test-doc",
            "chunk_index": i,
            "title": f"Section {i}",
            "content": f"Content {i}",
            "source_file": "test-doc.md",
            "source_path": "onboarding/uploads/test-doc.md",
            "document_type": "policy",
            "permission_tags": ["all-employees"],
            "ingested_at": "2026-09-21T00:00:00+00:00",
        }
        for i in range(3)
    ]
    with patch("onboarding.router.fetch_document_chunks", return_value=mock_chunks):
        resp = client.get("/onboarding/status/test-doc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == "test-doc"
    assert body["total_chunks"] == 3
    assert body["status"] == "completed"


def test_status_not_found(client):
    with patch("onboarding.router.fetch_document_chunks", return_value=[]):
        resp = client.get("/onboarding/status/nonexistent-doc")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /onboarding/documents
# ---------------------------------------------------------------------------

def test_list_documents(client):
    mock_docs = [
        {
            "document_id": "leave-policy",
            "source_file": "leave-policy.md",
            "document_type": "policy",
            "permission_tags": ["all-employees"],
            "ingested_at": "2026-09-21T00:00:00+00:00",
            "total_chunks": 4,
        }
    ]
    with patch("onboarding.router.list_all_documents", return_value=mock_docs):
        resp = client.get("/onboarding/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["documents"][0]["document_id"] == "leave-policy"


def test_list_documents_empty(client):
    with patch("onboarding.router.list_all_documents", return_value=[]):
        resp = client.get("/onboarding/documents")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# DELETE /onboarding/documents/{document_id}
# ---------------------------------------------------------------------------

def test_delete_document(client):
    mock_chunks = [{"id": "test-doc_000"}]
    with (
        patch("onboarding.router.fetch_document_chunks", return_value=mock_chunks),
        patch("onboarding.router.delete_document_chunks", return_value=1),
    ):
        resp = client.delete("/onboarding/documents/test-doc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_chunks"] == 1


def test_delete_document_not_found(client):
    with patch("onboarding.router.fetch_document_chunks", return_value=[]):
        resp = client.delete("/onboarding/documents/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /onboarding/health
# ---------------------------------------------------------------------------

def test_health_check(client):
    with patch("azure.search.documents.indexes.SearchIndexClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.list_index_names.return_value = ["enterprise-knowledge-index"]
        mock_client_cls.return_value = mock_client
        resp = client.get("/onboarding/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "azure_search" in body
    assert "azure_openai" in body
