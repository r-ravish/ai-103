<!-- onboarding/README.md -->

# Onboarding Module — Document Ingestion Service

**Owner:** Rakshit | **Branch:** `feature/onboarding-day4` | **Status:** Production-deployed

This module provides the **document ingestion pipeline** for the Enterprise Knowledge Agent.  
It accepts document uploads, parses them, chunks the content, generates embeddings, and indexes all chunks into `enterprise-knowledge-index` on Azure AI Search — making them immediately searchable by the RAG agent via `POST /chat`.

> The onboarding endpoint is mounted directly on the shared FastAPI backend (`backend/app/main.py`) and is accessible at the same URL as the rest of the API. No separate service or port is required.

---

## Table of Contents

1. [What this module does](#what-this-module-does)
2. [Pipeline architecture](#pipeline-architecture)
3. [API endpoints](#api-endpoints)
4. [Accepted file types](#accepted-file-types)
5. [How to upload a document (curl)](#how-to-upload-a-document-curl)
6. [How to verify ingestion status](#how-to-verify-ingestion-status)
7. [Production verification](#production-verification)
8. [How chunking works](#how-chunking-works)
9. [The 11-field ingestion contract](#the-11-field-ingestion-contract)
10. [Running unit tests](#running-unit-tests)
11. [Module structure](#module-structure)

---

## What this module does

When a document is uploaded through `POST /onboarding/upload`:

1. The file is validated (type, size).
2. Text is extracted from the document (Markdown, PDF, TXT, DOCX).
3. The text is split into semantically coherent chunks using **structure-first chunking**.
4. Each chunk is embedded using Azure OpenAI **`text-embedding-3-small`** (1536 dims).
5. Chunks are assembled into 11-field index records matching `docs/ingestion-contract.md`.
6. Records are uploaded to **`enterprise-knowledge-index`** on Azure AI Search.

After ingestion, the document is **immediately searchable** by the agent via `POST /chat`.

`GET /onboarding/documents` and `GET /onboarding/status/{document_id}` query the live index to give an admin real-time visibility into what is indexed and how many chunks each document produced.

---

## Pipeline architecture

```
Client (admin)
     │
     ▼  POST /onboarding/upload  (multipart/form-data)
     │
  FastAPI backend  (backend/app/main.py → routes/onboarding.py)
     │
     ├── 1. Validate       — extension, size
     ├── 2. Parse          — backend/scripts/ingest_pilot_documents.py
     │     ├── .md  → strip YAML frontmatter → plain text
     │     ├── .txt → read as-is
     │     ├── .pdf → pypdf page extraction
     │     └── .docx→ python-docx paragraphs
     ├── 3. Chunk          — structure-first (headings) → 500-tok fallback
     ├── 4. Embed          — Azure OpenAI text-embedding-3-small (batch 16)
     ├── 5. Build records  — 11-field contract (id, document_id, chunk_index, ...)
     └── 6. Index          — Azure AI Search: enterprise-knowledge-index

     ▼ GET /onboarding/status/{document_id}
     └── Live query to Azure AI Search → returns chunk-level metadata

     ▼ GET /onboarding/documents
     └── Live query to Azure AI Search → one row per distinct document_id
```

---

## API endpoints

All endpoints are mounted under the shared backend with the `/onboarding` prefix.

### `POST /onboarding/upload`

Upload and ingest a document.

**Request** — `multipart/form-data`

| Field | Required | Description |
|---|---|---|
| `file` | **Yes** | Document file (.md, .txt, .pdf, .docx) |

**Response** — `200 OK`

```json
{
  "document_id": "leave-policy",
  "filename": "leave-policy.md",
  "title": "Employee Leave Policy",
  "status": "ingested",
  "chunks_count": 4,
  "uploaded_at": "2026-09-21T13:30:00+00:00"
}
```

**Error codes**

| HTTP | Reason |
|---|---|
| `400` | Empty file or missing filename |
| `415` | Unsupported file extension |
| `500` | Chunking, embedding, or Azure Search failure |

---

### `GET /onboarding/documents`

List all documents currently indexed in `enterprise-knowledge-index`.

**Response** — `200 OK`

```json
{
  "documents": [
    {
      "document_id": "leave-policy",
      "filename": "leave-policy.md",
      "title": "Employee Leave Policy",
      "status": "ingested",
      "chunks_count": 4,
      "uploaded_at": "2026-09-20T10:00:00Z"
    }
  ],
  "total": 5,
  "source": "live"
}
```

The `source` field is `"live"` when the data comes from Azure AI Search, or `"fallback"` when Azure credentials are not configured (local dev without `.env`).

---

### `GET /onboarding/status/{document_id}`

Per-document ingestion status with full chunk-level detail.

**Example:** `GET /onboarding/status/leave-policy`

**Response** — `200 OK`

```json
{
  "document_id": "leave-policy",
  "filename": "leave-policy.md",
  "title": "Employee Leave Policy",
  "status": "ingested",
  "chunks_count": 4,
  "uploaded_at": "2026-09-20T10:00:00Z",
  "permission_tags": ["all-employees"],
  "document_type": "policy",
  "source": "live",
  "chunks": [
    {
      "id": "leave-policy_000",
      "chunk_index": 0,
      "title": "Employee Leave Policy",
      "content_preview": "Employees are entitled to 18 days of paid annual leave…",
      "source_file": "leave-policy.md",
      "ingested_at": "2026-09-20T10:00:00Z"
    }
  ]
}
```

| HTTP | Reason |
|---|---|
| `404` | Document not found in the index |

---

## Accepted file types

| Extension | Parser |
|---|---|
| `.md` | Built-in: strip YAML frontmatter, return text |
| `.txt` | Built-in: read as UTF-8 |
| `.pdf` | pypdf: page-by-page text extraction |
| `.docx` | python-docx: paragraph extraction |

---

## How to upload a document (curl)

```bash
# Upload a Markdown policy file
curl -X POST https://<backend-url>/onboarding/upload \
  -F "file=@docs/pilot-documents/leave-policy.md"

# Upload a PDF
curl -X POST https://<backend-url>/onboarding/upload \
  -F "file=@my-policy.pdf"
```

Using the **Swagger UI** (available at `https://<backend-url>/docs`):
1. Navigate to `POST /onboarding/upload`
2. Click **Try it out**
3. Choose a file and click **Execute**

---

## How to verify ingestion status

```bash
# Check status of a specific document
curl https://<backend-url>/onboarding/status/leave-policy

# List all indexed documents
curl https://<backend-url>/onboarding/documents

# General health check
curl https://<backend-url>/health
```

---

## Production verification

Use `onboarding/scripts/verify_production.py` to run an end-to-end verification against the live deployment:

```bash
# Verify against Azure Container Apps deployment
python onboarding/scripts/verify_production.py \
    --url https://<your-backend-url> \
    --file docs/pilot-documents/leave-policy.md

# Verify against localhost
python onboarding/scripts/verify_production.py \
    --url http://localhost:8000 \
    --file docs/pilot-documents/leave-policy.md
```

The script runs 5 checks:

| Step | What it verifies |
|---|---|
| 1 | Backend health check (`GET /health`) |
| 2 | Document upload (`POST /onboarding/upload`) — status `ingested`, chunks > 0 |
| 3 | Ingestion status (`GET /onboarding/status/{id}`) — live chunk metadata |
| 4 | Document list (`GET /onboarding/documents`) — doc appears in index |
| 5 | RAG retrieval (`POST /chat`) — agent answers from the uploaded doc without escalation |

Exit code is `0` if all checks pass, `1` otherwise.

---

## How chunking works

The module uses **structure-first chunking** (as specified in `docs/ingestion-contract.md`):

1. The document is split by Markdown headings (`#`, `##`, `###`, etc.) into sections.
2. Each section that fits within **500 tokens** is kept as a single chunk.
3. Sections that exceed 500 tokens are further split with **60-token overlap** between consecutive chunks.
4. `chunk_index` is zero-based and monotonically increasing across the entire document.
5. Each chunk inherits the title of the heading section it belongs to.

Tokenisation uses `tiktoken` with the `text-embedding-3-small` encoding — identical to the pilot ingestion script.

---

## The 11-field ingestion contract

Every indexed record contains exactly these 11 fields (from `docs/ingestion-contract.md`):

| Field | Type | Description |
|---|---|---|
| `id` | `Edm.String` | Index key: `{document_id}_{chunk_index:03d}` |
| `document_id` | `Edm.String` | Stable document identifier (filename stem) |
| `chunk_index` | `Edm.Int32` | Zero-based chunk ordering |
| `title` | `Edm.String` | Section heading for this chunk |
| `content` | `Edm.String` | Chunk text |
| `embedding` | `Collection(Edm.Single)` | 1536-dimensional vector |
| `source_file` | `Edm.String` | Original filename |
| `source_path` | `Edm.String` | Path within the repository |
| `document_type` | `Edm.String` | Logical type: `policy`, `faq`, etc. |
| `permission_tags` | `Collection(Edm.String)` | Access-control groups |
| `ingested_at` | `Edm.DateTimeOffset` | UTC ingestion timestamp |

---

## Running unit tests

All tests are fully offline — no Azure credentials required.

```bash
# From the repo root
pip install pytest

# Run all onboarding tests
pytest onboarding/tests/ -v

# Run individual test files
pytest onboarding/tests/test_chunking.py -v   # 16 tests
pytest onboarding/tests/test_parsing.py -v    # 13 tests
pytest onboarding/tests/test_indexing.py -v   # 11 tests
pytest onboarding/tests/test_router.py -v     # 15 tests
```

Expected output: **55/55 passed**.

---

## Module structure

```
onboarding/
├── README.md                      ← this file
├── requirements.txt               ← Python dependencies
├── .env.example                   ← environment variable template
│
├── scripts/
│   ├── smoke_test.py              ← local end-to-end pipeline test (port 8002)
│   └── verify_production.py      ← production verification against live backend
│
└── tests/
    ├── __init__.py
    ├── test_chunking.py           ← 16 unit tests: structure-first chunking
    ├── test_parsing.py            ← 13 unit tests: frontmatter, MD/TXT/extension
    ├── test_indexing.py           ← 11 unit tests: 11-field record building
    └── test_router.py             ← 15 integration tests: HTTP routes (mocked Azure)
```

The **route implementation** lives in `backend/routes/onboarding.py` (mounted onto the shared FastAPI app). The **chunking/parsing logic** is shared with the pilot ingestion script at `backend/scripts/ingest_pilot_documents.py`.
