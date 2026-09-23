# Ingestion Contract

## Purpose

This document defines the agreed contract for converting source documents into chunks and indexing those chunks in Azure AI Search.

Rakshit's onboarding module should treat this document as the source of truth for the ingestion-side data shape and retrieval metadata.

## Current pilot architecture

```
Source documents
      ↓
Structure-first chunking
      ↓
Azure OpenAI: text-embedding-3-small
      ↓
1536-dimensional embedding
      ↓
Azure AI Search: enterprise-knowledge-index
```

---

## Day 1 architecture decisions and setup notes

This section records the key infrastructure decisions made during Day 1 so future team members understand not only the final architecture, but also why the resources are split across regions.

### Region constraint

The project used an Azure for Students subscription with a subscription-level resource deployment policy. The allowed deployment regions discovered during setup were:

- East Asia
- Korea Central
- South Central India
- Central India
- Malaysia West

Because of this policy, the main Foundry and Azure AI Search resources were created in **Central India**.

### Embedding model selection

The first model search was performed from the Microsoft Foundry project in Central India. `text-embedding-3-small` was not available in that project's general model catalog, so the team checked Azure OpenAI availability separately rather than switching the whole project to another region.

A separate Azure OpenAI resource was created in **Korea Central**, which was also permitted by the subscription policy. From that Azure OpenAI resource, `text-embedding-3-small` was available and was deployed using Global Standard.

**Final embedding setup:**

| Field | Value |
|---|---|
| Azure OpenAI resource | `ai103-openai-embedding` |
| Region | Korea Central |
| Model | `text-embedding-3-small` |
| Deployment name | `text-embedding-3-small` *(confirm this matches the value of `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` in your `.env` — deployment name and model name are independent in Azure and only coincide here because that's what it was named at creation)* |
| Deployment type | Global Standard |
| Dimensions | 1536 |

### Final Day 1 resource layout

```
Azure for Students subscription
│
├── Central India
│   ├── Microsoft Foundry project
│   │   └── ai-103-enterprise-knowledge-agent
│   └── Azure AI Search
│       └── ai103-enterprise-search-ravish
│           └── enterprise-knowledge-index
│
└── Korea Central
    └── Azure OpenAI
        └── ai103-openai-embedding
            └── text-embedding-3-small
```

The Search index remains in Central India, while the embedding model is hosted through the separate Azure OpenAI resource in Korea Central. The application therefore uses Azure OpenAI to generate both document and query embeddings, and Azure AI Search to store and retrieve the resulting vectors.

### Why this note is included

This decision history is intentionally recorded here so future contributors do not assume that the embedding model must be deployed in the same region as the Search service or Foundry project. Any future change to the model, deployment type, or resource region should be reviewed against the subscription's regional policy and current Azure model availability before modifying this contract.

---

## Index

| Field | Value |
|---|---|
| Azure AI Search index | `enterprise-knowledge-index` |
| Embedding model | `text-embedding-3-small` |
| Embedding deployment type | Global Standard |
| Embedding dimensions | 1536 |
| Vector algorithm | HNSW |

## Indexed chunk schema

Every indexed chunk must conform to the following schema:

| Field | Type | Required | Purpose |
|---|---|---|---|
| `id` | `Edm.String` | Yes | Unique chunk key. Format: `{document_id}_{chunk_index}`; zero-padded index is acceptable, e.g. `leave-policy_003`. |
| `document_id` | `Edm.String` | Yes | Stable identifier for the source document. |
| `chunk_index` | `Edm.Int32` | Yes | Zero-based ordering of chunks within the source document. |
| `title` | `Edm.String` | Yes | Human-readable title/section heading associated with the chunk. |
| `content` | `Edm.String` | Yes | The text content of the indexed chunk. |
| `embedding` | `Collection(Edm.Single)` | Yes | 1536-dimensional vector generated from `content` using `text-embedding-3-small`. |
| `source_file` | `Edm.String` | Yes | Original source filename, e.g. `leave-policy.md`. |
| `source_path` | `Edm.String` | Yes | Source location used by the ingestion pipeline. Current pilot uses the repository path; this may become a blob/URI in production. |
| `document_type` | `Edm.String` | Yes | Logical source type such as `policy`, `faq`, or `ticket-data`. |
| `permission_tags` | `Collection(Edm.String)` | Yes | One or more access-control groups applicable to the chunk, e.g. `["all-employees", "hr"]`. |
| `ingested_at` | `Edm.DateTimeOffset` | Yes | UTC timestamp for when the chunk was indexed. |

### Key rules

- `id` is the index key and must be unique across the entire index.
- `chunk_index` preserves source-document chunk ordering and should start at 0.
- `permission_tags` is a collection, not a single string, so a chunk can be visible to multiple groups.
- `embedding` is stored for vector retrieval and is **not** returned as normal search result content (marked non-retrievable in the index definition).

---

## Chunking policy

The pilot uses **structure-first chunking**.

1. Parse the Markdown document and **remove YAML frontmatter** before chunking or embedding.
   - Frontmatter is stripped and **not parsed**. No frontmatter fields are read by the ingestion pipeline.
   - `document_id` is derived from the **source filename stem** (e.g. `leave-policy.md` → `leave-policy`), not from any frontmatter field.
   - `permission_tags` must be supplied by the caller or configured in the ingestion pipeline (currently via `PERMISSION_TAGS_MAP` in `backend/scripts/ingest_pilot_documents.py`). The `permissions_tag` field present in some pilot-document frontmatter is intentionally ignored.
2. Split the document by Markdown headings/sections.
3. Keep a section together when it is at or below the configured limit.
4. When a section exceeds the limit, split that section into token-based chunks.
   - Use a maximum of approximately **500 tokens** per fallback chunk.
   - Use **60 tokens** of overlap between fallback chunks.
5. Preserve `chunk_index` ordering within each document.

This strategy is intended to keep chunks semantically coherent while still handling oversized sections.

## Embedding policy

- The embedding input is the final `content` text of each chunk.
- Embeddings are generated with the Azure OpenAI deployment named `text-embedding-3-small` (see Deployment name note above).
- The output vector dimension is 1536.
- The same embedding model/deployment must be used for both document embeddings and query embeddings in this pilot.

## Retrieval contract

Query-time retrieval should follow this pattern:

```
User query
   ↓
text-embedding-3-small
   ↓
query vector
   ↓
Azure AI Search vector search on `embedding`
   ↓
Top-k chunks
```

**Current pilot uses pure vector search only.** Hybrid search (vector + keyword + semantic ranking) — the configuration recommended in the project plan for production quality — is deferred; this is a known gap, not the final retrieval design.

Retrieved records should expose enough metadata to provide a verifiable citation, at minimum:

- `title`
- `content`
- `source_file`
- `source_path`
- `document_id`
- `chunk_index`
- `document_type`

## Permission semantics

`permission_tags` represents the access groups allowed to see a chunk.

Examples:
- `["all-employees"]`
- `["all-employees", "hr"]`

The field is designed to support filter-based permission-aware retrieval. Actual authentication/authorization enforcement is outside this ingestion contract and must be applied by the application layer when user identity and group membership are available.

---

## Pilot validation

The current pilot contains **5** synthetic enterprise-policy documents and **19** indexed chunks.

Basic vector retrieval has been verified for:

- Annual leave → `leave-policy.md`
- Reimbursement → `reimbursement-policy.md`
- Work-from-home rules → `work-from-home-policy.md`

A VPN-related query was also tested as a knowledge-gap case; the closest semantic result was returned, but the pilot corpus does not contain a VPN-specific requirement. This demonstrates that retrieval alone must not be treated as proof that sufficient evidence exists to answer a question.

## Future-compatible fields

The current contract intentionally includes `ingested_at` and `document_type` because downstream ingestion-status and multi-source workflows are expected to need them.

Potential future metadata such as `page_number` and `token_count` is not required by the current pilot and is therefore deferred.

---

## Day 1 Summary Log

- Discovered Azure for Students subscription restricts deployments to: East Asia, Korea Central, South Central India, Central India, Malaysia West.
- Deployed Foundry project + Azure AI Search (`ai103-enterprise-search-ravish`) in Central India.
- `text-embedding-3-small` unavailable in Central India's Foundry model catalog; deployed a separate Azure OpenAI resource (`ai103-openai-embedding`) in Korea Central instead — Global Standard, 1536 dimensions.
- Defined and created `enterprise-knowledge-index` (HNSW vector search, 11-field schema — see above).
- Ingested 5 synthetic policy documents → 19 chunks, structure-first chunking (500 token max, 60 token overlap), YAML frontmatter stripped before chunking.
- Verified vector retrieval against 4 test questions; 3 returned correct source documents, 1 (VPN) correctly surfaced as a knowledge gap — no VPN-specific content exists in the pilot corpus.
- Scripts: `backend/scripts/create_search_index.py`, `backend/scripts/ingest_pilot_documents.py`, `backend/scripts/test_retrieval.py`.

## Source of truth

Any ingestion implementation should conform to this contract. Changes to field names, types, embedding dimensions, chunking behavior, or permission semantics should be reviewed before implementation so downstream modules remain compatible.