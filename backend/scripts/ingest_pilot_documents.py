import os
import re
from datetime import datetime, timezone
from pathlib import Path

import tiktoken
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# --- Config ---
SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
SEARCH_ADMIN_KEY = os.environ["AZURE_SEARCH_ADMIN_KEY"]
INDEX_NAME = "enterprise-knowledge-index"

AOAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AOAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AOAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
AOAI_EMBEDDING_DEPLOYMENT = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]

DOCS_DIR = Path(os.environ.get("PILOT_DOCS_DIR", "docs/pilot-documents"))
MAX_TOKENS = 500
OVERLAP_TOKENS = 60
EMBED_BATCH_SIZE = 16
UPLOAD_BATCH_SIZE = 100

# Per-file metadata — document_type and permission_tags for every pilot doc.
# These are not read from frontmatter (see docs/ingestion-contract.md).
# Add new entries here when new documents are introduced.
DOCUMENT_TYPE_MAP = {
    "employee-benefits.md": "policy",
    "leave-policy.md": "policy",
    "reimbursement-policy.md": "policy",
    "work-from-home-policy.md": "policy",
    "it-security-policy.md": "policy",
}
PERMISSION_TAGS_MAP = {
    "employee-benefits.md": ["all-employees"],
    "leave-policy.md": ["all-employees"],
    "reimbursement-policy.md": ["all-employees"],
    "work-from-home-policy.md": ["all-employees"],
    "it-security-policy.md": ["all-employees", "it"],
}

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

_encoding = None

def get_encoding():
    global _encoding
    if _encoding is None:
        try:
            _encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    return _encoding


def strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block (--- ... ---) if present."""
    return FRONTMATTER_PATTERN.sub("", text, count=1).lstrip()


def split_into_sections(text: str, fallback_title: str):
    """Split markdown into (title, body) sections by heading. Falls back to whole doc."""
    lines = text.splitlines()
    sections = []
    current_title = fallback_title
    current_lines = []
    for line in lines:
        if re.match(r"^#{1,6}\s+", line):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return [s for s in sections if s[1]]


def chunk_text(text: str, max_tokens: int = MAX_TOKENS, overlap: int = OVERLAP_TOKENS):
    """Token-based chunking with overlap, only used when a section exceeds max_tokens."""
    enc = get_encoding()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunks.append(enc.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start = end - overlap
    return chunks


def extract_file_text(path: Path) -> str:
    """Extract plain text from .md, .txt, .pdf, or other policy documents safely."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            if pages_text:
                return "\n\n".join(pages_text)
        except Exception:
            pass

    return path.read_text(encoding="utf-8", errors="ignore")


def build_chunks_for_file(path: Path):
    raw_text = extract_file_text(path)
    text = strip_frontmatter(raw_text)

    document_id = path.stem
    document_type = DOCUMENT_TYPE_MAP.get(path.name, "policy")
    permission_tags = PERMISSION_TAGS_MAP.get(path.name, ["all-employees"])
    ingested_at = datetime.now(timezone.utc).isoformat()

    sections = split_into_sections(text, fallback_title=document_id)

    records = []
    chunk_index = 0
    for title, body in sections:
        for piece in chunk_text(body):
            records.append(
                {
                    "id": f"{document_id}_{chunk_index:03d}",
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "title": title,
                    "content": piece,
                    "source_file": path.name,
                    "source_path": str(path),
                    "document_type": document_type,
                    "permission_tags": permission_tags,
                    "ingested_at": ingested_at,
                }
            )
            chunk_index += 1
    return records


def embed_records(client: AzureOpenAI, records: list):
    for i in range(0, len(records), EMBED_BATCH_SIZE):
        batch = records[i : i + EMBED_BATCH_SIZE]
        response = client.embeddings.create(
            model=AOAI_EMBEDDING_DEPLOYMENT,
            input=[r["content"] for r in batch],
        )
        for record, item in zip(batch, response.data):
            record["embedding"] = item.embedding


def upload_records(search_client: SearchClient, records: list):
    for i in range(0, len(records), UPLOAD_BATCH_SIZE):
        batch = records[i : i + UPLOAD_BATCH_SIZE]
        result = search_client.upload_documents(documents=batch)
        failed = [r for r in result if not r.succeeded]
        if failed:
            print(f"  {len(failed)} documents failed to upload: {[f.key for f in failed]}")


def main():
    aoai_client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_API_KEY,
        api_version=AOAI_API_VERSION,
    )
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_ADMIN_KEY),
    )

    md_files = sorted(DOCS_DIR.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {DOCS_DIR}")
        return

    all_records = []
    for path in md_files:
        records = build_chunks_for_file(path)
        print(f"{path.name}: {len(records)} chunks")
        all_records.extend(records)

    print(f"Embedding {len(all_records)} chunks...")
    embed_records(aoai_client, all_records)

    print("Uploading to Azure AI Search...")
    upload_records(search_client, all_records)

    print(f"Done. Indexed {len(all_records)} chunks from {len(md_files)} document(s).")


if __name__ == "__main__":
    main()