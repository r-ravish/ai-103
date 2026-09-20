# Foundry Tracing — Day 3 Guide

Tracing enables the team to inspect the **complete request path** for every evaluation
question:

```
User query
    ↓
Azure AI Foundry Agent (Responses API)
    ↓
RAG retrieval — knowledge_base_retrieve MCP tool
    ↓
[Optional] MCP tool call — create_support_ticket / get_support_ticket
    ↓
Final answer generation
    ↓
Response returned to /chat
```

This guide explains where traces are recorded, how to locate a specific request, and
what information is available at each step.

---

## 1. Where Traces Are Recorded

All agent activity is captured automatically by the **Azure AI Foundry** portal.

Navigate to:

```
Azure AI Foundry → Your Project → Tracing
```

Every call to `foundry_service.ask()` in `backend/app/foundry_agent.py` produces a trace.
The trace is identified by the **response ID** returned by the Responses API
(field `response_id` in `backend/app/foundry_agent.py` line `return {..., "response_id": response.id}`).

---

## 2. Correlating an Evaluation Request to a Trace

### Step 1 — Find the response_id in the evaluation run log

When the backend is running, every `/chat` call logs the response ID:

```
INFO  Agent replied (142 chars, 2 citations)
```

The response ID also appears in the Foundry tracing portal automatically.

### Step 2 — Filter traces in the portal

In the Foundry Tracing view:

1. Set the time range to the evaluation run window.
2. Filter by **Agent name**: `enterprise-knowledge-agent`.
3. Each row is one `responses.create` call — one per question.

### Step 3 — Open the trace

Click any row to see the full trace tree.

---

## 3. What Each Trace Shows

### For a RAG question (e.g. LEAVE-001, WFH-001)

```
responses.create
  └── knowledge_base_retrieve          ← retrieval MCP call
        └── [retrieved chunks list]
  └── assistant message
        └── answer text
        └── url_citation annotations   ← citation source URLs
```

**What to verify:**
- ✅ Correct documents retrieved (check chunk source_file fields)
- ✅ Answer grounded in retrieved chunks
- ✅ Citations match the retrieved document IDs

### For a tool-calling question (e.g. TOOL-001, TOOL-002)

```
responses.create (first call)
  └── knowledge_base_retrieve (may or may not fire)
  └── mcp_approval_request              ← agent wants to call tool
        └── server: enterprise-support-mcp
        └── tool: create_support_ticket

responses.create (second call — approval submitted)
  └── mcp_call: create_support_ticket
        └── input: { title, description, priority }
        └── output: Ticket created. ID: TKT-XXXXXXXX ...
  └── assistant message
        └── final answer (includes TKT-XXXXXXXX)
```

**What to verify:**
- ✅ `mcp_approval_request` was emitted (agent correctly identified tool need)
- ✅ `create_support_ticket` was called (not fabricated)
- ✅ Tool inputs are accurate (title/description match the question)
- ✅ Tool output contains a real `TKT-XXXXXXXX` ID
- ✅ Final answer references the ticket ID from the tool output

### For a knowledge-gap question (e.g. VPN-001, LEAVE-005)

```
responses.create
  └── knowledge_base_retrieve
        └── [chunks returned — but from unrelated docs]
  └── assistant message
        └── answer: "I don't have sufficient information..."
        └── [no url_citation annotations — agent suppressed them]
```

**What to verify:**
- ✅ Agent correctly suppressed citations when gap detected
- ✅ No ticket tool was called
- ✅ Answer does not fabricate policy details

---

## 4. Trace Fields Reference

| Field | Location in trace | Purpose |
|---|---|---|
| `response.id` | Top-level | Unique ID for this Responses API call |
| `input` | Top-level | The question sent to the agent |
| `output[].type == "message"` | Output array | Final assistant message |
| `output[].content[].annotations` | Message content | `url_citation` entries (citation sources) |
| `output[].type == "mcp_call"` | Output array | A completed MCP tool call |
| `output[].type == "mcp_approval_request"` | Output array | Agent requesting tool use |
| `output[].name` | MCP call | Tool name (e.g. `create_support_ticket`) |
| `output[].input` | MCP call | Arguments passed to the tool |
| `output[].output` | MCP call | Tool return value |
| `output_text` | Top-level | Cleaned final answer (inline citations stripped) |

---

## 5. How to Identify a Specific Evaluation Request

The evaluation script (`evaluation/run_eval.py`) logs the HTTP response for each question.
When the backend is running locally, the backend logs will show the Foundry `response.id`.

**To link an eval record to a trace:**

1. Look up `question_id` in `evaluation/results/day3-results.json`
2. Find the corresponding backend log line with the timestamp and question preview
3. The Foundry portal trace for that time window will contain the matching call

For future runs, consider adding `response_id` directly to the evaluation result record
by extending the `/chat` response schema with `"response_id": response.id`.

---

## 6. Trace Expectations per Category

| Category | Expected trace shape |
|---|---|
| `answerable` | `knowledge_base_retrieve` → answer with citations |
| `edge_case` | `knowledge_base_retrieve` → answer with citations (policy boundary reasoning) |
| `knowledge_gap` | `knowledge_base_retrieve` → answer without citations (gap detected) |
| `out_of_scope` | May skip retrieval → answer: "not available in knowledge base" |
| `tool_action` | `knowledge_base_retrieve` (optional) → `mcp_approval_request` → `create_support_ticket` → answer with TKT ID |
| `no_tool` | `knowledge_base_retrieve` → answer with citations → **no** `mcp_approval_request` |

---

## 7. Debugging a Failed Evaluation Question

For every FAIL in `day3-results.json`, inspect the trace and answer:

### Was the failure in retrieval?

- Check: Did `knowledge_base_retrieve` return the expected document?
- If the wrong document was retrieved: re-run ingestion or review the chunk index.

### Was the failure in tool selection?

- For `tool_action` questions: Did `mcp_approval_request` appear? If not, the agent
  did not recognise the tool need — check the agent's system prompt.
- For `no_tool` questions: Did `mcp_approval_request` appear when it should not?
  If so, the agent is over-triggering tool use — check system prompt constraints.

### Was the failure in tool execution?

- Check: Did `create_support_ticket` return an error?
- Verify MCP server (`backend/mcp_server.py`) is running and reachable.
- Verify the `/internal/tickets` route is registered in `backend/app/main.py`.

### Was the failure in answer generation?

- Check: Did the agent receive correct retrieval output but still produce a wrong answer?
- This is an LLM reasoning failure — review the agent's instructions in Foundry.

### Was it a citation failure only?

- Check: Is the answer correct but the citation points to the wrong document?
- Review `_extract_citations` in `backend/app/foundry_agent.py`.

---

## 8. Next Steps (Day 4+)

- Add `response_id` to the `/chat` response schema so the eval script can log it directly.
- Build a trace dashboard in `dashboard/app.py` to visualise per-question traces.
- Use Foundry tracing for Day 4 escalation evaluation (verify escalation path in trace).
