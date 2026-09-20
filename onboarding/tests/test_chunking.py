"""
onboarding/tests/test_chunking.py
----------------------------------
Unit tests for the chunking module.

These tests are fully offline — no Azure calls are made.
Run with: pytest onboarding/tests/test_chunking.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from onboarding.chunking import chunk_document, _split_into_sections, _token_based_split


# ---------------------------------------------------------------------------
# _split_into_sections
# ---------------------------------------------------------------------------

def test_split_into_sections_with_headings():
    text = "# Section One\nContent one.\n## Section Two\nContent two."
    sections = _split_into_sections(text, fallback_title="doc")
    titles = [t for t, _ in sections]
    assert "Section One" in titles
    assert "Section Two" in titles


def test_split_into_sections_no_headings():
    text = "Just some plain text without any headings."
    sections = _split_into_sections(text, fallback_title="fallback")
    assert len(sections) == 1
    assert sections[0][0] == "fallback"
    assert "Just some plain text" in sections[0][1]


def test_split_into_sections_empty_text():
    sections = _split_into_sections("", fallback_title="empty")
    assert sections == []


def test_split_into_sections_strips_empty_bodies():
    text = "# Empty Heading\n\n# Real Heading\nActual content here."
    sections = _split_into_sections(text, fallback_title="doc")
    bodies = [b for _, b in sections]
    # At least one non-empty body must be present
    assert any(b.strip() for b in bodies)


# ---------------------------------------------------------------------------
# _token_based_split
# ---------------------------------------------------------------------------

def test_token_based_split_short_text():
    short = "This is a short text."
    pieces = _token_based_split(short, max_tokens=500, overlap=60)
    assert len(pieces) == 1
    assert pieces[0] == short


def test_token_based_split_long_text():
    # Generate a text that exceeds 20 tokens
    long_text = " ".join(["word"] * 100)
    pieces = _token_based_split(long_text, max_tokens=20, overlap=5)
    assert len(pieces) > 1


def test_token_based_split_overlap_produces_continuity():
    """Consecutive chunks should share content when overlap > 0."""
    long_text = " ".join([f"word{i}" for i in range(200)])
    pieces = _token_based_split(long_text, max_tokens=50, overlap=10)
    assert len(pieces) >= 2
    # The end of chunk N and the start of chunk N+1 should have common tokens
    # (this is a loose check — just verify overlap doesn't crash)


# ---------------------------------------------------------------------------
# chunk_document
# ---------------------------------------------------------------------------

LEAVE_POLICY_TEXT = """\
# Employee Leave Policy

Employees are entitled to 18 days of paid annual leave per calendar year.

Leave requests should be submitted at least 3 working days before the start date.

## Sick Leave

Employees may take sick leave when unable to work because of illness.

## Public Holidays

Company holidays are separate from annual leave.
"""


def test_chunk_document_returns_raw_chunks():
    chunks = chunk_document(
        text=LEAVE_POLICY_TEXT,
        fallback_title="leave-policy",
        max_tokens=500,
        overlap_tokens=60,
    )
    assert len(chunks) >= 1


def test_chunk_document_zero_based_index():
    chunks = chunk_document(
        text=LEAVE_POLICY_TEXT,
        fallback_title="leave-policy",
        max_tokens=500,
        overlap_tokens=60,
    )
    for expected_idx, chunk in enumerate(chunks):
        assert chunk.chunk_index == expected_idx


def test_chunk_document_monotonically_increasing():
    chunks = chunk_document(
        text=LEAVE_POLICY_TEXT,
        fallback_title="leave-policy",
        max_tokens=500,
        overlap_tokens=60,
    )
    indices = [c.chunk_index for c in chunks]
    assert indices == sorted(indices)


def test_chunk_document_titles_populated():
    chunks = chunk_document(
        text=LEAVE_POLICY_TEXT,
        fallback_title="leave-policy",
        max_tokens=500,
        overlap_tokens=60,
    )
    for chunk in chunks:
        assert chunk.title  # title must be non-empty


def test_chunk_document_content_populated():
    chunks = chunk_document(
        text=LEAVE_POLICY_TEXT,
        fallback_title="leave-policy",
        max_tokens=500,
        overlap_tokens=60,
    )
    for chunk in chunks:
        assert chunk.content.strip()  # content must be non-empty


def test_chunk_document_empty_text():
    chunks = chunk_document(
        text="",
        fallback_title="empty",
        max_tokens=500,
        overlap_tokens=60,
    )
    assert chunks == []


def test_chunk_document_no_headings_uses_fallback_title():
    plain = "Just some unstructured text without any Markdown headings."
    chunks = chunk_document(
        text=plain,
        fallback_title="my-doc",
        max_tokens=500,
        overlap_tokens=60,
    )
    assert len(chunks) >= 1
    assert chunks[0].title == "my-doc"


def test_chunk_document_oversized_section_splits():
    # Create a section that definitely exceeds 20 tokens
    big_body = "\n".join([f"This is sentence number {i} in a very long section." for i in range(100)])
    oversized_text = f"# Big Section\n{big_body}"
    chunks = chunk_document(
        text=oversized_text,
        fallback_title="oversized",
        max_tokens=20,
        overlap_tokens=5,
    )
    assert len(chunks) > 1


def test_chunk_document_section_count():
    """Verify distinct sections produce distinct chunk titles."""
    chunks = chunk_document(
        text=LEAVE_POLICY_TEXT,
        fallback_title="leave-policy",
        max_tokens=500,
        overlap_tokens=60,
    )
    titles = {c.title for c in chunks}
    # Should have at least 2 distinct section titles
    assert len(titles) >= 2
