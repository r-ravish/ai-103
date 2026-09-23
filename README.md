# Enterprise Knowledge Agent

Internal HR and IT policy Q&A system powered by Azure AI Foundry Agents and Azure AI Search RAG.
Employees ask questions in natural language; the agent retrieves grounded answers with citations from the policy knowledge base.

---

## Team

| Role | Person | Day 1 module |
|---|---|---|
| Lead / RAG foundation | Ravish | `backend/scripts/`, `docs/ingestion-contract.md` |
| Frontend | Radhika | `frontend/` |
| Evaluation | Aditya | `evaluation/` |
| Dashboard | Disha | `dashboard/` |
| Onboarding module | Rakshit | `onboarding/` (Day 3) |

---

## Module map

```
/
├── backend/
│   ├── app/            ← FastAPI app (Day 2: POST /chat)
│   │   └── main.py     ← entry point: uvicorn app.main:app --reload
│   ├── scripts/        ← one-off utility scripts
│   │   ├── create_search_index.py    ← creates / updates the Azure AI Search index
│   │   ├── ingest_pilot_documents.py ← chunks, embeds, and uploads pilot docs
│   │   └── test_retrieval.py         ← smoke-tests vector retrieval
│   ├── requirements.txt
│   └── .env.example    ← copy to .env and fill in your values
│
├── docs/
│   ├── ingestion-contract.md  ← source of truth for chunk schema, embedding config, retrieval
│   └── pilot-documents/       ← 5 synthetic policy documents (19 indexed chunks)
│
├── evaluation/
│   ├── evaluation_set.json    ← 22 graded questions for automated evaluation (v3.0)
│   ├── evaluation_set.md      ← human-readable companion
│   ├── run_eval.py            ← Day 4 evaluation script (correctness, citations, escalation)
│   ├── tracing.md             ← Foundry tracing guide
│   └── content_safety.md      ← Azure AI Content Safety preparation notes
│
├── frontend/                  ← Next.js chat shell (mock backend, real UI)
├── dashboard/                 ← Streamlit metrics dashboard (connected to live data)
└── onboarding/                ← Rakshit's document ingestion module (Day 3)
```

---

## Azure resources (Day 1)

| Resource | Name | Region |
|---|---|---|
| Microsoft Foundry project | `ai-103-enterprise-knowledge-agent` | Central India |
| Azure AI Search | `ai103-enterprise-search-ravish` | Central India |
| Azure OpenAI (embedding) | `ai103-openai-embedding` | Korea Central |
| Search index | `enterprise-knowledge-index` | — |
| Embedding deployment | `text-embedding-3-small` · Global Standard · 1536 dim | — |

> The embedding resource is in Korea Central (not Central India) because `text-embedding-3-small` was unavailable in the Foundry model catalog for that region. See `docs/ingestion-contract.md` for the full decision log.

---

## Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd ai-103

# 2. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install backend dependencies
pip install -r backend/requirements.txt

# 4. Configure environment variables
cp backend/.env.example backend/.env
# Open backend/.env and fill in all values (see .env.example for instructions)

# 5. Run the backend (Day 2+)
cd backend
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

---

## Git workflow

| Branch | Purpose |
|---|---|
| `main` | Stable release checkpoints — merged from `develop` at day-end milestones |
| `develop` | Integration branch — all feature branches merge here via PR |
| `feature/<name>` | One branch per day/feature; PR → `develop` when ready |

---

## Key documents

- **`docs/ingestion-contract.md`** — chunk schema, embedding config, retrieval contract. Rakshit's onboarding module must conform to this.
- **`evaluation/evaluation_set.json`** — 22-question graded evaluation set (v3.0). Aditya's automated runner reads this.
- **`evaluation/run_eval.py`** — Day 4 evaluation script: correctness, citations, tool calls, and structured escalation scoring.
- **`evaluation/results/day3-summary.md`** — latest evaluation run results (human-readable).
- **`evaluation/tracing.md`** — Foundry tracing guide for inspecting query → retrieval → tool → answer.
- **`frontend/lib/mockResponses.ts`** — the seam to replace when the real backend is ready.

---

## Responsible AI

This section documents the mechanisms the Enterprise Knowledge Agent uses to reduce unsupported answers and unsafe behaviour, and the measured results from evaluation.

### 1. Grounded Retrieval

Every answer is generated from chunks retrieved from the enterprise policy knowledge base via Azure AI Search vector retrieval. The agent does not answer from general knowledge alone — it retrieves relevant policy passages first, then generates an answer grounded in those passages.

- Knowledge base: 5 synthetic pilot policy documents (19 indexed chunks)
- Retrieval: `text-embedding-3-small` embeddings, cosine similarity
- Chunk metadata: `source_file`, `chunk_id`, `policy_area`

### 2. Citation Display

When the agent answers from the knowledge base, it returns structured citation metadata alongside the answer:

```json
{
  "answer": "...",
  "citations": [{ "source_file": "leave-policy.md", "title": "Leave Policy" }]
}
```

Users can verify which policy document the answer was drawn from. The evaluation checks that `citations` contains the expected `source_file` for every answerable question.

### 3. Out-of-Scope Detection and Escalation

When the agent cannot find grounded evidence in the knowledge base, it does not guess. Instead:

1. The backend detects the knowledge gap using marker phrases in the initial agent response.
2. It automatically triggers the `create_support_ticket` MCP tool to escalate the request to a human reviewer.
3. The `/chat` response includes structured escalation fields:

```json
{
  "escalation_required": true,
  "escalation_reason": "knowledge_gap",
  "action_taken": true,
  "action_type": "escalation",
  "ticket_id": "TKT-XXXXXXXX"
}
```

Every out-of-scope question results in a human-reviewed support ticket, not a hallucinated answer.

### 4. Human Escalation via MCP Tool

The MCP server (`backend/mcp_server.py`) exposes `create_support_ticket` and `get_support_ticket` tools. The Foundry agent uses these tools for:

- **Direct support requests** — employee explicitly asks to create a ticket
- **Automatic escalation** — agent detects it cannot answer and escalates without being asked

All MCP tool calls require approval via `_approve_mcp_requests` before execution.

### 5. Content Safety Screening

Azure AI Content Safety screens all inputs and outputs through the `/chat` endpoint:

- Input screened before reaching the agent (HTTP 400 on blocked input)
- Output screened before returning to the client (safe refusal replaces blocked output)
- Configured severity threshold: `2` (Low — appropriate for enterprise HR context)
- Passthrough mode available for local development

See `evaluation/content_safety.md` for the full test scenarios and integration notes.

### 6. Evaluation Methodology

The evaluation system (`evaluation/run_eval.py`) tests 22 questions across 7 categories:

| Category | Questions | What is evaluated |
|---|---|---|
| answerable | 8 | RAG retrieval quality, fact accuracy, citation correctness |
| edge_case | 4 | Boundary condition reasoning, no hallucination |
| knowledge_gap | 2 | Escalation triggered, no fabricated policy |
| out_of_scope | 1 | Escalation triggered, no speculation |
| tool_action | 2 | `create_support_ticket` called, TKT ID returned |
| no_tool | 2 | Tool NOT called for policy questions |
| escalation | 3 | Out-of-corpus scenarios escalate correctly |

Escalation is verified using **structured response fields** (`escalation_required`, `escalation_reason`, `action_taken`, `action_type`), not text matching. Results are written to `evaluation/results/day3-results.json` for dashboard consumption.

### 7. Current Limitations

- **Pilot corpus only.** Results may not generalise to a full production document set.
- **Heuristic gap detection.** Knowledge gap detection uses marker phrases. Subtle hallucinations that do not trigger these markers may not be detected.
- **English only.** Multilingual behaviour has not been evaluated.
- **No confidence score.** Gap detection is based on language patterns, not a calibrated probability.
- **Automated-heuristic correctness scoring.** Uses keyword matching, not semantic similarity. Manual review of edge-case results is recommended.
- **Azure authentication required for full runs.** The evaluation script requires an authenticated Azure environment to run against the real backend.

These limitations are consistent with the scope of a Day 4 pilot evaluation and should be addressed before production deployment.
