"""
onboarding/parsing.py
---------------------
Document parsing and text extraction layer.

Supports:
  • Markdown (.md)   — strip YAML frontmatter, return raw text.
  • Plain text (.txt) — return as-is.
  • PDF (.pdf)        — Azure AI Document Intelligence (preferred) with
                        pypdf as a graceful fallback when DI is not configured.
  • DOCX (.docx)      — python-docx word extraction.

All public functions return a plain str (extracted text).
"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block if present."""
    return _FRONTMATTER_PATTERN.sub("", text, count=1).lstrip()


def _parse_markdown(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    return _strip_frontmatter(text)


def _parse_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _parse_pdf_with_document_intelligence(content: bytes) -> str:
    """
    Use Azure AI Document Intelligence (prebuilt-read model) to extract text
    from a PDF byte string.  Returns the full concatenated text.

    Raises RuntimeError if DI credentials are missing or the API call fails.
    """
    from azure.ai.formrecognizer import DocumentAnalysisClient  # type: ignore
    from azure.core.credentials import AzureKeyCredential

    try:
        from onboarding import config
    except ImportError:
        import config  # type: ignore

    endpoint = config.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
    key = config.AZURE_DOCUMENT_INTELLIGENCE_KEY

    if not endpoint or not key:
        raise RuntimeError(
            "Azure Document Intelligence credentials are not configured.  "
            "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
            "AZURE_DOCUMENT_INTELLIGENCE_KEY in your .env file."
        )

    client = DocumentAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )

    logger.info("Submitting PDF to Azure Document Intelligence (prebuilt-read).")
    poller = client.begin_analyze_document("prebuilt-read", document=io.BytesIO(content))
    result = poller.result()

    pages_text: list[str] = []
    for page in result.pages:
        page_lines = [line.content for line in (page.lines or [])]
        pages_text.append("\n".join(page_lines))

    extracted = "\n\n".join(pages_text)
    logger.info("Document Intelligence extracted %d characters.", len(extracted))
    return extracted


def _parse_pdf_fallback(content: bytes) -> str:
    """
    Extract text from a PDF using pypdf (pure-Python fallback).
    Used when Document Intelligence is not configured.
    """
    try:
        import pypdf  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is not installed.  Run: pip install pypdf"
        ) from exc

    reader = pypdf.PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)

    extracted = "\n\n".join(pages)
    logger.info("pypdf fallback extracted %d characters.", len(extracted))
    return extracted


def _parse_docx(content: bytes) -> str:
    """Extract text from a .docx file using python-docx."""
    try:
        import docx  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is not installed.  Run: pip install python-docx"
        ) from exc

    doc = docx.Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    extracted = "\n\n".join(paragraphs)
    logger.info("python-docx extracted %d characters.", len(extracted))
    return extracted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text(filename: str, content: bytes) -> str:
    """
    Dispatch to the correct parser based on the file extension.

    Parameters
    ----------
    filename : str
        Original filename (used to determine the parser).
    content : bytes
        Raw file bytes.

    Returns
    -------
    str
        Extracted plain text.

    Raises
    ------
    ValueError
        If the file extension is not supported.
    RuntimeError
        If parsing fails (e.g. Document Intelligence call failure).
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".md":
        return _parse_markdown(content)

    if suffix == ".txt":
        return _parse_txt(content)

    if suffix == ".pdf":
        try:
            from onboarding import config as _config
        except ImportError:
            import config as _config  # type: ignore

        di_configured = bool(
            _config.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
            and _config.AZURE_DOCUMENT_INTELLIGENCE_KEY
        )

        if di_configured:
            logger.info("PDF detected — using Azure Document Intelligence.")
            return _parse_pdf_with_document_intelligence(content)
        else:
            logger.warning(
                "PDF detected but Document Intelligence is not configured — "
                "falling back to pypdf.  Results may be lower quality."
            )
            return _parse_pdf_fallback(content)

    if suffix == ".docx":
        return _parse_docx(content)

    raise ValueError(
        f"Unsupported file type: '{suffix}'.  "
        "Accepted extensions: .pdf, .md, .txt, .docx"
    )
