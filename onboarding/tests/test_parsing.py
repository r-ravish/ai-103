"""
onboarding/tests/test_parsing.py
---------------------------------
Unit tests for the parsing module.

These tests are fully offline — no Azure calls are made.
Run with: pytest onboarding/tests/test_parsing.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from onboarding.parsing import (
    _parse_markdown,
    _parse_txt,
    _strip_frontmatter,
    extract_text,
)


# ---------------------------------------------------------------------------
# _strip_frontmatter
# ---------------------------------------------------------------------------

def test_strip_frontmatter_removes_block():
    text = "---\ntitle: Test\n---\n\n# Hello"
    result = _strip_frontmatter(text)
    assert "title:" not in result
    assert "Hello" in result


def test_strip_frontmatter_no_frontmatter():
    text = "# No frontmatter here\nJust content."
    result = _strip_frontmatter(text)
    assert result == text


def test_strip_frontmatter_only_removes_leading():
    text = "---\nkey: val\n---\nContent\n---\nnot-frontmatter\n---"
    result = _strip_frontmatter(text)
    assert "key:" not in result
    # Trailing --- blocks should remain
    assert "not-frontmatter" in result


# ---------------------------------------------------------------------------
# _parse_markdown
# ---------------------------------------------------------------------------

def test_parse_markdown_strips_frontmatter():
    md = b"---\ndocument_id: test\n---\n# Heading\nContent here."
    result = _parse_markdown(md)
    assert "document_id" not in result
    assert "Heading" in result


def test_parse_markdown_no_frontmatter():
    md = b"# Title\nSome content."
    result = _parse_markdown(md)
    assert "Title" in result


def test_parse_markdown_utf8_decoded():
    md = "# Héllo Wörld\nContent.".encode("utf-8")
    result = _parse_markdown(md)
    assert "Héllo" in result


# ---------------------------------------------------------------------------
# _parse_txt
# ---------------------------------------------------------------------------

def test_parse_txt_basic():
    txt = b"Hello, world!"
    assert _parse_txt(txt) == "Hello, world!"


def test_parse_txt_multiline():
    txt = b"Line 1\nLine 2\nLine 3"
    result = _parse_txt(txt)
    assert "Line 1" in result
    assert "Line 3" in result


# ---------------------------------------------------------------------------
# extract_text dispatch
# ---------------------------------------------------------------------------

def test_extract_text_md():
    content = b"# Policy\nThis is policy content."
    result = extract_text("leave-policy.md", content)
    assert "Policy" in result


def test_extract_text_txt():
    content = b"Plain text content."
    result = extract_text("notes.txt", content)
    assert "Plain text content." in result


def test_extract_text_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("file.xyz", b"data")


def test_extract_text_uppercase_extension():
    """Extensions should be case-insensitive."""
    content = b"# Policy\nContent."
    result = extract_text("POLICY.MD", content)
    assert "Policy" in result


def test_extract_text_md_with_frontmatter():
    content = (
        b"---\n"
        b"document_id: DOC-LEAVE-001\n"
        b"title: Employee Leave Policy\n"
        b"---\n\n"
        b"# Employee Leave Policy\n\n"
        b"Employees are entitled to 18 days of paid annual leave.\n"
    )
    result = extract_text("leave-policy.md", content)
    assert "document_id" not in result
    assert "Employee Leave Policy" in result
    assert "18 days" in result
