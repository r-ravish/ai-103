# API Contract — POST /chat

> **Status**: Draft stub — to be finalised at the start of Day 2 before `feature/agent-core` coding begins.
>
> The frontend `types/chat.ts` already defines a `Citation` type whose field names mirror the ingestion contract retrieval metadata. The response shape below is designed so that wiring up the frontend is a mapping exercise, not a UI rewrite.

---

## Endpoint

```
POST /chat
Content-Type: application/json
```

## Request

```json
{
  "message": "How many days of annual leave do I get?",
  "conversation_id": "optional-uuid-for-multi-turn"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `message` | `string` | Yes | The user's question. |
| `conversation_id` | `string` | No | Omit for a new conversation. Pass back the value returned by a previous response to continue a thread. |

## Response — grounded answer

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "Employees are entitled to 18 days of paid annual leave per calendar year.",
  "is_knowledge_gap": false,
  "citations": [
    {
      "title": "Employee Leave Policy",
      "content": "Employees are entitled to 18 days of paid annual leave per calendar year.",
      "source_file": "leave-policy.md",
      "source_path": "docs/pilot-documents/leave-policy.md",
      "document_id": "leave-policy",
      "chunk_index": 0,
      "document_type": "policy"
    }
  ]
}
```

## Response — knowledge gap

When the agent cannot find sufficient grounded evidence, it **must not fabricate**. Instead:

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "I could not find information about VPN requirements in the current knowledge base. Please contact the IT security team directly.",
  "is_knowledge_gap": true,
  "citations": []
}
```

## Response fields

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | `string` | Echo back or generate a new UUID for the thread. |
| `answer` | `string` | The agent's response text. |
| `is_knowledge_gap` | `boolean` | `true` when the agent could not find grounded evidence. Never omit this field. |
| `citations` | `array` | Zero or more citation objects. Empty for knowledge-gap responses. |

### Citation object fields

Field names intentionally match the ingestion-contract retrieval metadata and the frontend `Citation` type in `frontend/types/chat.ts`.

| Field | Type | Notes |
|---|---|---|
| `title` | `string` | Section heading or document title. |
| `content` | `string` | The retrieved chunk text used to ground this answer. |
| `source_file` | `string` | Original filename, e.g. `leave-policy.md`. |
| `source_path` | `string` | Repository or blob path. |
| `document_id` | `string` | Stable document identifier (filename stem). |
| `chunk_index` | `integer` | Zero-based chunk position within the document. |
| `document_type` | `string` | Logical type: `policy`, `faq`, `ticket-data`, etc. |

## Error responses

| Status | Meaning |
|---|---|
| `422` | Request validation error (missing required field, wrong type). |
| `500` | Unhandled server error. |

---

## Frontend integration notes

- `is_knowledge_gap` maps directly to `Message.isKnowledgeGap` in `frontend/types/chat.ts`.
- `citations` maps to `Message.citations`. Each citation object maps to the `Citation` interface (camelCase in TS, snake_case in JSON — the mapping lives in `lib/mockResponses.ts` → replace with real fetch).
- The mock seam to replace is `getMockResponse` in `frontend/lib/mockResponses.ts`.
