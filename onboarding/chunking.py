"""
onboarding/chunking.py
----------------------
Structure-first chunking as defined in docs/ingestion-contract.md.

Policy:
  1. Split the document by Markdown headings/sections.
  2. Keep a section together when it is at or below MAX_TOKENS_PER_CHUNK.
  3. When a section exceeds the limit, split into token-based chunks with
     OVERLAP_TOKENS of overlap between consecutive chunks.
  4. Preserve chunk_index ordering (zero-based, monotonically increasing).
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

import tiktoken

logger = logging.getLogger(__name__)

# Use the encoding that matches text-embedding-3-small
_ENCODING = tiktoken.encoding_for_model("text-embedding-3-small")

_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)


@dataclass
class RawChunk:
    """
    A single text chunk before embedding is added.

    Fields mirror the 11-field contract (embedding is added later by the
    indexing layer).
    """
    chunk_index: int
    title: str
    content: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_into_sections(text: str, fallback_title: str) -> list[tuple[str, str]]:
    """
    Split *text* by Markdown headings into (title, body) pairs.

    If the document has no headings, the whole text is returned as a single
    section with *fallback_title* as the title.
    """
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    current_title = fallback_title
    current_lines: list[str] = []

    for line in lines:
        if _HEADING_RE.match(line):
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append((current_title, body))
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_title, body))

    # Filter empty sections
    return [(t, b) for t, b in sections if b]


def _token_based_split(
    text: str,
    max_tokens: int,
    overlap: int,
) -> list[str]:
    """
    Split *text* into chunks of at most *max_tokens* with *overlap* tokens
    of context carried over between consecutive chunks.

    If the text fits within *max_tokens*, it is returned as a single-element list.
    """
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunks.append(_ENCODING.decode(chunk_tokens))
        if end >= len(tokens):
            break
        start = end - overlap

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_document(
    text: str,
    fallback_title: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[RawChunk]:
    """
    Apply structure-first chunking to *text* and return an ordered list of
    :class:`RawChunk` objects ready for embedding.

    Parameters
    ----------
    text : str
        Extracted document text (frontmatter already stripped).
    fallback_title : str
        Title used for sections that have no Markdown heading (typically the
        document_id / filename stem).
    max_tokens : int
        Maximum tokens per chunk (contract default: 500).
    overlap_tokens : int
        Token overlap between consecutive fallback chunks (contract default: 60).

    Returns
    -------
    list[RawChunk]
        Zero-indexed list of chunks preserving source-document order.
    """
    sections = _split_into_sections(text, fallback_title)

    if not sections:
        logger.warning("No sections extracted from document; creating a single chunk.")
        if text.strip():
            sections = [(fallback_title, text.strip())]
        else:
            return []

    result: list[RawChunk] = []
    chunk_index = 0

    for title, body in sections:
        pieces = _token_based_split(body, max_tokens, overlap_tokens)
        for piece in pieces:
            if not piece.strip():
                continue
            result.append(RawChunk(
                chunk_index=chunk_index,
                title=title,
                content=piece.strip(),
            ))
            chunk_index += 1

    logger.info(
        "Chunked document into %d chunks across %d section(s).",
        len(result),
        len(sections),
    )
    return result
