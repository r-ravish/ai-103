"""
onboarding/tests/test_indexing.py
----------------------------------
Unit tests for the indexing module — specifically build_index_records().

These tests are fully offline — no Azure calls are made.
Run with: pytest onboarding/tests/test_indexing.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from onboarding.chunking import RawChunk
from onboarding.indexing import build_index_records


# ---------------------------------------------------------------------------
# build_index_records
# ---------------------------------------------------------------------------

def _make_chunks(n: int) -> list[RawChunk]:
    return [
        RawChunk(
            chunk_index=i,
            title=f"Section {i}",
            content=f"Content for chunk {i}.",
        )
        for i in range(n)
    ]


def _make_embeddings(n: int, dims: int = 1536) -> list[list[float]]:
    return [[0.0] * dims for _ in range(n)]


COMMON_KWARGS = dict(
    document_id="test-doc",
    source_file="test-doc.md",
    source_path="onboarding/uploads/test-doc.md",
    document_type="policy",
    permission_tags=["all-employees"],
    ingested_at="2026-09-21T00:00:00+00:00",
)


def test_build_records_count():
    chunks = _make_chunks(3)
    embeddings = _make_embeddings(3)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    assert len(records) == 3


def test_build_records_id_format():
    """id must be {document_id}_{chunk_index:03d}."""
    chunks = _make_chunks(5)
    embeddings = _make_embeddings(5)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    for record in records:
        idx = record["chunk_index"]
        expected_id = f"test-doc_{idx:03d}"
        assert record["id"] == expected_id, f"Expected {expected_id}, got {record['id']}"


def test_build_records_all_11_fields():
    """Every record must have all 11 fields from the ingestion contract."""
    required_fields = {
        "id", "document_id", "chunk_index", "title", "content",
        "embedding", "source_file", "source_path", "document_type",
        "permission_tags", "ingested_at",
    }
    chunks = _make_chunks(2)
    embeddings = _make_embeddings(2)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    for record in records:
        missing = required_fields - set(record.keys())
        assert not missing, f"Record missing fields: {missing}"


def test_build_records_embedding_dimensions():
    chunks = _make_chunks(2)
    embeddings = _make_embeddings(2, dims=1536)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    for record in records:
        assert len(record["embedding"]) == 1536


def test_build_records_permission_tags_is_list():
    chunks = _make_chunks(1)
    embeddings = _make_embeddings(1)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    assert isinstance(records[0]["permission_tags"], list)
    assert "all-employees" in records[0]["permission_tags"]


def test_build_records_document_id_propagated():
    chunks = _make_chunks(2)
    embeddings = _make_embeddings(2)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    for record in records:
        assert record["document_id"] == "test-doc"


def test_build_records_chunk_index_zero_based():
    chunks = _make_chunks(3)
    embeddings = _make_embeddings(3)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    indices = [r["chunk_index"] for r in records]
    assert indices == [0, 1, 2]


def test_build_records_mismatch_raises():
    chunks = _make_chunks(3)
    embeddings = _make_embeddings(2)  # one fewer embedding
    with pytest.raises(ValueError, match="Chunk count"):
        build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)


def test_build_records_zero_chunks_returns_empty():
    records = build_index_records(chunks=[], embeddings=[], **COMMON_KWARGS)
    assert records == []


def test_build_records_content_preserved():
    chunks = _make_chunks(1)
    embeddings = _make_embeddings(1)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    assert records[0]["content"] == "Content for chunk 0."


def test_build_records_title_preserved():
    chunks = _make_chunks(1)
    embeddings = _make_embeddings(1)
    records = build_index_records(chunks=chunks, embeddings=embeddings, **COMMON_KWARGS)
    assert records[0]["title"] == "Section 0"
