<!-- onboarding/README.md -->

# Onboarding Module

**Document ingestion service for the Enterprise Knowledge Agent.**

This module accepts document uploads, parses them, chunks the content, generates embeddings, and indexes all chunks into `enterprise-knowledge-index` using the exact 11-field schema defined in [`docs/ingestion-contract.md`](../docs/ingestion-contract.md).

Owner: **Rakshit** | Branch: `feature/onboarding`

---

## Table of Contents

1. [What this module does](#what-this-module-does)
2. [Architecture](#architecture)
3. [API endpoints](#api-endpoints)
4. [Accepted file types](#accepted-file-types)
5. [How document parsing works](#how-document-parsing-works)
6. [How chunking works](#how-chunking-works)
7. [How embeddings are generated](#how-embeddings-are-generated)
8. [How documents are indexed](#how-documents-are-indexed)
9. [The 11-field ingestion contract](#the-11-field-ingestion-contract)
10. [Required environment variables](#required-environment-variables)
11. [Running locally (standalone)](#running-locally-standalone)
12. [Mounting onto the main backend](#mounting-onto-the-main-backend)
13. [How to test an upload](#how-to-test-an-upload)
14. [How to check ingestion status](#how-to-check-ingestion-status)
15. [Running unit tests](#running-unit-tests)
16. [Error handling](#error-handling)
17. [Module structure](#module-structure)

---

## What this module does

The onboarding module provides a production-ready HTTP API for ingesting documents into the project's Azure AI Search knowledge base.

When a document is uploaded:

1. The file is validated (type, size).
2. Text is extracted (Markdown, PDF, DOCX, TXT).
3. The extracted text is split into semantically coherent chunks using structure-first chunking.
4. Each chunk is embedded using Azure OpenAI `text-embedding-3-small`.
5. Chunks are assembled into 11-field index records matching the ingestion contract.
6. Records are uploaded to `enterprise-knowledge-index` in Azure AI Search.

After ingestion, the document is immediately searchable by the RAG system (`POST /chat`).

---

## Architecture

```
Client
  │
  ▼ POST /onboarding/upload  (multipart/form-data)
  │
FastAPI Router (onboarding/router.py)
  │
  ├── Validate file (type, size)
  │
  ▼
Service Layer (onboarding/service.py)
  │
  ├── 1. Parse     → onboarding/parsing.py
  │     ├── .md    → strip YAML frontmatter, return text
  │     ├── .txt   → return as-is
  │     ├── .pdf   → Azure Document Intelligence  (→ pypdf fallback)
  │     └── .docx  → python-docx
  │
  ├── 2. Chunk     → onboarding/chunking.py
  │     ├── Split by Markdown headings
  │     └── Token-based fallback (500 tok max, 60 tok overlap)
  │
  ├── 3. Embed     → onboarding/embedding.py
  │     └── Azure OpenAI text-embedding-3-small  (batch=16)
  │
  ├── 4. Build records → onboarding/indexing.py
  │     └── 11-field contract (id, document_id, chunk_index, ...)
  │
  └── 5. Upload    → onboarding/indexing.py
        └── Azure AI Search: enterprise-knowledge-index
```

---

## API endpoints

All endpoints are prefixed with `/onboarding`.

### `POST /onboarding/upload`

Upload and ingest a document.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | Yes | Document to ingest (.pdf, .md, .txt, .docx) |
| `document_type` | string | No | Logical type: `policy`, `faq`, `ticket-data`. Default: `policy` |
| `permission_tags` | string | No | Comma-separated groups: `all-employees,hr`. Default: `all-employees` |
| `document_id` | string | No | Explicit stable ID. Derived from filename if omitted. |
| `title` | string | No | Human-readable title. Derived from filename if omitted. |

**Response** — `200 OK`

```json
{
  "document_id": "leave-policy",
  "source_file": "leave-policy.md",
  "document_type": "policy",
  "permission_tags": ["all-employees"],
  "total_chunks": 4,
  "indexed_chunks": 4,
  "ingested_at": "2026-09-21T00:00:00+00:00",
  "chunks": [
    {
      "chunk_index": 0,
      "title": "Employee Leave Policy",
      "content_preview": "Employees are entitled to 18 days of paid annual leave..."
    }
  ],
  "message": "Successfully ingested 'leave-policy.md' as document_id='leave-policy'. 4/4 chunks indexed."
}
```

**Error responses**

| HTTP | Condition |
|---|---|
| `400` | File is empty |
| `413` | File exceeds 50 MB limit |
| `415` | Unsupported file type |
| `422` | Document produced no extractable text |
| `502` | Azure AI Search or OpenAI failure |

---

### `GET /onboarding/status/{document_id}`

Check ingestion status for a document.

**Response** — `200 OK`

```json
{
  "document_id": "leave-policy",
  "status": "completed",
  "source_file": "leave-policy.md",
  "document_type": "policy",
  "permission_tags": ["all-employees"],
  "total_chunks": 4,
  "ingested_at": "2026-09-21T00:00:00+00:00",
  "chunks": [
    {
      "id": "leave-policy_000",
      "chunk_index": 0,
      "title": "Employee Leave Policy",
      "content_preview": "Employees are entitled to 18 days...",
      "source_file": "leave-policy.md",
      "ingested_at": "2026-09-21T00:00:00+00:00"
    }
  ]
}
```

| HTTP | Condition |
|---|---|
| `404` | Document not found in the index |
| `502` | Azure AI Search unreachable |

---

### `GET /onboarding/documents`

List all ingested documents.

**Query parameters**

| Param | Default | Description |
|---|---|---|
| `limit` | 100 | Max records to return (1–1000) |

**Response** — `200 OK`

```json
{
  "total": 6,
  "documents": [
    {
      "document_id": "leave-policy",
      "source_file": "leave-policy.md",
      "document_type": "policy",
      "permission_tags": ["all-employees"],
      "total_chunks": 4,
      "ingested_at": "2026-09-21T00:00:00+00:00",
      "status": "completed"
    }
  ]
}
```

---

### `DELETE /onboarding/documents/{document_id}`

Remove all chunks for a document from the index.

**Response** — `200 OK`

```json
{
  "document_id": "leave-policy",
  "deleted_chunks": 4,
  "message": "Deleted 4 chunk(s) for document_id='leave-policy'."
}
```

| HTTP | Condition |
|---|---|
| `404` | Document not found |
| `502` | Azure AI Search failure |

---

### `GET /onboarding/health`

Check service configuration and Azure Search connectivity.

**Response** — `200 OK`

```json
{
  "status": "ok",
  "azure_search": "ok — index exists",
  "azure_openai": "configured",
  "azure_document_intelligence": "not configured (pypdf fallback active for PDFs)",
  "index_name": "enterprise-knowledge-index"
}
```

---

## Accepted file types

| Extension | Parser | Notes |
|---|---|---|
| `.md` | Built-in | YAML frontmatter stripped automatically |
| `.txt` | Built-in | UTF-8 decoded |
| `.pdf` | Azure Document Intelligence | Falls back to pypdf if DI not configured |
| `.docx` | python-docx | Paragraphs extracted |

Maximum upload size: **50 MB** (configurable via `MAX_UPLOAD_SIZE_MB`).

---

## How document parsing works

### Markdown (`.md`)
YAML frontmatter blocks (`--- ... ---`) are stripped before any processing.  
The pilot documents all contain frontmatter (`document_id`, `title`, `permissions_tag`) — this is removed so it doesn't pollute chunk content or embeddings.

### Plain text (`.txt`)
Decoded as UTF-8 and returned as-is.

### PDF (`.pdf`)
1. **Azure AI Document Intelligence** (`prebuilt-read` model) — used when `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_KEY` are configured. Extracts text page-by-page, preserving layout and handling scanned/image PDFs.
2. **pypdf fallback** — used when Document Intelligence is not configured. Suitable for text-based PDFs; image-only PDFs will produce empty output.

### DOCX (`.docx`)
python-docx extracts paragraph text from the document body.

---

## How chunking works

The module implements **structure-first chunking** as specified in the ingestion contract:

1. The document is split by Markdown heading levels (`#`, `##`, etc.) into sections.
2. Each section that fits within **500 tokens** is kept as a single chunk.
3. Sections exceeding 500 tokens are further split into token-based chunks with **60-token overlap** between consecutive chunks.
4. `chunk_index` is zero-based and monotonically increasing across the entire document.
5. Each chunk carries the title of the section it belongs to.

The tokeniser used is `tiktoken` with the `text-embedding-3-small` encoding, matching the pilot scripts exactly.

---

## How embeddings are generated

- **Model**: Azure OpenAI `text-embedding-3-small`
- **Dimensions**: 1536
- **Input**: The `content` field of each chunk
- **Batch size**: 16 chunks per API call (configurable)
- **Client**: `openai.AzureOpenAI` with `azure_endpoint`, `api_key`, `api_version`

The same model and deployment **must** be used for query embeddings in the RAG system. Changing the embedding model would break retrieval.

---

## How documents are indexed

Each chunk produces one record conforming to the 11-field contract. Records are uploaded to `enterprise-knowledge-index` in batches of 100 via `azure-search-documents`.

The `id` field is the index key and is formatted as:

```
{document_id}_{chunk_index:03d}
```

Examples: `leave-policy_000`, `leave-policy_001`, `leave-policy_002`

---

## The 11-field ingestion contract

Every indexed record contains exactly these fields (from `docs/ingestion-contract.md`):

| Field | Type | Description |
|---|---|---|
| `id` | `Edm.String` | Index key: `{document_id}_{chunk_index:03d}` |
| `document_id` | `Edm.String` | Stable document identifier |
| `chunk_index` | `Edm.Int32` | Zero-based chunk ordering |
| `title` | `Edm.String` | Section heading associated with the chunk |
| `content` | `Edm.String` | Chunk text |
| `embedding` | `Collection(Edm.Single)` | 1536-dim vector |
| `source_file` | `Edm.String` | Original filename |
| `source_path` | `Edm.String` | Upload path |
| `document_type` | `Edm.String` | Logical type (policy, faq, etc.) |
| `permission_tags` | `Collection(Edm.String)` | Access-control groups |
| `ingested_at` | `Edm.DateTimeOffset` | UTC ingestion timestamp |

---

## Required environment variables

Copy `onboarding/.env.example` to `onboarding/.env` and fill in your values.

| Variable | Required | Description |
|---|---|---|
| `AZURE_SEARCH_ENDPOINT` | **Yes** | Azure AI Search service URL |
| `AZURE_SEARCH_ADMIN_KEY` | **Yes** | Admin API key (write access) |
| `SEARCH_INDEX_NAME` | No | Default: `enterprise-knowledge-index` |
| `AZURE_OPENAI_ENDPOINT` | **Yes** | Azure OpenAI service URL |
| `AZURE_OPENAI_API_KEY` | **Yes** | Azure OpenAI API key |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | No | Default: `text-embedding-3-small` |
| `AZURE_OPENAI_API_VERSION` | No | Default: `2024-10-21` |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | No | Required for PDF parsing via DI |
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | No | Required for PDF parsing via DI |
| `MAX_TOKENS_PER_CHUNK` | No | Default: `500` |
| `OVERLAP_TOKENS` | No | Default: `60` |
| `MAX_UPLOAD_SIZE_MB` | No | Default: `50` |

> **Never commit real keys.** Store them only in `.env` (which is git-ignored).

---

## Running locally (standalone)

```bash
# 1. From the repo root, activate your virtual environment
source .venv/bin/activate

# 2. Install onboarding dependencies
pip install -r onboarding/requirements.txt

# 3. Configure environment variables
cp onboarding/.env.example onboarding/.env
# Edit onboarding/.env and fill in your Azure credentials

# 4. Run the onboarding service on port 8002
uvicorn onboarding.main:app --reload --port 8002
```

The interactive API docs are available at: **http://localhost:8002/docs**

---

## Mounting onto the main backend

To expose the onboarding routes via the same FastAPI app as `POST /chat`:

```python
# In backend/app/main.py, add:
from onboarding.router import router as onboarding_router
app.include_router(onboarding_router)
```

This requires `PYTHONPATH` to include the repo root, which is already the case when running from the repo root with `uvicorn app.main:app`.

---

## How to test an upload

### Using curl

```bash
# Upload a Markdown file
curl -X POST http://localhost:8002/onboarding/upload \
  -F "file=@docs/pilot-documents/leave-policy.md" \
  -F "document_type=policy" \
  -F "permission_tags=all-employees"
```

```bash
# Upload a PDF with Document Intelligence
curl -X POST http://localhost:8002/onboarding/upload \
  -F "file=@my-document.pdf" \
  -F "document_type=policy" \
  -F "permission_tags=all-employees,hr" \
  -F "document_id=my-document"
```

### Using the smoke test script

```bash
# Start the service (separate terminal)
uvicorn onboarding.main:app --reload --port 8002

# Run the smoke test
python onboarding/scripts/smoke_test.py
# or with a custom file:
python onboarding/scripts/smoke_test.py --file path/to/your/document.md
```

### Using the Swagger UI

Navigate to **http://localhost:8002/docs** → `POST /onboarding/upload` → **Try it out**.

---

## How to check ingestion status

```bash
# Status for a specific document
curl http://localhost:8002/onboarding/status/leave-policy

# List all ingested documents
curl http://localhost:8002/onboarding/documents

# Service health check
curl http://localhost:8002/onboarding/health
```

---

## Running unit tests

Tests are fully offline — no Azure credentials required.

```bash
# From the repo root
pip install pytest

# Run all onboarding tests
pytest onboarding/tests/ -v

# Run a specific test file
pytest onboarding/tests/test_chunking.py -v
pytest onboarding/tests/test_parsing.py -v
pytest onboarding/tests/test_indexing.py -v
pytest onboarding/tests/test_router.py -v
```

---

## Error handling

| Scenario | HTTP | Response |
|---|---|---|
| Unsupported file type | `415` | `{"detail": "Unsupported file type '.xyz'. Accepted: ..."}` |
| Empty file | `400` | `{"detail": "Uploaded file is empty."}` |
| File too large | `413` | `{"detail": "File exceeds maximum upload size of 50 MB."}` |
| No extractable text | `422` | `{"detail": "Document '...' produced no extractable text."}` |
| Document Intelligence failure | `502` | `{"detail": "Azure Document Intelligence API failed: ..."}` |
| Embedding generation failure | `502` | `{"detail": "Azure OpenAI embedding call failed: ..."}` |
| Azure AI Search upload failure | `502` | `{"detail": "N records failed to upload to Azure AI Search."}` |
| Document not found (status) | `404` | `{"detail": "No indexed chunks found for document_id='...'."}` |
| Unknown server error | `500` | `{"detail": "An unexpected error occurred: ..."}` |

---

## Module structure

```
onboarding/
├── __init__.py          — package marker
├── config.py            — all configuration from env vars
├── schemas.py           — Pydantic request/response models
├── parsing.py           — text extraction (MD, PDF, DOCX, TXT)
├── chunking.py          — structure-first chunking
├── embedding.py         — Azure OpenAI embedding generation
├── indexing.py          — Azure AI Search upload/query/delete
├── service.py           — orchestrator (parse→chunk→embed→index)
├── router.py            — FastAPI routes
├── main.py              — standalone FastAPI app entry point
├── requirements.txt     — Python dependencies
├── .env.example         — environment variable template
├── scripts/
│   └── smoke_test.py    — end-to-end local pipeline test
└── tests/
    ├── __init__.py
    ├── test_chunking.py — unit tests: chunking
    ├── test_parsing.py  — unit tests: parsing
    ├── test_indexing.py — unit tests: record building
    └── test_router.py   — integration tests: HTTP routes (mocked Azure)
```
