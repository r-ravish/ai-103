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
│   ├── evaluation_set.json    ← 15 graded questions for automated evaluation
│   ├── evaluation_set.md      ← human-readable companion
│   └── content_safety.md      ← Azure AI Content Safety preparation notes
│
├── frontend/                  ← Next.js chat shell (mock backend, real UI)
├── dashboard/                 ← Streamlit metrics dashboard skeleton
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

Current active branch: `feature/agent-core` (Day 2 — `POST /chat` + Foundry Agent).

---

## Key documents

- **`docs/ingestion-contract.md`** — chunk schema, embedding config, retrieval contract. Rakshit's onboarding module must conform to this.
- **`evaluation/evaluation_set.json`** — 15-question graded evaluation set. Aditya's automated runner reads this.
- **`frontend/lib/mockResponses.ts`** — the seam to replace when the real backend is ready (see comment at top of file).
